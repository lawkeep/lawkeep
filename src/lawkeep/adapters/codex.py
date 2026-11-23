"""OpenAI Codex (CLI / IDE) adapter.

Formats (checked 2026-11-21 against the official docs; Codex moved its docs from
developers.openai.com/codex to learn.chatgpt.com/docs during 2026):

- Instructions: Codex reads ``AGENTS.md`` natively, so the shared base covers it.
- Hooks: ``<repo>/.codex/hooks.json`` ``{"hooks": {"PreToolUse": [{"matcher": "...",
  "hooks": [{"type": "command", "command": "...", "timeout": 30}]}]}}``. PreToolUse sees
  ``tool_name`` ``Bash`` / ``apply_patch`` (file edits; matcher aliases ``Edit``/``Write``) /
  MCP tools, with ``tool_input.command`` holding the shell command or the patch body. Deny with
  ``hookSpecificOutput.permissionDecision = "deny"`` + ``permissionDecisionReason``. "ask" is
  NOT supported for PreToolUse. Project hooks load only when the project's ``.codex/`` layer is
  trusted, and new hooks must be reviewed with ``/hooks``.
  https://learn.chatgpt.com/docs/hooks (formerly https://developers.openai.com/codex/hooks)
- Approval prompts for specific commands: Rules (experimental) in ``<repo>/.codex/rules/*.rules``,
  ``prefix_rule(pattern=[...], decision="prompt", justification=..., match=[...], not_match=[...])``.
  https://learn.chatgpt.com/docs/agent-configuration/rules
- MCP: ``[mcp_servers.<name>]`` with ``command`` / ``args`` in ``.codex/config.toml`` (project
  file honoured only for trusted projects). https://developers.openai.com/codex/mcp

What this adapter installs: the PreToolUse + SessionStart hooks, a rules file that makes
``lawkeep approve`` prompt the person, and the MCP server entry. Because Codex hooks cannot
"ask", the person's yes for ``lawkeep approve`` comes from the rules file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from lawkeep.adapters import base
from lawkeep.models import as_dict, as_list

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

NAME = "codex"
ROOT_EXPR = "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
EDIT_MATCHER = "apply_patch|Edit|Write|Bash"

#: Shown to the person in Codex's prompt (plain words; Codex hooks cannot list the items).
JUSTIFICATION_TEXT = (
    "lawkeep: your coding agent wants to record YOUR approval of a law change. Say yes only "
    "if you asked for this and have read the law. Not sure? Say no - you can approve later "
    "yourself with lawkeep approve."
)
JUSTIFICATION = '"' + JUSTIFICATION_TEXT + '"'

RULES = f"""\
# lawkeep: `lawkeep approve` records YOUR decision on a law change, so Codex asks you
# before running it. Added by `lawkeep init`.
# Format: https://learn.chatgpt.com/docs/agent-configuration/rules
prefix_rule(
    pattern = ["lawkeep", "approve"],
    decision = "prompt",
    justification = {JUSTIFICATION},
    match = ["lawkeep approve h-1a2b3c4d --yes"],
    not_match = ["lawkeep check"],
)
prefix_rule(
    pattern = ["uv", "run", "lawkeep", "approve"],
    decision = "prompt",
    justification = {JUSTIFICATION},
)
prefix_rule(
    pattern = [["python", "python3"], "-m", "lawkeep", "approve"],
    decision = "prompt",
    justification = {JUSTIFICATION},
)
"""


def _mcp_toml() -> str:
    import json as _json

    script = base.mcp_launch_script(ROOT_EXPR)
    return (
        "\n# lawkeep MCP server (check, propose, report, list_laws). Added by `lawkeep init`.\n"
        "# Starts lawkeep from PATH, else from the project's .venv.\n"
        "[mcp_servers.lawkeep]\n"
        'command = "sh"\n'
        f'args = ["-c", {_json.dumps(script)}]\n'
    )


def hook_command(event: str) -> str:
    return base.launcher(f"hook {event} --agent {NAME}", ROOT_EXPR)


def _has(groups: list[Any], event: str) -> bool:
    return any(
        f"lawkeep hook {event}" in str(as_dict(h).get("command", ""))
        for g in groups
        for h in as_list(as_dict(g).get("hooks"))
    )


def hooks_update(data: dict[str, Any]) -> None:
    all_hooks = base.ensure_dict(data, "hooks")
    for event, matcher, name in (
        ("PreToolUse", EDIT_MATCHER, "pre-tool-use"),
        ("SessionStart", "startup|resume|clear", "session-start"),
    ):
        groups = base.ensure_list(all_hooks, event)
        if not _has(groups, name):
            groups.append(
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": hook_command(name), "timeout": 30}],
                }
            )


class CodexAdapter:
    name = NAME

    def detect(self, root: Path) -> bool:
        return (root / ".codex").is_dir()

    def install(self, root: Path, *, hooks: bool = True) -> base.InstallResult:
        result = base.InstallResult(agent=NAME)
        if hooks:
            base.merge_json(root, root / ".codex" / "hooks.json", hooks_update, result)
        base.write_if_missing(root, root / ".codex" / "rules" / "lawkeep.rules", RULES, result)
        self._mcp(root, result)
        result.notes.append(
            "Codex reads project settings in .codex/ only after you trust the project; then "
            "review and trust the new lawkeep hooks with /hooks in Codex. Codex hooks cannot "
            "ask you directly, so `lawkeep approve` asks through .codex/rules/lawkeep.rules."
        )
        return result

    @staticmethod
    def _mcp(root: Path, result: base.InstallResult) -> None:
        path = root / ".codex" / "config.toml"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            result.warnings.append(
                f".codex/config.toml could not be read ({exc}); lawkeep did not change it. Add "
                'the MCP server yourself: [mcp_servers.lawkeep] command = "lawkeep" args = ["mcp"]'
            )
            return
        servers = data.get("mcp_servers")
        if isinstance(servers, dict) and base.MCP_SERVER_NAME in servers:
            return
        sep = "" if (not text or text.endswith("\n")) else "\n"
        base.write_text(path, text + sep + (_mcp_toml() if text else _mcp_toml().lstrip("\n")))
        result.changed(base.rel(root, path))


ADAPTER = CodexAdapter()
