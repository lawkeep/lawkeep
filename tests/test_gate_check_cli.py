"""Gate (B): `lawkeep check` end to end (exit codes, JSON shape, plain-English text)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lawkeep import cli, history, ledger

FIXTURES = Path(__file__).parent / "fixtures" / "gate"


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    shutil.copytree(FIXTURES / "refunds_project", root)
    (root / "laws" / "history.jsonl").touch()
    (root / "laws" / "failing_examples.jsonl").touch()
    history.record_change(root, action="init", actor="person:tester", direction="stricter")
    return root


def plant_bug(root: Path) -> None:
    shutil.copy(FIXTURES / "buggy_refunds.py", root / "src" / "shop" / "refunds.py")


def check(root: Path, capsys, *extra: str) -> tuple[int, dict]:
    code = cli.main(["check", "--json", "--root", str(root), *extra])
    out = capsys.readouterr().out
    return code, json.loads(out)


def check_text(root: Path, capsys, *extra: str) -> tuple[int, str]:
    """Human output, rendered wide so phrases are not wrapped (fitting narrow terminals is
    tested in test_ui_output.py)."""
    old = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = "200"
    try:
        code = cli.main(["check", "--root", str(root), *extra])
    finally:
        if old is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = old
    return code, capsys.readouterr().out


def test_all_hold_json_shape(tmp_path, capsys):
    root = make_project(tmp_path)
    code, data = check(root, capsys)
    assert code == 0 and data["exit_code"] == 0
    assert list(data)[:5] == ["kind", "schema_version", "exit_code", "summary", "lawkeep_version"]
    assert data["kind"] == "check" and data["schema_version"] == 1
    assert data["summary"] == "ALL LAWS HOLD (3 of 3)"
    assert data["profile"] == "pr" and data["root"] == str(root.resolve())
    for key in ("laws", "integrity", "waiting", "notes", "started_at", "duration_seconds"):
        assert key in data
    law = next(x for x in data["laws"] if x["law_id"] == "refunds.refund_is_capped")
    assert set(law) >= {
        "law_id",
        "sentence",
        "status",
        "level",
        "examples_tried",
        "simplest_failing_example",
        "failure_message",
        "duration_seconds",
        "evidence",
        "file",
        "nodeid",
    }
    assert law["status"] == "holds" and law["examples_tried"] == 60
    assert law["evidence"]["profile"] == "pr" and law["evidence"]["backend"] == "hypothesis"


def test_all_hold_text(tmp_path, capsys):
    root = make_project(tmp_path)
    code, text = check_text(root, capsys)
    assert code == 0
    assert "ALL LAWS HOLD" in text and "All 3 of your laws held on your current code." in text
    assert "“A refund never exceeds the original charge”" in text
    assert "lawkeep tried up to 60 inputs per law (the same inputs every run" in text
    assert "Next step: Nothing to do." in text


def test_failing_law_json_text_and_saved_example(tmp_path, capsys):
    root = make_project(tmp_path)
    plant_bug(root)
    code, data = check(root, capsys)
    assert code == 1
    assert data["summary"] == "SOME LAWS FAIL (1 of 3 fail)"
    law = next(x for x in data["laws"] if x["status"] == "fails")
    assert law["simplest_failing_example"] == {"charge": "0", "amount": "1001"}
    saved = ledger.load(root)
    assert len(saved) == 1 and saved[0]["example"] == {"charge": "0", "amount": "1001"}
    assert any("saved 1 new failing input" in n for n in data["notes"])

    code, text = check_text(root, capsys, "--details")
    assert code == 1
    assert "SOME LAWS FAIL" in text and "1 of 3 laws broke on your current code" in text
    assert "This law fails" in text and "law id refunds.refund_is_capped" in text
    assert "The input that breaks it: charge: $0" in text and "amount: $1001" in text
    assert "exact value: charge=0, amount=1001" in text  # --details keeps the raw value
    assert "lawkeep also re-tried 1 saved failing example." in text
    assert "stop and ask a person" in text and "do not edit" in text
    assert len(ledger.load(root)) == 1  # replaying the same failure does not grow the file


def test_no_save(tmp_path, capsys):
    root = make_project(tmp_path)
    plant_bug(root)
    code, data = check(root, capsys, "--no-save")
    assert code == 1 and ledger.load(root) == []
    assert any("--no-save" in n for n in data["notes"])


def test_unrecorded_change_waits_for_a_person(tmp_path, capsys):
    root = make_project(tmp_path)
    p = root / "laws" / "refunds.py"
    p.write_text(p.read_text().replace("<= charge", "<= charge + 10**9"))  # weakened, still holds
    code, data = check(root, capsys)
    assert code == 2
    assert data["summary"].startswith("WAITING FOR YOUR DECISION (3 of 3 laws hold")
    issue = next(i for i in data["integrity"] if i["kind"] == "unrecorded_law_change")
    assert issue["severity"] == "error" and issue["path"] == "laws/refunds.py"
    code, text = check_text(root, capsys)
    assert "Needs a person's decision" in text and "unrecorded law change" in text


def test_failure_beats_waiting(tmp_path, capsys):
    root = make_project(tmp_path)
    plant_bug(root)
    (root / "laws" / "strategies.py").write_text(
        (root / "laws" / "strategies.py").read_text() + "\n# touched\n"
    )
    code, data = check(root, capsys)
    assert code == 1
    assert any(i["kind"] == "unrecorded_law_change" for i in data["integrity"])


def test_pending_proposal_waits(tmp_path, capsys):
    root = make_project(tmp_path)
    history.record_change(
        root,
        action="change_law",
        actor="agent:test",
        law_id="refunds.refund_is_capped",
        direction="looser",
        status="waiting",
        permission_used="ask",
        reason="no fees on tiny refunds",
        sentence_after="A refund may exceed the charge a bit",
    )
    code, data = check(root, capsys)
    assert code == 2
    assert data["waiting"][0]["law_id"] == "refunds.refund_is_capped"
    assert data["waiting"][0]["change"] == "waiting"


def test_outside_conftest_trick_is_not_loaded_and_is_flagged(tmp_path, capsys):
    root = make_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    plant_bug(root)
    (root / "conftest.py").write_text(
        "import shop.refunds as r\nr.refund = lambda charge, amount: min(amount, charge)\n"
    )
    code, data = check(root, capsys)
    assert code == 1  # the law still fails: the conftest.py did not run
    flagged = [i for i in data["integrity"] if i["kind"] == "side_door_file"]
    assert [i["path"] for i in flagged] == ["conftest.py"]
    assert flagged[0]["severity"] == "warning"


def test_law_filter(tmp_path, capsys):
    root = make_project(tmp_path)
    code, data = check(root, capsys, "--law", "refunds.fee_example")
    assert code == 0 and [x["law_id"] for x in data["laws"]] == ["refunds.fee_example"]


def test_unknown_law_id_suggests_a_close_match(tmp_path, capsys):
    root = make_project(tmp_path)
    code, data = check(root, capsys, "--law", "refunds.refund_is_caped")
    assert code == 3 and data["exit_code"] == 3
    assert data["kind"] == "check" and "hint" in data
    assert "Did you mean refunds.refund_is_capped?" in data["hint"]

    code, data = check(root, capsys, "--law", "not_a_law_at_all")
    assert code == 3 and "Did you mean" not in data["hint"]


def test_deep_profile(tmp_path, capsys):
    root = make_project(tmp_path)
    code, data = check(root, capsys, "--profile", "deep")
    assert code == 0 and data["profile"] == "deep"
    law = next(x for x in data["laws"] if x["law_id"] == "refunds.refund_is_capped")
    assert law["examples_tried"] == 200 and law["evidence"]["derandomize"] is False


def test_unknown_profile_is_setup_problem(tmp_path, capsys):
    root = make_project(tmp_path)
    code, data = check(root, capsys, "--profile", "nightly-ish")
    assert code == 3 and data["exit_code"] == 3


def test_no_project_is_setup_problem_via_console(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "lawkeep", "check", "--json", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["exit_code"] == 3


def test_console_exit_code_for_failure(tmp_path):
    root = make_project(tmp_path)
    plant_bug(root)
    proc = subprocess.run(
        [sys.executable, "-m", "lawkeep", "check", "--json", "--root", str(root)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stderr
    data = json.loads(proc.stdout)  # stdout holds exactly one JSON document
    assert data["exit_code"] == 1


def test_no_laws_yet(tmp_path, capsys):
    root = tmp_path / "empty"
    (root / "laws").mkdir(parents=True)
    (root / "lawkeep.toml").write_text("")
    (root / "laws" / "history.jsonl").touch()
    (root / "laws" / "failing_examples.jsonl").touch()
    history.record_change(root, action="init", actor="person:tester")
    code, data = check(root, capsys)
    assert code == 0 and "no laws yet" in data["summary"]
