# tests

pytest suite for lawkeep. Run: `cd <repo> && uv run pytest -q` (about 6-7 minutes);
lint: `uv run ruff check src tests && uv run ruff format --check src tests`; types:
`uv run pyright` (tests are checked in pyright's standard mode, `src/lawkeep` in strict mode).

- File prefixes follow the modules: `test_core_*` (foundation), `test_gate_*`, `test_strength_*` /
  `test_protection_*` / `test_report_*`, `test_lifecycle_*`, `test_adapters_*`, `test_ui_output.py`
  (human output: fits 80 and 60 columns without breaking words, plain mode has no ANSI codes,
  JSON keys unchanged, the wording of `lawkeep.explain`); the
  `*_review_fixes.py` files cover the 2026-11-22 review fixes; `test_adapters_guard_writes.py` is the table of shell commands the guard allows or denies, `test_lifecycle_draft_edits.py` the drafting agent's edits to approved files becoming waiting proposals (law looser/stricter, settings, generators, deleted file; approve, reject, changed meanwhile), `test_lifecycle_waiting_list.py` long runs without a person (the no-person rules in every agent instruction source, the `person_present` guess, the waiting count in check/report/hooks/Markdown, all five kinds in `approve`, the safe batch, confirm/undo of approvals made without a terminal; it clears `CI`, `LAWKEEP_PERSON_PRESENT` and the Claude Code variables so the guess does not depend on where the tests run), `test_lifecycle_direction_determinism.py` the static "limit moved" rule and same-change-same-label runs, `test_docs_llms.py` the generated LLM docs (`scripts/build_llms_docs.py --check` passes, `llms.txt` has the llms.txt shape, `llms-full.txt` lists every command); `test_lawrun.py` the law-running core (every mode starts isolated in a hostile shell, writes nothing into the project, request on stdin, records on the pipe, partial results on timeout, the gate's one-record channel). `tamper/` is the cheating test
  suite (see its AGENTS.md); `fixtures/` holds made-up projects (see `fixtures/AGENTS.md`).
- The slow tests are the gate, strength, lifecycle and tamper ones: they start real isolated
  Python processes. Run one file while working, the whole suite before you finish.
- Tests run with `--import-mode=importlib` and there is no shared `conftest.py`: put helpers in your
  own test file.
- Use `tmp_path` copies only. Never run a lawkeep command that changes files with this
  repository as the project: lawkeep checks itself here (root `laws/`, `laws.lock`; see
  `AGENTS.md` → "Current state"), so a test that ran `init`, `propose` or `approve` here would
  change the real setup. Run subprocesses with `cwd=tmp_path`.
- Types: tests pass `uv run pyright` in standard mode. Functions that return `X | None` need an
  `assert value is not None` (or a small helper that asserts) before use; deliberate misuse in a
  test gets `# pyright: ignore[rule]  # reason`. `tomli` is a dev dependency so the 3.10 branch
  type-checks.
- Human text wraps at the terminal width (80 when not a terminal): tests that look for
  long phrases set `COLUMNS=200`, or assert on JSON / stable key phrases.
- Never call a real coding agent or the network; inject runners (`agent_launcher.launch(runner=...)`)
  or use `fixtures/lifecycle/fake_agent.py`.
- No private code: every fixture is a made-up project.
