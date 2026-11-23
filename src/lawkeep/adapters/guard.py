"""Decide whether an agent's tool call would change the laws directly.

Used by ``lawkeep hook pre-tool-use`` for every agent (Claude Code, Codex, Cursor, Copilot).
No project code runs here and nothing is written: it only reads the hook payload (and, for
shell commands, the scripts and patch files a command names) and answers "allow", "deny"
(with a plain-English message saying to use ``lawkeep propose``) or "ask" (when the command
actually *runs* ``lawkeep approve``, so the person's yes comes from the agent's own permission
prompt; the question names what would be approved, see ``approve_preview.py``). Text that only
mentions ``lawkeep approve`` (a here-document, a commit message, a string in code) is not asked
about.

Protected paths (relative to the project root):

- everything under ``laws/`` (laws, helpers, ``strategies.py``, ``conftest.py``,
  ``history.jsonl``, ``failing_examples.jsonl``) except ``laws/drafts/``;
- ``laws/drafts/proposals/`` (pending proposals waiting for a person's decision: changing one
  after it was recorded would change what the person is asked to approve);
- ``laws.lock``, ``lawkeep.toml`` and ``.github/workflows/lawkeep.yml``.

``laws/drafts/`` (outside ``proposals/``) stays writable: drafts are ignored by the gate until a
person approves them. A separate law-drafting session started by ``lawkeep draft`` may also
write ``laws/strategies.py``; the launcher marks that session with the environment variable
``LAWKEEP_DRAFTING=1`` (inherited by the agent's hook processes, which the agent itself
cannot change).

How a call is judged:

- edit tools: by their target path (absolute or relative to the call's folder, ``..``
  removed, symlinks followed);
- shell commands: by what they *write to*, worked out on paper by
  :mod:`lawkeep.adapters.writes` (redirections, ``rm``/``mv``/``cp``/``sed -i``/``git
  checkout``/``patch``/..., inline Python and shell code). Reading or naming a protected path
  (``cat laws/x.py``, ``grep -r laws``, ``git commit -m "update laws"``) is allowed. When a
  command writes somewhere the guard cannot see (``eval``, paths built at run time, decoded
  scripts), it is denied only if it plausibly touches the laws: it names a protected path or
  runs decoded code. See ``writes.py`` for exactly what is and is not seen.

This is a speed bump, not a wall: anything it misses still shows up as an *unrecorded law
change* in ``lawkeep check`` / ``lawkeep report``. That is the promise: never silently.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from lawkeep import paths
from lawkeep.adapters import shellwords, writes
from lawkeep.models import as_dict, as_list

#: Set by `lawkeep draft` (agent_launcher.DRAFTING_ENV) for the separate drafting session.
DRAFT_SESSION_ENV = "LAWKEEP_DRAFTING"

#: Tool names (lower-cased) that run shell commands, across agents.
SHELL_TOOLS = frozenset(
    {"bash", "shell", "exec_command", "run_in_terminal", "runterminalcommand", "powershell"}
)
#: Tool names (lower-cased) whose ``command`` is an apply_patch body (Codex).
PATCH_TOOLS = frozenset({"apply_patch", "applypatch"})
#: Keys that hold a single file path in a tool's arguments, across agents.
PATH_KEYS = ("file_path", "filePath", "path", "target_file", "notebook_path", "filename", "file")
PATH_LIST_KEYS = ("paths", "files", "file_paths")
#: Protected folders a recursive delete or move must not take away with it.
_PROTECTED_DIRS = (paths.LAWS_DIRNAME, f"{paths.LAWS_DIRNAME}/{paths.DRAFTS_DIRNAME}/proposals")


@dataclass
class Decision:
    """What the hook should tell the agent."""

    action: str = "allow"  # "allow" | "deny" | "ask"
    message: str = ""  # plain English, shown to the agent (deny) or the person (ask)
    paths: list[str] = field(default_factory=list[str])  # protected paths involved (relative)
    root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


# ---------------------------------------------------------------------------------------------
# Paths


def _resolve(path: str, cwd: Path) -> Path:
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        p = cwd / p
    return Path(os.path.normpath(str(p)))


def protected_rel(path: str | os.PathLike[str], cwd: str | os.PathLike[str] | None = None):
    """``(root, relpath)`` when ``path`` is a protected lawkeep file, else ``None``.

    The path is made absolute against ``cwd`` with ``..`` removed, and judged both as written
    and with symlinks followed (``src/r.py`` linking to ``laws/refunds.py`` is protected). The
    project root is found from the file's own location, so this works whatever the agent's
    current folder is.
    """
    cwd_path = Path(cwd) if cwd else Path.cwd()
    target = _resolve(str(path), cwd_path)
    try:
        real = Path(os.path.realpath(target))
    except (OSError, ValueError):
        real = target
    for candidate in dict.fromkeys([target, real]):
        found = _protected_rel(candidate)
        if found:
            return found
    return None


def _protected_rel(target: Path) -> tuple[Path, str] | None:
    root = paths.find_root(target)
    if root is None:
        return None
    try:
        rel = target.relative_to(Path(os.path.normpath(str(root))))
    except ValueError:
        try:
            rel = target.resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            return None
    parts = rel.parts
    if not parts:
        return None
    relstr = "/".join(parts)
    if relstr in (paths.LOCK_FILENAME, paths.CONFIG_FILENAME, ".github/workflows/lawkeep.yml"):
        return root, relstr
    if parts[0] != paths.LAWS_DIRNAME:
        return None
    if len(parts) == 1:  # the laws/ folder itself (rm -r laws, mv laws ...)
        return root, relstr
    draft_session = os.environ.get(DRAFT_SESSION_ENV, "") not in ("", "0")
    if parts[1] == paths.DRAFTS_DIRNAME:
        if len(parts) >= 3 and parts[2] == "proposals":
            return root, relstr
        return None
    if draft_session and relstr == f"{paths.LAWS_DIRNAME}/{paths.STRATEGIES_FILENAME}":
        return None
    return root, relstr


# ---------------------------------------------------------------------------------------------
# Payload parsing


def _as_dict(value: object) -> dict[str, Any]:
    """A dict, or a JSON string holding one (Copilot sends ``toolArgs`` as text); else ``{}``."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return as_dict(value)


