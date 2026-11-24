"""Workstream E: `lawkeep init` creates everything, is idempotent and never clobbers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lawkeep import cli, history, lock


def project(tmp_path: Path, *, git: bool = True) -> Path:
    root = tmp_path / "shop"
    (root / "src").mkdir(parents=True)
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Ada"], check=True)
    return root


def init(root: Path, *args: str, capsys=None) -> tuple[int, dict]:
    code = cli.main(["init", "--root", str(root), "--json", *args])
    data = json.loads(capsys.readouterr().out) if capsys else {}
    return code, data


def test_init_creates_everything(tmp_path, capsys):
    root = project(tmp_path)
    (root / ".claude").mkdir()
    code, data = init(root, capsys=capsys)
    assert code == 0, data
    assert data["kind"] == "init" and data["exit_code"] == 0
    for rel in (
        "lawkeep.toml",
        "laws.lock",
        "laws/strategies.py",
        "laws/history.jsonl",
        "laws/failing_examples.jsonl",
        "AGENTS.md",
        ".gitignore",
        ".claude/settings.json",
        ".mcp.json",
        "CLAUDE.md",
        ".git/hooks/pre-commit",
    ):
        assert (root / rel).is_file(), rel
    assert (root / "laws" / "drafts").is_dir()
    assert ".lawkeep/" in (root / ".gitignore").read_text()
    toml = (root / "lawkeep.toml").read_text()
    assert 'name = "claude-code"' in toml and 'source = ["src"]' in toml
    entries = history.read(root)
    assert [e.action for e in entries] == ["init"]
    assert entries[0].actor == "person:Ada" and entries[0].direction == "stricter"
    assert lock.diff_against_lock(root).is_empty
    assert data["data"]["agents"] == ["claude-code"] and data["data"]["agents_detected"]
    assert "draft laws" in data["hint"]


def test_init_is_idempotent(tmp_path, capsys):
    root = project(tmp_path)
    init(root, "--agent", "all", "--ci", capsys=capsys)
    files_before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts[:1]
    }
    hook_before = (root / ".git" / "hooks" / "pre-commit").read_bytes()
    code, data = init(root, "--agent", "all", "--ci", capsys=capsys)
    assert code == 0
    assert data["data"]["files_changed"] == []
    files_after = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts[:1]
    }
    assert files_after == files_before
    assert (root / ".git" / "hooks" / "pre-commit").read_bytes() == hook_before
    assert [e.action for e in history.read(root)] == ["init"]


def test_init_all_agents_and_ci(tmp_path, capsys):
    root = project(tmp_path)
    code, data = init(root, "--agent", "all", "--ci", capsys=capsys)
    assert code == 0
    for rel in (
        ".codex/hooks.json",
        ".codex/config.toml",
        ".codex/rules/lawkeep.rules",
        ".cursor/hooks.json",
        ".cursor/mcp.json",
        ".cursor/rules/lawkeep.mdc",
        ".github/copilot-instructions.md",
        ".github/hooks/lawkeep.json",
        ".github/workflows/lawkeep.yml",
    ):
        assert (root / rel).is_file(), rel
    wf = (root / ".github" / "workflows" / "lawkeep.yml").read_text()
    assert "uses: lawkeep/lawkeep@v0\n" in wf and "TODO" not in wf
    assert data["data"]["agents"] == ["claude-code", "codex", "cursor", "copilot"]
    assert data["data"]["ci_workflow_added"] is True


def test_init_comma_separated_agents_and_no_hooks(tmp_path, capsys):
    root = project(tmp_path)
    code, data = init(root, "--agent", "codex,cursor", "--no-hooks", "--no-ci", capsys=capsys)
    assert code == 0
    assert data["data"]["agents"] == ["codex", "cursor"]
    assert not (root / ".git" / "hooks" / "pre-commit").exists()
    assert not (root / ".codex" / "hooks.json").exists()
    assert not (root / ".cursor" / "hooks.json").exists()
    assert (root / ".cursor" / "mcp.json").exists()
    assert not (root / ".claude").exists()
    assert not (root / ".github").exists()


def test_init_none_writes_only_core_files(tmp_path, capsys):
    root = project(tmp_path)
    code, _ = init(root, "--agent", "none", capsys=capsys)
    assert code == 0
    assert not (root / "AGENTS.md").exists()
    assert (root / "laws.lock").exists()


def test_init_unknown_agent_is_a_setup_problem(tmp_path, capsys):
    root = project(tmp_path)
    code, data = init(root, "--agent", "vim", capsys=capsys)
    assert code == 3 and "vim" in data["summary"]
    assert not (root / "laws").exists()


def test_init_without_agents_found_adds_shared_base(tmp_path, capsys):
    root = project(tmp_path, git=False)
    code, data = init(root, capsys=capsys)
    assert code == 0
    assert data["data"]["agents"] == []
    assert (root / "AGENTS.md").exists()
    assert any("--agent claude-code" in line for line in data["lines"])
    assert any("not a git repository" in n for n in data["data"]["notes"])


def test_init_keeps_user_files(tmp_path, capsys):
    root = project(tmp_path)
    (root / "lawkeep.toml").write_text('[permissions]\nadd_law = "ask"\n')
    (root / "laws").mkdir()
    (root / "laws" / "strategies.py").write_text("# mine\n")
    (root / "AGENTS.md").write_text("# Team rules\n")
    code, _ = init(root, "--agent", "none", capsys=capsys)
    assert code == 0
    assert (root / "lawkeep.toml").read_text() == '[permissions]\nadd_law = "ask"\n'
    assert (root / "laws" / "strategies.py").read_text() == "# mine\n"


def test_init_refuses_to_record_an_unrecorded_change(tmp_path, capsys):
    root = project(tmp_path)
    init(root, "--agent", "none", capsys=capsys)
    (root / "laws" / "strategies.py").write_text("# edited outside lawkeep\n")
    (root / "laws" / "drafts").rmdir()
    code, data = init(root, "--agent", "none", capsys=capsys)
    assert code == 2
    assert data["data"]["state"] == "unrecorded"
    assert data["data"]["unrecorded"] == ["laws/strategies.py"]
    assert "accept-unrecorded" in " ".join(data["lines"])
    assert [e.action for e in history.read(root)] == ["init"]  # nothing recorded
    assert not (root / "laws" / "drafts").exists()  # law files untouched


def test_init_does_not_recreate_a_deleted_lock(tmp_path, capsys):
    root = project(tmp_path)
    init(root, "--agent", "none", capsys=capsys)
    (root / "laws.lock").unlink()
    code, data = init(root, "--agent", "none", capsys=capsys)
    assert code == 2 and data["data"]["state"] == "lock_lost"
    assert not (root / "laws.lock").exists()


def test_init_rerun_recreates_missing_folders_without_a_history_entry(tmp_path, capsys):
    root = project(tmp_path)
    init(root, "--agent", "none", capsys=capsys)
    (root / "laws" / "drafts").rmdir()  # not fingerprinted
    code, data = init(root, "--agent", "none", capsys=capsys)
    assert code == 0
    assert (root / "laws" / "drafts").is_dir()
    assert [e.action for e in history.read(root)] == ["init"]


def test_init_completes_a_partial_setup(tmp_path, capsys):
    root = project(tmp_path)
    (root / "lawkeep.toml").write_text("")
    (root / "laws").mkdir()
    (root / "laws" / "history.jsonl").touch()
    # lawkeep.toml and laws/ exist but nothing is locked yet: init locks them
    init(root, "--agent", "none", capsys=capsys)
    assert [e.action for e in history.read(root)] == ["init"]
    assert lock.diff_against_lock(root).is_empty


def test_init_text_output(tmp_path, capsys):
    root = project(tmp_path)
    code = cli.main(["init", "--root", str(root), "--agent", "claude-code"])
    out = capsys.readouterr().out
    assert code == 0
    assert "LAWKEEP IS SET UP" in out and "laws.lock" in out
    assert "Next step: Ask your coding agent to draft laws" in out


def test_init_root_must_exist(tmp_path, capsys):
    code, data = init(tmp_path / "missing", capsys=capsys)
    assert code == 3 and "not a folder" in data["summary"]


@pytest.mark.parametrize("flag", ["--ci", None])
def test_ci_default_depends_on_github_folder(tmp_path, capsys, flag):
    root = project(tmp_path)
    args = ["--agent", "none"] + ([flag] if flag else [])
    init(root, *args, capsys=capsys)
    assert (root / ".github" / "workflows" / "lawkeep.yml").exists() == (flag == "--ci")


def test_workflow_template_only_uses_inputs_the_action_has():
    """The workflow `init` installs passes only inputs that action.yml defines."""
    import re

    import lawkeep

    repo = Path(lawkeep.__file__).resolve().parents[2]
    action = repo / "action.yml"
    if not action.is_file():
        pytest.skip("action.yml is not next to the installed package")
    template = (
        Path(lawkeep.__file__).parent / "adapters" / "templates" / "lawkeep-workflow.yml"
    ).read_text()
    after = template.split("uses: lawkeep/lawkeep@", 1)[1]
    used = re.findall(r"^ {10}([a-z][a-z-]*):", after, flags=re.M)
    assert used, "the template passes no inputs"
    defined = set(re.findall(r"^  ([a-z][a-z-]*):\n    description:", action.read_text(), re.M))
    assert set(used) <= defined, set(used) - defined
