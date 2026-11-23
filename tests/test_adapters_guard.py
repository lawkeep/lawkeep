"""Workstream E: the guard that turns direct law edits into "use lawkeep propose"."""

from __future__ import annotations

from pathlib import Path

import pytest

from lawkeep.adapters import guard


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    (root / "laws" / "drafts" / "proposals" / "h-1").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "lawkeep.toml").write_text("", encoding="utf-8")
    (root / "laws" / "refunds.py").write_text("# law\n", encoding="utf-8")
    return root


def edit(root: Path, path: str, tool: str = "Edit", cwd: Path | None = None) -> dict:
    return {
        "tool_name": tool,
        "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"},
        "cwd": str(cwd or root),
    }


def bash(root: Path, command: str, cwd: Path | None = None) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or root)}


@pytest.mark.parametrize(
    "rel",
    [
        "laws/refunds.py",
        "laws/new_law.py",
        "laws/strategies.py",
        "laws/conftest.py",
        "laws/history.jsonl",
        "laws/failing_examples.jsonl",
        "laws/drafts/proposals/h-1/refunds.py",
        "laws.lock",
        "lawkeep.toml",
    ],
)
def test_edit_to_protected_path_is_denied(tmp_path, rel):
    root = make_project(tmp_path)
    for path in (str(root / rel), rel):
        d = guard.decide(edit(root, path))
        assert d.action == "deny", (path, d)
        assert d.paths == [rel]
        assert "lawkeep" in d.message


@pytest.mark.parametrize(
    "rel", ["src/refunds.py", "README.md", "laws/drafts/refunds_v2.py", "lawsuit.py"]
)
def test_edit_elsewhere_is_allowed(tmp_path, rel):
    root = make_project(tmp_path)
    assert guard.decide(edit(root, str(root / rel))).action == "allow"
    assert guard.decide(edit(root, rel, tool="Write")).action == "allow"


def test_deny_message_tells_agent_to_use_propose(tmp_path):
    root = make_project(tmp_path)
    d = guard.decide(edit(root, "laws/refunds.py"))
    assert "lawkeep propose" in d.message and "stop and ask the person" in d.message
    lock = guard.decide(edit(root, "laws.lock"))
    assert "written only by lawkeep" in lock.message


def test_relative_path_from_a_subfolder(tmp_path):
    root = make_project(tmp_path)
    assert guard.decide(edit(root, "../laws/refunds.py", cwd=root / "src")).action == "deny"
    # src/laws/x.py is not a law file
    assert guard.decide(edit(root, "laws/x.py", cwd=root / "src")).action == "allow"


def test_not_a_lawkeep_project_is_allowed(tmp_path):
    other = tmp_path / "plain"
    other.mkdir()
    assert guard.decide(edit(other, str(other / "laws.lock"))).action == "allow"


def test_draft_session_may_write_strategies_but_not_laws(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    monkeypatch.setenv(guard.DRAFT_SESSION_ENV, "1")
    assert guard.decide(edit(root, "laws/strategies.py")).action == "allow"
    assert guard.decide(edit(root, "laws/refunds.py")).action == "deny"


def test_multiedit_and_notebook_paths(tmp_path):
    root = make_project(tmp_path)
    nb = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": "laws/x.ipynb"},
        "cwd": str(root),
    }
    assert guard.decide(nb).action == "deny"
    multi = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "laws/refunds.py",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
        "cwd": str(root),
    }
    assert guard.decide(multi).action == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "echo 'x' > laws/refunds.py",
        "echo x >> laws/history.jsonl",
        "cat new.py>laws/refunds.py",
        "printf x | tee laws/refunds.py",
        "cp /tmp/weak.py laws/refunds.py",
        "mv laws/refunds.py /tmp/",
        "rm laws/refunds.py",
        "rm -rf laws",
        "sed -i 's/<=/</' laws/refunds.py",
        "sed -i.bak 's/a/b/' laws/refunds.py",
        "perl -pi -e 's/a/b/' laws/refunds.py",
        "git checkout -- laws/refunds.py",
        "git restore laws/refunds.py",
        "truncate -s 0 laws.lock",
        "touch laws/conftest.py",
        "find laws -name '*.py' -delete",
        "python -c \"open('laws/refunds.py','w').write('')\"",
        "python3 - <<'EOF'\nopen('laws/refunds.py', 'w').write('x')\nEOF",
        "cd src && echo x > ../laws/refunds.py",
        "true; echo x > lawkeep.toml",
        "FOO=1 sudo cp a.py laws/refunds.py",
        "lawkeep check --json > laws/out.json",
    ],
)
def test_bash_writes_into_laws_are_denied(tmp_path, command):
    root = make_project(tmp_path)
    d = guard.decide(bash(root, command))
    assert d.action == "deny", (command, d)