@dataclass
class ToolCall:
    """A tool call normalised from any agent's hook payload."""

    tool: str = ""
    file_paths: list[str] = field(default_factory=list[str])
    command: str | None = None  # shell command text
    patch: str | None = None  # Codex apply_patch body
    cwd: str | None = None


def parse_payload(payload: dict[str, Any]) -> ToolCall:
    """Normalise Claude Code / Codex / Cursor / Copilot hook input into a :class:`ToolCall`.

    - Claude Code and Codex: ``tool_name``, ``tool_input``, ``cwd``.
    - Cursor ``preToolUse``: ``tool_name``, ``tool_input`` (``command``, ``working_directory``);
      Cursor ``beforeShellExecution``: top-level ``command`` and ``cwd``.
    - Copilot: ``toolName``, ``toolArgs`` (object or JSON string), ``cwd``; its VS Code
      compatible variant uses ``tool_name`` / ``tool_input``.
    """
    tool = str(payload.get("tool_name") or payload.get("toolName") or "")
    args = _as_dict(payload.get("tool_input", payload.get("toolArgs")))
    cwd = payload.get("cwd") or args.get("working_directory") or args.get("cwd")
    call = ToolCall(tool=tool, cwd=str(cwd) if cwd else None)
    low = tool.lower()
    if not tool and isinstance(payload.get("command"), str):  # Cursor beforeShellExecution
        call.tool = "Shell"
        call.command = payload["command"]
        return call
    command: object = args.get("command", args.get("cmd"))
    if isinstance(command, list):
        command = shlex.join(str(c) for c in cast("list[object]", command))
    if low in PATCH_TOOLS:
        call.patch = str(command or args.get("patch") or args.get("input") or "")
        return call
    if low in SHELL_TOOLS:
        call.command = str(command or "")
        return call
    for key in PATH_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            call.file_paths.append(value)
    for key in PATH_LIST_KEYS:
        call.file_paths.extend(v for v in as_list(args.get(key)) if isinstance(v, str) and v)
    for item in as_list(args.get("edits")):  # some agents nest a path per edit
        edit = as_dict(item)
        for key in PATH_KEYS:
            value = edit.get(key)
            if isinstance(value, str):
                call.file_paths.append(value)
    return call


def patch_paths(patch: str) -> list[str]:
    """Files touched by a Codex ``apply_patch`` body (Add/Update/Delete File, Move to)."""
    out: list[str] = []
    for line in patch.splitlines():
        m = re.match(r"\*\*\*\s+(?:Add|Update|Delete) File:\s*(.+?)\s*$", line) or re.match(
            r"\*\*\*\s+Move to:\s*(.+?)\s*$", line
        )
        if m:
            out.append(m.group(1))
    return out


# ---------------------------------------------------------------------------------------------
# Shell commands (the analysis itself lives in writes.py / pywrites.py / shellwords.py)


