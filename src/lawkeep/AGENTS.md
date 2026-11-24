# src/lawkeep

The lawkeep Python package (v0.1). `docs/ARCHITECTURE.md` is the code contract; `docs/PLAN.md` the design.

- **Foundation:** `__init__.py` (lazy public API and `__version__`), `__main__.py`, `_law.py`
  (`@law`), `strategies.py` (`st`), `config.py` (`lawkeep.toml`), `paths.py`,
  `models.py` (every report shape), `lock.py` (`laws.lock`), `history.py` (`laws/history.jsonl`;
  `record_change` is the only way to change laws), `discovery.py` (finds laws without running code),
  `output.py` (JSON and `emit`), `ui.py` (the shared Rich building blocks every command uses
  for human output: verdict banner, panels, tables, warnings, next step, yes/no; plain text when
  not a terminal, in CI or with `NO_COLOR`), `explain.py` (the shared plain-English sentences
  about laws: "works with your current code", strong/weak, example tables, recommendations),
  `readable.py` (input values in words: "a charge of $0.25 with no discount code"; parses
  with `ast`, never runs anything, returns None when unsure),
  `exitcodes.py` (0 hold, 1 fail, 2 waiting, 3 setup), `errors.py`, `cli.py`.
- **Law-running core (one way to run laws):** `lawrun.py` (parent side: the isolated
  `python -I -S -B` command through `_boot.py`, the scrubbed environment, the request sent on
  stdin, the write-once results pipe read as JSON lines, the shared pytest arguments, and the
  three modes `check` / `strength` / `probe` with their per-mode settings in `MODES`) and
  `_lawrun_child.py` (child side: reads the request, opens the results channel, removes
  `LAWKEEP_*` except `LAWKEEP_ROOT`, sets `sys.path`, calls the mode's handler). Handlers:
  `pytest_plugin.run_check`, `strength/_worker.run`, `_probe_worker.run`.
- **Gate:** `runner.py` (`check` mode: builds the gate request, turns the one results record
  into a `RunOutcome`, and hints at a close match for an unknown `--law` id),
  `pytest_plugin.py` (switched on only by `run_check`, never by the
  environment; passive otherwise, and it is loaded in every pytest run, this repository's
  included, through the pytest11 entry point; `load_laws_fixtures` is shared with strength),
  `integrity.py` (lock, history and side-door checks; no code runs), `ledger.py` (saved failing examples).
- **Law lifecycle:** `direction.py` (stricter / same / looser / unclear by evidence, plus the static
  "limit moved" rule `bound_direction`; the evidence uses a fixed seed from the law id and both
  versions' source hashes and a fixed budget of 100 inputs), `permissions.py`,
  `examples_table.py` (example tables from the `probe` mode; always seeded, `PYTHONHASHSEED=0`,
  private Hypothesis storage folder, so the same files give the same inputs; the child code is
  `_probe_worker.py`), `agent_launcher.py`, `lawchanges.py` (the law change report),
  `draft_edits.py` (after `lawkeep draft`: each fingerprinted file the drafting agent changed,
  other than pure additions to `laws/strategies.py`, is put back and becomes one waiting
  proposal through `commands/propose.park_proposal` with `whole_file`/`from_draft`; direction
  judged per changed law with `direction.decide_direction`; never applied automatically).
- **Long runs without a person (2026-11-23):** `waiting.py` (the one waiting list: drafts,
  proposals, drafting-agent edits, unrecorded edits, unconfirmed approvals; `collect` is static,
  never raises, and feeds the additive JSON `waiting_for_person` and the one-line count in
  `check`, `report`, the session hooks and the PR comment), `approvals.py` (approvals recorded
  with `terminal: false`: `unconfirmed_groups`, `keep_copies` of the earlier file bytes under
  `laws/drafts/proposals/undo/<id>/`, and `confirm`/`undo`, which only `approve` calls, in a
  terminal), `presence.py` (`detect()`: the documented `person_present` guess; it never changes
  what lawkeep allows).
- **Strength and protection:** `strength/`, `protection.py`. **Agents:** `adapters/`, `mcp_server.py`.
  **Commands:** `commands/`.

Conventions: Python 3.10+; human output follows `docs/OUTPUT-STYLE.md` and goes through
`ui.py`/`explain.py` (lead with the verdict, give every number its meaning, ids and paths dim or
behind `--details`, end with "Next step:"); every command supports `--json`, whose output never
goes through Rich and must keep its schema (keep `SimpleReport.lines` and the summaries as they
are; build the human screen separately and pass it as `emit(..., text=...)`); `@law` takes an
optional `inputs={"name": "plain description"}` (read statically by
`discovery.describe_inputs`); never call `lock.write_lock` directly; check `lock.diff_against_lock(root).is_empty` before
recording a change; import optional packages (`mcp`, `crosshair`) lazily; never say "proven" below L4.
Gotcha: code that runs laws must go through `lawrun.run` (never plain `python` or `pytest`;
add a mode there rather than a fourth way of starting Python), and
`integrity.py` / `discovery.py` / `lock.py` must never import or run project code.
Gotcha: Hypothesis adds constants from every loaded non-site-packages module to its inputs, so
in an editable install (this repository) the lawkeep modules a child imports can change the
inputs a probe draws; keep child-side imports small and stable.

Types: the whole package passes `uv run pyright` in **strict** mode (`[tool.pyright]` in
`pyproject.toml`; the decision is in `docs/PLAN.md`, 2026-11-23) and ships `py.typed`. Keep it
that way: annotate every function; give empty lists/dicts an element type
(`out: list[str] = []`, `field(default_factory=list["LawInfo"])`, quoted when the class is
defined later); read JSON from disk through `models.as_dict` / `models.as_list`; at untyped
third-party boundaries (Hypothesis internals, pytest's `from_parent`, the `mcp` SDK) use a `cast`,
a `Protocol` (see `mcp_server._Server`) or a typed wrapper. `HistoryEntry.from_dict` and the other
`from_dict`s raise `TypeError` when a list/dict field holds another kind of value. Suppress only
with `# pyright: ignore[rule]  # reason` (`# type: ignore` is not honoured); there are 6 today.
Runtime guards for untyped callers (e.g. `@law` argument checks) take `object` so strict mode does
not call them unnecessary.

Test: `uv run pytest` (whole suite, about 6-7 minutes); tests are in `tests/` by module prefix
(see `tests/AGENTS.md`).
