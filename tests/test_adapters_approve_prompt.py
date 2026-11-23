"""The guard's "confirm `lawkeep approve`" question: asked only when a command runs approve,
and written so the person sees what they would approve (adapters/approve_preview.py)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from lawkeep import approvals, cli, direction, history
from lawkeep.adapters import approve_preview, guard
from lawkeep.adapters.writes import ApproveRun
from lawkeep.commands import approve as approve_cmd
from lawkeep.models import HistoryEntry, LawInfo

FIX = Path(__file__).parent / "fixtures" / "lifecycle"
LAW_ID = "pricing.discount_never_raises_price"


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    (root / "laws").mkdir(parents=True)
    (root / "lawkeep.toml").write_text("", encoding="utf-8")
    return root


def bash(root: Path, command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(root)}


# ------------------------------------------------------------------ ask only when it runs

ASK = [
    "lawkeep approve",
    "uv run lawkeep approve --yes x",
    "python -m lawkeep approve",
    "python3 -m lawkeep approve h-1 --no",
    ".venv/bin/lawkeep approve",
    'bash -c "lawkeep approve"',
    "sh -c 'cd sub && lawkeep approve h-1 --yes'",
    "cd sub && lawkeep approve",
    "env LAWKEEP_X=1 lawkeep approve h-1",
    "sudo lawkeep approve h-1 --yes",
    "timeout 30 lawkeep approve h-1 --yes",
    "uvx lawkeep approve h-1 --yes",
    "lawkeep --root . approve h-1",
    "echo h-1 | xargs lawkeep approve --yes",
    "python -c \"import subprocess; subprocess.run(['lawkeep','approve'])\"",
    "python -c \"import os; os.system('lawkeep approve h-1 --yes')\"",
    "python -c \"import subprocess, sys; subprocess.run(['lawkeep', 'approve', input()])\"",
    'python -c \'from lawkeep.cli import main; main(["approve", "--yes"])\'',
    'python -c \'from lawkeep import history; history.record_change(".", action="x")\'',
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['lawkeep', 'approve', 'h-1'])\nEOF",
    "node -e \"require('child_process').execSync('lawkeep approve h-1 --yes')\"",
]

HEREDOC_EXAMPLE = """cd /tmp/scratch && ls -la; python3 - <<'EOF'
from pathlib import Path
p=Path("issues.py"); t=p.read_text()
reps=[("old text", "Run `lawkeep draft <module> --request ...` and then `lawkeep approve`."),
      ("x", "'approve' and 'lawkeep' as words")]
for a, b in reps:
    t = t.replace(a, b)
