# GitHub Copilot

```bash
lawkeep init --agent copilot
```

**Status: not run for real.** Set up according to GitHub's documentation (checked 2026-11-21) and
tested with simulated hook messages only. Copilot CLI, the Copilot cloud agent and VS Code agent mode
are covered as far as each supports hooks.

## What `init` sets up

| File | What lawkeep adds |
| --- | --- |
| `.github/copilot-instructions.md` | the lawkeep instructions (Copilot's agents also read `AGENTS.md`) |
| `.github/hooks/lawkeep.json` | `preToolUse` and `sessionStart` hooks (Copilot CLI and the cloud agent) |
| `.mcp.json` | the `lawkeep` MCP server (read by VS Code and Copilot CLI) |
| `AGENTS.md` | the lawkeep section |

## Things to know

- In the cloud agent and in Copilot CLI's autopilot mode, nobody can answer a prompt, so "ask" is
  treated as "deny": the agent cannot run `lawkeep approve` there at all.
- The cloud agent reads hooks only from the default branch, and its MCP servers are set in the
  repository's settings on github.com, not in a file.
- VS Code's own agent mode is not listed as a hooks surface in GitHub's reference, so there lawkeep
  relies on the shared base (instructions, MCP, pre-commit hook, `lawkeep check`).
- Not verified: which field holds the file path for `edit` / `create` tool calls; lawkeep's hook looks
  for every common field name.

## `lawkeep draft`

Default command:

```bash
copilot -p {prompt} --no-ask-user \
  --allow-tool 'read, write(laws/drafts/*), write(laws/strategies.py)' \
  --deny-tool 'shell, url'
```

It allows reading and writing only draft files and `laws/strategies.py`, and denies shell and URL
access. This command is based on GitHub's Copilot CLI documentation and has never been run; in
particular it is not confirmed that a tool which is neither allowed nor denied is refused in `-p`
mode, or that `write(laws/drafts/*)` matches every draft path.
