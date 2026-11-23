# src/lawkeep/commands

One module per CLI command: `init`, `draft`, `approve`, `check`, `strength`, `propose`, `report`, `hook`, `mcp`.
`cli.py` discovers them; never edit `cli.py` to add arguments.

Each module exposes `HELP`, `add_arguments(parser)` and `run(args) -> int`. `cli.py` adds `--json` and `--root`.
Pattern: `root = paths.require_root(args.root); cfg = config.load_config(root)` … `output.emit(report, args.json, text=...)`;
return `report.exit_code`. The human `text` is built only when `not args.json`, with `lawkeep.ui`
(banner first, `ui.next_step` last) and `lawkeep.explain` (shared sentences and the draft-law
panel used by `draft` and `approve`); follow `docs/OUTPUT-STYLE.md`. The JSON report (summary,
`lines`, `data`) keeps its old content: agents parse it. `check` and `strength` take
`--details`/`-v` for ids, timings and every note. `approve` prints each item with `ui.show`
before asking (`_ask`, or `_choose` for an unconfirmed approval: confirm / undo / skip), then a
closing screen (`_final_screen`). With no ids it is the one waiting list (`collect(...,
unconfirmed=True)`, items sorted with unrecorded first, `overview` table, `_ask_each`:
unrecorded first, then the "approve all recommended" batch when 2+ items are
`_is_batch_safe`, then one by one). A yes recorded without a terminal goes through
`_decide_recorded`, which keeps undo copies (`approvals.keep_copies`). `check`, `report` and
`hook session-start/-end` add the waiting count (`waiting.collect`) and `person_present`
(`presence.detect`); `propose` sets `next_step` ("Parked as h-… Continue …" when nobody is
there). Raise `errors.SetupError(msg, hint=...)` for setup problems (exit 3).
Show `cfg.warnings`. Never prompt in `--json` mode or without a terminal: return 2 (waiting) instead.

Gotchas: `approve` is the only command that records a person's yes; `propose` refuses while
`laws.lock` shows an unrecorded change; `draft` never leaves the agent's edits to approved files
in place: `draft_edits` puts them back and parks them as waiting proposals (shared parking code:
`propose.park_proposal`; `apply_proposal` writes `whole_file` proposals byte for byte), and
`approve --yes` without ids never decides them (`approve._is_weakening`) nor unconfirmed
approvals, and the batch never takes anything `_is_weakening`, unrecorded or unconfirmed.
`approve.select` is the one place that picks what a run decides; the guard's approve question
(`adapters/approve_preview.py`) reuses it with `approve.collect`, so keep both free of
writes and project code. Agent hooks (`hook pre-tool-use`) always exit 0 because
exit 2 means "block" to agents.

Tests: `tests/test_gate_check_cli.py`, `test_report_cli.py`, `test_lifecycle_flow.py`,
`test_lifecycle_draft_edits.py`, `test_lifecycle_waiting_list.py` (park and keep going, the one
waiting list, the batch, confirm/undo),
`test_lifecycle_review_fixes.py`, `test_adapters_init.py`, `test_adapters_hook.py`,
`test_adapters_mcp.py`, `test_core_cli.py`. Run them against `tmp_path` projects, never this repository.