@pytest.mark.parametrize(
    "command",
    [
        "cat laws/refunds.py",
        "grep -n refund laws/*.py",
        "cp laws/refunds.py laws/drafts/refunds_v2.py",
        "pytest tests/",
        "git diff laws/",
        "git add laws/refunds.py",
        "lawkeep check --json",
        "lawkeep propose refunds.refund_is_capped --file laws/drafts/r.py --reason 'tiny refunds'",
        "uv run lawkeep check",
        "echo x > src/refunds.py",
        "cd laws && cat refunds.py",
        "cd src && echo x > laws/notes.txt",
        "cat <<EOF > notes.md\nsee laws/refunds.py\nEOF",
        "python -c 'print(1)'",
    ],
)
def test_harmless_bash_is_allowed(tmp_path, command):
    root = make_project(tmp_path)
    assert guard.decide(bash(root, command)).action == "allow", command


@pytest.mark.parametrize(
    "command",
    [
        "lawkeep approve h-1a2b3c4d --yes",
        "uv run lawkeep approve refunds.refund_is_capped --yes",
        "python -m lawkeep approve --accept-unrecorded --yes",
        "cd /x && .venv/bin/lawkeep approve --no",
        "LAWKEEP_ROOT=. lawkeep --json approve h-1",
    ],
)
def test_approve_asks_the_person(tmp_path, command):
    root = make_project(tmp_path)
    d = guard.decide(bash(root, command))
    assert d.action == "ask", command
    assert "YOUR" in d.message


def test_codex_apply_patch(tmp_path):
    root = make_project(tmp_path)
    patch = "*** Begin Patch\n*** Update File: laws/refunds.py\n@@\n-a\n+b\n*** End Patch\n"
    payload = {"tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(root)}
    assert guard.decide(payload).action == "deny"
    ok = patch.replace("laws/refunds.py", "src/refunds.py")
    payload["tool_input"]["command"] = ok
    assert guard.decide(payload).action == "allow"
    move = "*** Begin Patch\n*** Update File: src/a.py\n*** Move to: laws/a.py\n*** End Patch"
    assert guard.patch_paths(move) == ["src/a.py", "laws/a.py"]


def test_copilot_payload_with_string_args(tmp_path):
    root = make_project(tmp_path)
    payload = {"toolName": "edit", "toolArgs": '{"path": "laws/refunds.py"}', "cwd": str(root)}
    assert guard.decide(payload).action == "deny"
    payload = {"toolName": "bash", "toolArgs": {"command": "rm laws.lock"}, "cwd": str(root)}
    assert guard.decide(payload).action == "deny"
    payload = {"toolName": "create", "toolArgs": {"path": "src/new.py"}, "cwd": str(root)}
    assert guard.decide(payload).action == "allow"


def test_cursor_payloads(tmp_path):
    root = make_project(tmp_path)
    before_shell = {"command": "echo x > laws/refunds.py", "cwd": str(root)}
    assert guard.decide(before_shell).action == "deny"
    pre_tool = {
        "tool_name": "Shell",
        "tool_input": {"command": "rm laws/refunds.py", "working_directory": str(root)},
    }
    assert guard.decide(pre_tool).action == "deny"
    write = {"tool_name": "Write", "tool_input": {"target_file": str(root / "laws/x.py")}}
    assert guard.decide(write).action == "deny"


@pytest.mark.parametrize(
    "payload", [{}, {"tool_name": "Read"}, {"tool_name": 3, "tool_input": "x"}, []]
)
def test_odd_payloads_are_allowed(payload):
    assert guard.decide(payload).action == "allow"


# Integration: commands that only *mention* laws must not be stopped (false positives seen
# during the build), while inline code that writes a law path still is.
@pytest.mark.parametrize(
    "command",
    [
        "python3 - <<'PY'\ns = open('src/r.py').read().replace('the laws hold', 'ok')\n"
        "open('src/r.py', 'w').write(s)\nPY",
        "python -c \"open('src/r.py', 'w').write('laws are rules')\"",
        "sed -i 's/laws/rules/' src/r.py",
        "git commit -m 'explain the laws'",
    ],
)
def test_mentioning_laws_is_allowed(tmp_path, command):
    root = make_project(tmp_path)
    assert guard.decide(bash(root, command)).action == "allow"


@pytest.mark.parametrize(
    "command",
    [
        "python -c \"open('laws/refunds.py', 'w').write('')\"",
        "python3 - <<'PY'\nopen('laws/refunds.py', 'w').write('x')\nPY",
        "bash -c 'echo x > laws/refunds.py'",
        'sh -c "rm lawkeep.toml"',
    ],
)
def test_inline_code_writing_laws_is_denied(tmp_path, command):
    root = make_project(tmp_path)
    assert guard.decide(bash(root, command)).action == "deny"


def test_drafting_session_env_matches_launcher():
    from lawkeep import agent_launcher

    assert guard.DRAFT_SESSION_ENV == agent_launcher.DRAFTING_ENV