def segments(command: str) -> list[list[str]]:
    """The simple commands of a shell command line as lists of literal words (best effort;
    words with expansions keep only their literal characters). Nested ``$(...)`` commands
    are included. Unparsable text gives a rough whitespace split."""
    try:
        commands = shellwords.walk(shellwords.parse(command))
    except shellwords.Incomplete:
        return [command.split()] if command.split() else []
    return [[w.static_text() for w in c.words] for c in commands if c.words]


def lawkeep_subcommand(words: list[str]) -> str | None:
    """``approve`` for ``lawkeep approve ...`` / ``uv run lawkeep approve`` / ``python -m lawkeep approve``."""
    w = list(words)
    while w and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]) or w[0] in ("sudo", "env", "command")):
        w = w[1:]
    while w and w[0] in ("uv", "uvx", "pipx", "poetry", "pdm", "hatch", "rye"):
        w = w[1:]
        while w and (w[0] in ("run", "exec", "--") or w[0].startswith("-")):
            w = w[1:]
    if (
        len(w) >= 3
        and re.match(r"^(.*/)?python[0-9.]*$", w[0])
        and w[1] == "-m"
        and w[2] == "lawkeep"
    ):
        w = w[2:]
    if w and re.match(r"^(.*/)?lawkeep$", w[0]):
        rest: list[str] = []
        skip = False
        for x in w[1:]:
            if skip:
                skip = False
            elif x == "--root":
                skip = True
            elif not x.startswith("-"):
                rest.append(x)
        return rest[0] if rest else ""
    return None


def _runs_approve(words: list[str]) -> bool:
    """A simple command that is ``lawkeep approve`` (not ``lawkeep approve --help``)."""
    return lawkeep_subcommand(words) == "approve" and not ({"--help", "-h"} & set(words))


def is_approval_command(command: str) -> bool:
    """True when the shell command *runs* ``lawkeep approve`` (a person's decision), also when
    it is wrapped (``uv run``, ``sh -c``, ``xargs``, ``python -c "...cli.main(['approve'])"``,
    ``subprocess``) or writes history entries through lawkeep's Python API
    (``history.record_change``). Text that only mentions it (``echo "lawkeep approve"``, a
    here-document body, a commit message) does not count, nor does ``--help``."""
    return writes.analyse(command, None).approval or any(
        _runs_approve(seg) for seg in segments(command)
    )


def written_paths(command: str, cwd: str | os.PathLike[str] | None = None) -> list[str]:
    """Paths a shell command would create, change or delete, as far as the guard can see
    (see :mod:`lawkeep.adapters.writes`). With ``cwd``, relative paths are made absolute
    (following ``cd``); without it, only absolute paths are returned."""
    return writes.analyse(command, cwd).targets


# ---------------------------------------------------------------------------------------------
# Decision


def deny_message(rels: list[str]) -> str:
    shown = ", ".join(rels[:3]) + (" ..." if len(rels) > 3 else "")
    only_lawkeep = all(r in (paths.LOCK_FILENAME,) or r.endswith(".jsonl") for r in rels)
    if only_lawkeep:
        return (
            f"lawkeep blocked this: {shown} is written only by lawkeep, never by hand. "
            "Use `lawkeep check`, `lawkeep propose` or `lawkeep approve` (the person decides) "
            "instead. If you think something is wrong with it, stop and tell the person."
        )
    return (
        f"lawkeep blocked this: {shown} holds this project's laws (rules the code must always "
        "follow), so it cannot be changed directly; that would be an unrecorded law change. "
        "What to do: if the code breaks a law, fix the code and run `lawkeep check`. To change "
        "a law, write the complete new version to a file under laws/drafts/ (for example "
        "laws/drafts/refunds_v2.py) and run "
        '`lawkeep propose <LAW_ID> --file laws/drafts/refunds_v2.py --reason "<why>"`. '
        "Stricter changes may go in right away; a change that weakens a law waits for the "
        "person's yes. If a law conflicts with your task, stop and ask the person - that is a "
        "successful outcome."
    )


#: The question when lawkeep cannot work out what would be approved (see ``approve_message``).
APPROVE_MESSAGE = (
    "lawkeep: your coding agent wants to record YOUR approval of a law change "
    "(`lawkeep approve`). Say yes only if you asked for this and have read the law and its "
    "examples. Not sure? Say no — nothing is lost; you can approve later yourself with "
    "`lawkeep approve`."
)


def approve_message(found: writes.Findings, cwd: Path) -> str:
    """The question for the person: what the command's ``lawkeep approve`` would decide."""
    try:
        from lawkeep.adapters import approve_preview

        return approve_preview.describe(found.approve_runs, cwd)
    except Exception:  # pragma: no cover - defensive: the question must always be asked
        return APPROVE_MESSAGE