p.write_text(t)
EOF
python3 issues.py issues.json"""

ALLOW = [
    HEREDOC_EXAMPLE,
    'git commit -m "docs: explain lawkeep approve"',
    'echo "run lawkeep approve later" > notes.md',
    "printf 'lawkeep approve h-1 --yes\\n' >> TODO.md",
    'grep -r "lawkeep approve" docs',
    "rg 'lawkeep approve' src",
    "python3 - <<'EOF'\nprint(\"lawkeep approve\")\nEOF",
    'python3 -c \'print("lawkeep", "approve")\'',
    "cat > notes.md <<'EOF'\nNext: lawkeep approve h-1 --yes\nEOF",
    "python3 -c \"import subprocess; subprocess.run(['gh', 'issue', 'create', '--body', "
    "'then run lawkeep approve'])\"",
    "lawkeep approve --help",
    "lawkeep approve -h",
    "lawkeep --help",
    "lawkeep report",
    "lawkeep check",
    "lawkeep propose x --file laws/drafts/x.py --reason 'approve later'",
]


@pytest.mark.parametrize("command", ASK)
def test_running_approve_asks(tmp_path, command):
    root = make_project(tmp_path)
    (root / "sub").mkdir()
    d = guard.decide(bash(root, command))
    assert d.action == "ask", command
    assert d.message.startswith("lawkeep: your coding agent wants to")
    assert "Not sure? Say no" in d.message
    assert guard.is_approval_command(command), command


@pytest.mark.parametrize("command", ALLOW)
def test_mentioning_approve_does_not_ask(tmp_path, command):
    root = make_project(tmp_path)
    assert guard.decide(bash(root, command)).action == "allow", command
    assert not guard.is_approval_command(command), command


def test_a_script_file_that_only_mentions_approve_does_not_ask(tmp_path):
    root = make_project(tmp_path)
    (root / "issues.py").write_text(
        "import json, subprocess, sys\n"
        "for issue in json.load(open(sys.argv[1])):\n"
        "    body = issue['body'] + ' Then run `lawkeep approve`.'\n"
        "    subprocess.run(['gh', 'issue', 'create', '--body', body, '--label', 'approve'])\n",
        encoding="utf-8",
    )
    assert guard.decide(bash(root, "python3 issues.py issues.json")).action == "allow"


def test_a_script_file_that_runs_approve_asks(tmp_path):
    root = make_project(tmp_path)
    (root / "go.py").write_text(
        "import subprocess\nsubprocess.run(['lawkeep', 'approve', 'h-1', '--yes'])\n",
        encoding="utf-8",
    )
    assert guard.decide(bash(root, "python3 go.py")).action == "ask"


def test_the_fallback_message_is_short_and_plain():
    msg = guard.APPROVE_MESSAGE
    assert msg.startswith("lawkeep: your coding agent wants to record YOUR approval")
    assert "Not sure? Say no" in msg and "`lawkeep approve`" in msg
    assert len(msg) < 300


# ------------------------------------------------------------------ one line per item kind


def _entry(**kw) -> HistoryEntry:
    e = HistoryEntry(action=kw.pop("action", "change_law"), actor="agent:x", **kw)
    e.details.setdefault("proposal_path", "laws/drafts/proposals/x/")
    return e


def _proposal(**kw) -> approve_cmd.Item:
    return approve_cmd.Item("proposal", "h-1", "t", entry=_entry(**kw))


def test_item_lines_for_each_kind():
    loose = _proposal(
        direction="looser",
        law_id="refunds.no_fee",
        sentence_before="A refund never includes a fee",
        sentence_after="A refund may include a fee of at most $1",
    )
    assert approve_preview.item_line(loose, True) == [
        "Loosen “A refund never includes a fee” → “A refund may include a fee of at most $1” "
        "(looser: protects less)"
    ]
    assert approve_preview.item_line(loose, False)[0].startswith("REJECT: Loosen “A refund")
    tight = _proposal(direction="stricter", sentence_before="a", sentence_after="b")
    assert approve_preview.item_line(tight, True) == ["Tighten “a” → “b” (stricter)"]
    unclear = _proposal(direction="unclear", sentence_before="a", sentence_after="b")
    assert "cannot tell whether this protects less" in approve_preview.item_line(unclear, True)[0]
    strong = _proposal(
        action="add_law",
        direction="stricter",
        sentence_after="Totals are never negative",
        details={"strength": {"quick_check_caught": 3, "flags": []}},
    )
    assert approve_preview.item_line(strong, True) == [
        "Add new law “Totals are never negative” (strong)"
    ]
    weak = _proposal(
        action="add_law",
        direction="stricter",
        sentence_after="Totals are numbers",
        details={"strength": {"quick_check_caught": 0, "flags": ["one_sided"]}},
    )
    assert approve_preview.item_line(weak, True)[0].startswith(
        "Add new law “Totals are numbers” (weak"
    )
    gone = _proposal(action="remove_law", direction="looser", sentence_before="Never negative")
    assert approve_preview.item_line(gone, True) == ["Delete the law “Never negative”"]
    skip = _proposal(action="skip_law", direction="looser", sentence_before="Never negative")
    assert approve_preview.item_line(skip, True) == ["Switch off the law “Never negative”"]
    edit = _proposal(direction="looser", details={"from_draft": True, "target_file": "laws/p.py"})
    assert approve_preview.item_line(edit, True) == ["Accept the drafting AI's change to laws/p.py"]
    assert approve_preview.item_line(edit, False) == [
        "REJECT the drafting AI's change to laws/p.py"
    ]
    draft = approve_cmd.Item(
        "draft",
        "laws/drafts/t.py",
        "t",
        laws=[
            LawInfo(law_id="t.a", qualname="a", sentence="Totals add up", file="laws/drafts/t.py"),
            LawInfo(law_id="t.b", qualname="b", sentence="Other", file="laws/drafts/t.py"),
        ],
    )
    assert approve_preview.item_line(draft, True) == [
        "Add new law “Totals add up” (+1 more in the same file)"
    ]
    assert approve_preview.item_line(draft, False)[0].startswith("REJECT the new draft law")
    hand = approve_cmd.Item("unrecorded", "unrecorded", "t", paths=["laws/refunds.py"])
    assert approve_preview.item_line(hand, True) == [
        "Accept a hand edit to laws/refunds.py (made outside lawkeep)"
    ]
    group = approvals.UnconfirmedGroup(
        [
            HistoryEntry(
                action="add_law",
                actor="agent:x",
                approved_by="person:A",
                sentence_after="Totals add up",
            )
        ]
    )
    unconf = approve_cmd.Item("unconfirmed", "h-2", "t", group=group)
    assert approve_preview.item_line(unconf, True) == [
        "Confirm an approval made without a terminal: “Totals add up”"
    ]
    assert approve_preview.item_line(unconf, False)[0].startswith("UNDO an approval")


def test_long_sentences_are_shortened():
    long = "x" * 300
    line = approve_preview.item_line(_proposal(direction="looser", sentence_before=long), True)[0]
    assert len(line) < 140 and "…" in line


def test_the_list_is_capped(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    items = [
        approve_cmd.Item(
            "proposal",
            f"h-{i}",
            "t",
            entry=_entry(direction="stricter", sentence_before=f"law {i}", sentence_after="b"),
        )
        for i in range(8)
    ]
    for it in items:
        assert it.entry is not None
        it.entry.id = it.ref
    monkeypatch.setattr(approve_cmd, "collect", lambda *a, **k: list(items))
    text = approve_preview.describe([ApproveRun([f"h-{i}" for i in range(8)] + ["--yes"])], root)
    assert text.startswith("lawkeep: your coding agent wants to record YOUR approval of 8 law")
    assert text.count("\n• ") == approve_preview.MAX_LINES
    assert "…and 3 more" in text


def test_unknown_and_opaque_runs_say_so(tmp_path):
    root = make_project(tmp_path)
    for runs in ([ApproveRun(None, str(root))], [ApproveRun(["nope", "--yes"], str(root))]):
        text = approve_preview.describe(runs, root)
        assert approve_preview.UNKNOWN in text, text
        assert "Not sure? Say no" in text
    text = approve_preview.describe([ApproveRun(["--bogus-flag"], str(root))], root)
    assert approve_preview.UNKNOWN in text
    text = approve_preview.describe([ApproveRun(["--yes"], str(tmp_path / "elsewhere"))], root)
    assert approve_preview.UNKNOWN in text  # no lawkeep project there
    text = approve_preview.describe([ApproveRun(["--yes"], str(root))], root)
    assert "Nothing is waiting" in text


# ------------------------------------------------------------------ against a real waiting list


@pytest.fixture
def waiting_project(tmp_path, monkeypatch, capsys) -> tuple[Path, dict[str, str]]:
    """The made-up tea shop with a draft, a looser proposal, a skip, a drafting-AI edit and a
    hand edit to lawkeep.toml."""
    monkeypatch.setenv(direction.PLANTED_BUGS_ENV, "0")
    monkeypatch.setattr(approve_cmd, "_interactive", lambda: False)
    root = tmp_path / "teashop"
    shutil.copytree(FIX / "teashop", root)
    agent = f"{sys.executable} {FIX / 'fake_agent.py'} {{prompt_file}}"
    (root / "lawkeep.toml").write_text(
        f'[agent]\nname = "other"\ncommand = "{agent}"\n\n[strength]\nquick_check = false\n',
        encoding="utf-8",
    )
    for name in ("history.jsonl", "failing_examples.jsonl"):
        (root / "laws" / name).write_text("", encoding="utf-8")
    history.record_change(root, action="init", actor="person:tester", direction="stricter")
    monkeypatch.setenv("FAKE_AGENT_MODE", "edit_looser")
    cli.main(["draft", "teashop.pricing", "--root", str(root), "--json"])
    for name in ("looser", "skip"):
        cli.main(
            [
                "propose",
                LAW_ID,
                "--file",
                str(FIX / "proposals" / f"{name}.py"),
                "--reason",
                name,
                "--actor",
                "agent:codex",
                "--root",
                str(root),
                "--json",
            ]
        )
    ids: dict[str, str] = {}
    for e in history.pending(history.read(root)):
        if e.details.get("from_draft"):
            ids["draft_edit"] = e.id
        elif e.action == "skip_law":
            ids["skip"] = e.id
        else:
            ids["looser"] = e.id
    toml = root / "lawkeep.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "# by hand\n", encoding="utf-8")
    capsys.readouterr()
    return root, ids


def _ask(root: Path, command: str) -> str:
    d = guard.decide(bash(root, command))
    assert d.action == "ask", command
    return d.message


def test_the_question_names_what_would_be_approved(waiting_project):
    root, ids = waiting_project
    msg = _ask(root, f"lawkeep approve {ids['looser']} --yes")
    assert msg.startswith(
        "lawkeep: your coding agent wants to record YOUR approval of 1 law change:"
    )
    assert "• Loosen “A discount never makes the price larger”" in msg
    assert "(looser: protects less)" in msg

    msg = _ask(root, f"uv run lawkeep approve {ids['skip']} --no")
    assert "YOUR rejection of 1 law change" in msg
    assert "• REJECT: Switch off the law “A discount never makes the price larger”" in msg

    msg = _ask(root, f"lawkeep approve {ids['draft_edit']} --yes")
    assert "• Accept the drafting AI's change to laws/pricing.py" in msg

    msg = _ask(root, "lawkeep approve laws/drafts/pricing_total.py --yes")
    assert "• Add new law “The total price is never negative”" in msg

    msg = _ask(root, "lawkeep approve --accept-unrecorded --yes")
    assert "• Accept a hand edit to lawkeep.toml (made outside lawkeep)" in msg
    assert "Loosen" not in msg


def test_yes_without_ids_names_only_what_it_decides(waiting_project):
    root, _ = waiting_project
    msg = _ask(root, "lawkeep approve --yes")
    assert "YOUR approval of 1 law change" in msg
    assert "Add new law “The total price is never negative”" in msg
    assert "Loosen" not in msg and "Switch off" not in msg
    assert "3 riskier changes" in msg and "never decides them" in msg


def test_plain_approve_only_lists(waiting_project):
    root, _ = waiting_project
    msg = _ask(root, "lawkeep approve")
    assert "which lists 5 things waiting for YOUR decision" in msg
    assert "decides nothing unless you answer" in msg


def test_unknown_id_says_lawkeep_could_not_tell(waiting_project):
    root, _ = waiting_project
    msg = _ask(root, "lawkeep approve h-00000000 --yes")
    assert "Nothing waiting is called “h-00000000”" in msg
    assert approve_preview.UNKNOWN in msg


def test_the_preview_changes_nothing(waiting_project):
    root, ids = waiting_project
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    _ask(root, f"lawkeep approve {ids['looser']} --yes")
    _ask(root, "lawkeep approve --yes")
    after = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after
