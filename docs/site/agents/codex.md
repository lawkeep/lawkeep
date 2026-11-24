# OpenAI Codex

```bash
lawkeep init --agent codex
```

**Status: not run for real.** Set up according to Codex's documentation (checked 2026-11-21) and
tested with simulated hook messages only.

## What `init` sets up

| File | What lawkeep adds |
| --- | --- |
| `AGENTS.md` | the lawkeep section (Codex reads `AGENTS.md` natively) |
| `.codex/hooks.json` | a `PreToolUse` hook on `apply_patch`, `Edit`, `Write` and `Bash`, and a `SessionStart` hook |
| `.codex/rules/lawkeep.rules` | rules that make Codex ask you before it runs `lawkeep approve` (also through `uv run` and `python -m`) |
| `.codex/config.toml` | the `lawkeep` MCP server under `[mcp_servers.lawkeep]` |

## Things to know

- Codex loads project hooks and the project config only when the project's `.codex/` folder is
  **trusted**, and new hooks must be reviewed with `/hooks`.
- Codex hooks cannot "ask", only allow or deny. So your yes for `lawkeep approve` comes from the
  rules file, which shows a fixed text ("lawkeep: your coding agent wants to record YOUR approval of a
  law change ..."), not the list of items.
- lawkeep cannot tell whether a person is chatting with Codex, so Codex sessions read as
  `person_present: false`. The instructions tell Codex that a person chatting with it counts as
  present.

## `lawkeep draft`

Default command: `codex exec --sandbox workspace-write {prompt}`.