def unsure_message(reasons: list[str], mentions: list[str]) -> str:
    named = ", ".join(mentions[:3]) + (" ..." if len(mentions) > 3 else "")
    why = "; ".join(reasons[:2])
    return (
        f"lawkeep blocked this: it cannot tell what this command writes ({why})"
        + (f", and the command names {named}" if named else ", and it runs decoded code")
        + ", so it may change this project's laws (laws/, laws.lock, lawkeep.toml), which "
        "cannot be changed directly. If you are not changing laws, write the command so the "
        "files it writes are plain to see (no eval, no paths built at run time, no encoded "
        "scripts), or use an edit tool. To change a law, write the complete new version to a "
        "file under laws/drafts/ and run "
        '`lawkeep propose <LAW_ID> --file laws/drafts/<file>.py --reason "<why>"`; a change '
        "that weakens a law waits for the person's yes. If a law conflicts with your task, "
        "stop and ask the person - that is a successful outcome."
    )


def _hits(cands: list[str], cwd: Path) -> tuple[list[str], str | None]:
    hits: list[str] = []
    root: str | None = None
    for cand in cands:
        if not cand:
            continue
        found = protected_rel(cand, cwd)
        if found:
            root = str(found[0])
            if found[1] not in hits:
                hits.append(found[1])
    return hits, root


def _contains_protected(path: str, cwd: Path) -> tuple[str, str] | None:
    """``(root, "laws")`` (or ``"laws/drafts/proposals"``) when ``path`` is a folder that
    holds protected files: the project root, a folder above it, or ``laws/drafts``. Removing
    or moving it (``rm -r``, ``mv``) takes the laws with it."""
    target = Path(os.path.normpath(path))
    for start in (target, cwd):
        root = paths.find_root(start)
        if root is None:
            continue
        for r in dict.fromkeys([Path(os.path.normpath(str(root))), root.resolve()]):
            for rel in _PROTECTED_DIRS:
                folder = r / rel
                if target in folder.parents and folder.is_dir():
                    return str(root), rel
    return None


def decide(payload: dict[str, Any]) -> Decision:
    """The decision for one hook payload. Never raises on odd input (returns allow).

    - Edit tools (Edit, Write, MultiEdit, NotebookEdit, apply_patch ...): the target path
      decides (made absolute against the call's folder, ``..`` removed, symlinks followed).
    - Shell commands: what the command *writes to* decides (:mod:`lawkeep.adapters.writes`),
      never a mere mention: ``cat laws/x.py``, ``grep -r laws``, ``git commit -m "laws"`` and
      ``lawkeep ...`` are allowed. A write to a protected path is denied. A write the guard
      cannot see (``eval``, paths built at run time, decoded scripts ...) is denied only when
      it plausibly touches the laws: the command names a protected path, or runs decoded
      code; otherwise it is allowed (``lawkeep check`` still flags anything that changed).
    - a command that runs ``lawkeep approve`` (also wrapped) gets "ask": the person confirms
      it, and the question lists what it would decide. Mentions in text are not asked about.
    """
    try:
        call = parse_payload(as_dict(payload))  # hook input is untrusted JSON
    except Exception:  # pragma: no cover - defensive: a broken payload must not break the agent
        return Decision()
    cwd = Path(call.cwd) if call.cwd else Path.cwd()
    candidates = list(call.file_paths)
    if call.patch:
        candidates.extend(patch_paths(call.patch))
    hits, root = _hits(candidates, cwd)
    found = None
    if call.command:
        try:
            found = writes.analyse(call.command, cwd)
        except Exception:  # pragma: no cover - defensive: fall back to a careful text check
            found = writes.Findings(
                unsure=["the command could not be analysed"],
                mentions=writes.bare_mentions(call.command),
                approval=any(_runs_approve(seg) for seg in segments(call.command)),
            )
        more, more_root = _hits(found.targets, cwd)
        for h in more:
            if h not in hits:
                hits.append(h)
        root = root or more_root
        for r in found.recursive:
            whole = _contains_protected(r, cwd)
            if whole and whole[1] not in hits:
                hits.append(whole[1])
                root = root or whole[0]
    if hits:
        return Decision("deny", deny_message(hits), hits, root)
    if found is not None and found.unsure and (found.mentions or found.forced):
        root_path = paths.find_root(cwd)
        return Decision(
            "deny",
            unsure_message(found.unsure, found.mentions),
            list(found.mentions),
            str(root_path) if root_path else None,
        )
    if found is not None and found.approval:
        return Decision("ask", approve_message(found, cwd))
    return Decision()
