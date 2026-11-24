# src/lawkeep/adapters/templates

Text files that `lawkeep init` writes into a user's project. They ship inside the package and
are read with `adapters.base.template(name)` (`importlib.resources`), by name only.

- `agents_snippet.md`: the lawkeep section put into the project's `AGENTS.md` (between
  `<!-- lawkeep:begin -->` / `<!-- lawkeep:end -->`) and reused by the Copilot and Cursor
  adapters. It is what every coding agent is told: run `check`, fix the code not the law, never
  touch `laws/` directly, use `propose`, `approve` only when the person asks, stop and ask when
  the person is there, and "When no person is there": park (propose), never work around the
  law or approve, keep going, end with done / waiting (ids) / not done because blocked. The same
  rules are in `commands/hook.py` (`REMINDER`, `NO_PERSON`) and `mcp_server.INSTRUCTIONS`;
  `tests/test_lifecycle_waiting_list.py` checks the key phrases in all of them.
- `pre-commit.sh`: the block added to `.git/hooks/pre-commit` (shows, does not block unless
  `git config lawkeep.precommit block`).
- `strategies.py`: the starting `laws/strategies.py`.
- `lawkeep-workflow.yml`: `.github/workflows/lawkeep.yml` for `init --ci`. It may only pass inputs
  that the root `action.yml` defines (a test checks this). The copy-me workflows in
  `.github/workflows/templates/` are separate files.

Gotchas: wording here is user-facing; keep it plain English and honest (rule 3 in the root
`AGENTS.md`), and keep commands and result codes in line with `docs/ARCHITECTURE.md` section 7.
This AGENTS.md is never installed (only named files are read). `agents_snippet.md` is also
quoted in the generated `docs/llms-full.txt`: after changing it run
`uv run python scripts/build_llms_docs.py` (CI fails otherwise).

Test: `uv run pytest tests/test_adapters_init.py tests/test_adapters_install.py`.
