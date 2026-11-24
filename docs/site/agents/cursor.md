# Cursor

```bash
lawkeep init --agent cursor
```

**Status: not run for real.** Set up according to Cursor's documentation and forum (checked
2026-11-21) and tested with simulated hook messages only.

## What `init` sets up

| File | What lawkeep adds |
| --- | --- |
| `.cursor/rules/lawkeep.mdc` | the lawkeep instructions as a project rule (Cursor also reads `AGENTS.md`) |
| `.cursor/hooks.json` | a `preToolUse` hook for edits, a `beforeShellExecution` hook, and a `sessionStart` hook |
| `.cursor/mcp.json` | the `lawkeep` MCP server |
| `AGENTS.md` | the lawkeep section |

## Things to know

- Cursor has no per-command "ask" rules in project settings, so your yes for `lawkeep approve` comes
  from the `beforeShellExecution` hook answering "ask".
- Not verified: which field holds the file path in Cursor's `preToolUse` message for writes (the docs
  only show a shell example). lawkeep's hook looks for every common field name. Forum reports say
  hooks sometimes do not fire; anything missed still shows up as an unrecorded law change.
- Cursor sessions read as `person_present: false` (see [Waiting list and person present](../concepts/waiting-list.md)).

## `lawkeep draft`

Default command: `cursor-agent -p --force {prompt}`.
