# MCP server

lawkeep includes a [Model Context Protocol](https://modelcontextprotocol.io/) server, so any agent
that supports MCP can use lawkeep as tools.

```bash
pip install 'lawkeep[mcp]'     # or: uv add --dev 'lawkeep[mcp]'
lawkeep mcp --agent claude-code
```

The server talks over standard input and output. `lawkeep init` writes the client configuration for
you (`.mcp.json`, `.codex/config.toml` or `.cursor/mcp.json`). The launcher falls back to the
project's `.venv` when `lawkeep` is not on the path.

## Tools

| Tool | What it does |
| --- | --- |
| `check(profile=None, laws=None)` | runs every law (`lawkeep check --json`) and returns the JSON report |
| `propose(law_id, reason, file=None, content=None, delete=False)` | proposes a law change instead of editing `laws/`; the new version comes as a file under `laws/drafts/` or as the full source |
| `report(since=None, session=True)` | the law change report for this session (or since a time) |
| `list_laws(include_drafts=False)` | the project's laws (id, sentence, file) without running any code |

`check`, `propose` and `report` run the same command as the CLI and return its JSON unchanged.
There is deliberately **no `approve` tool**: approving is for people.

`--agent` sets who is recorded as the author of proposals (`agent:claude-code`, ...; default
`other`).

## Instructions sent to the agent

The server also sends instructions that repeat the rules: run `check` before finishing, fix the code
and not the law, change laws only with `propose`, stop and ask when a person is there, park and keep
going when nobody is, and show the person `report` at the end. The exact text is in
[llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt), section "MCP server".
