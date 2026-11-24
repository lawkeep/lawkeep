# AI tools

lawkeep works with any coding agent through a shared base, and has richer adapters for four agents:

| Agent | `lawkeep init --agent` | Hooks | "ask before approve" | MCP | Run for real? |
| --- | --- | --- | --- | --- | --- |
| [Claude Code](claude-code.md) | `claude-code` | yes | permission rule + hook | `.mcp.json` | **yes** |
| [OpenAI Codex](codex.md) | `codex` | yes | rules file | `.codex/config.toml` | no, checked against its docs |
| [Cursor](cursor.md) | `cursor` | yes | shell hook | `.cursor/mcp.json` | no, checked against its docs |
| [GitHub Copilot](copilot.md) | `copilot` | yes (CLI, cloud agent) | hook | `.mcp.json` | no, checked against its docs |
| any other agent | `other` | no | your agent's own prompt | configure it yourself | — |

`lawkeep init --agent all` sets up all four. Running `init` again changes nothing that is already
set up; it merges into your files and never overwrites them.

:::{warning}
Only Claude Code has been run for real with lawkeep. The Codex, Cursor and Copilot adapters follow
those agents' documentation (checked on 2026-11-21) and were tested with simulated hook messages,
never inside the running agent. If you try one, please
[report what happened](https://github.com/lawkeep/lawkeep/issues).
:::

## The shared base (every agent)

- **Instructions in `AGENTS.md`.** `init` adds a lawkeep section (between `<!-- lawkeep:begin -->` and
  `<!-- lawkeep:end -->`). Codex, Cursor, Copilot and many other agents read `AGENTS.md`; Claude Code
  reads it through `@AGENTS.md` in `CLAUDE.md`.
- **The `lawkeep` command**, with `--json` on every command for machine-readable results.
- **The [MCP server](mcp.md)** (`lawkeep mcp`), so agents can call `check`, `propose`, `report` and
  `list_laws` as tools.
- **A git pre-commit hook** that shows law changes made outside lawkeep.

## What the richer adapters add

- **A guard before each tool call.** Direct edits to `laws/`, `laws.lock`, `lawkeep.toml` or the
  lawkeep workflow are refused, with a message telling the agent to use `lawkeep propose` instead.
  Shell commands are judged by what they write to, so reading laws is fine. The guard is a speed
  bump, not a wall: anything it misses still shows up as an unrecorded law change in `lawkeep check`.
- **Your yes for `lawkeep approve` comes from the agent's own permission prompt.** When an agent tries
  to run `lawkeep approve`, the agent asks you first and shows, in plain words, what would be decided.
- **Session start and end.** At the start of a session the agent is reminded of the rules, of how many
  things wait for your decision, and of lawkeep's guess whether a person is there.

## `lawkeep draft` and your agent

`lawkeep draft` starts a separate, non-interactive session of your agent to write draft laws. The
command it uses is set in `lawkeep.toml`:

```toml
[agent]
name = "claude-code"     # claude-code | codex | cursor | copilot | other
# command = "..."        # your own command; {prompt} or {prompt_file} is replaced, else stdin
timeout_seconds = 900
```

The built-in commands per agent are on each agent's page. Use `lawkeep draft --dry-run` to see the
message lawkeep would send without starting anything.

## What every agent is told

This is the text `lawkeep init` puts into `AGENTS.md` (and into Cursor's rule file and Copilot's
instructions):

```{include} ../../../src/lawkeep/adapters/templates/agents_snippet.md
:heading-offset: 1
```

```{toctree}
:hidden:

claude-code
codex
cursor
copilot
mcp
```
