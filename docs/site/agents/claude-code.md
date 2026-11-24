# Claude Code

```bash
lawkeep init --agent claude-code
```

**Status: run for real.** Claude Code is the only agent lawkeep has been tried with end to end.

## What `init` sets up

| File | What lawkeep adds |
| --- | --- |
| `.claude/settings.json` | a `PreToolUse` hook on `Edit`, `Write`, `MultiEdit`, `NotebookEdit` and `Bash` (`lawkeep hook pre-tool-use --agent claude-code`); a `SessionStart` hook (`lawkeep hook session-start`); `permissions.ask` rules for `lawkeep approve` (also through `uv run`, `uvx`, `python -m` and `.venv/bin/lawkeep`) |
| `.mcp.json` | the `lawkeep` MCP server (Claude Code asks you once before using a project server) |
| `CLAUDE.md` | `@AGENTS.md`, so Claude reads the shared lawkeep instructions |
| `AGENTS.md` | the lawkeep section (see [AI tools](index.md#what-every-agent-is-told)) |

Everything is merged into existing files; nothing is overwritten.

## How it behaves

- Claude's direct edits to `laws/`, `laws.lock`, `lawkeep.toml` or the lawkeep workflow are denied
  with a message to use `lawkeep propose`. Shell commands are judged by what they write to.
- When Claude runs `lawkeep approve`, Claude Code's own permission prompt asks you, with one plain
  line per item it would decide ("Loosen “…” → “…” (looser: protects less)").
- At session start, Claude is reminded of the rules, the waiting count and whether lawkeep thinks a
  person is there. lawkeep reads two Claude Code variables for that guess
  (`CLAUDE_CODE_SESSION_ATTENDED`, `CLAUDE_CODE_ENTRYPOINT`); they were seen in Claude Code 2.1, not
  taken from a documented contract. `claude -p` runs read as "nobody there".

## `lawkeep draft`

Default command: `claude -p --permission-mode acceptEdits {prompt}`.

## Turning the hooks off

`lawkeep init --agent claude-code --no-hooks` installs only the instructions and the MCP server.
