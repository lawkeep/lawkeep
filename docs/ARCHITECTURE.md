# lawkeep architecture: the interface contract

As of 2026-11-22 (v0.1 build, after integration). `docs/PLAN.md` is the design source of truth;
this file is the **code contract** that the parallel workstreams code against without talking
to each other. If you need to change a signature or a data format listed here, do not change it
silently: keep the old one working, add the new one, and report the change.

Contents: 1 Conventions · 2 Ownership · 3 Project layout on disk · 4 Data formats ·
5 Foundation modules (implemented) · 6 Workstream modules (as built) · 7 Commands ·
8 How the modules call each other · 9 Open points for the maintainer

---

## 1. Conventions (everyone)

- **Python 3.10+**, src layout, `uv`. Run tests with `cd /home/abhishek/personal/lawkeep && uv run pytest <paths>`.
  Lint: `uv run ruff check src tests && uv run ruff format --check src tests`.
  Types: `uv run pyright` (`src/lawkeep` strict, `tests` standard; `[tool.pyright]` in
  `pyproject.toml`). Suppress only with `# pyright: ignore[rule]  # reason`; `# type: ignore`
  is not honoured. JSON read from disk goes through `models.as_dict` / `models.as_list` (or a
  `cast` right after an `isinstance` check) so its shape is checked where it enters.
- **Result codes** (`lawkeep.exitcodes`): `ALL_HOLD=0`, `SOME_FAIL=1`, `WAITING=2`,
  `SETUP_PROBLEM=3`. When several apply, `exitcodes.combine(*codes)` picks with precedence
  3 > 1 > 2 > 0. argparse usage errors also exit 3 (never 2, which means "waiting").
- **Every command supports `--json`** (added by `cli.py`; read `args.json`). JSON mode prints
  exactly one JSON document on stdout and nothing else on stdout. Use `output.emit(report, args.json)`.
- **Plain English** in every user-facing message, with concrete examples
  ("refund $0.50 → fee $0.00"). Say what happened and what to do next. The rules are in
  `docs/OUTPUT-STYLE.md`; human screens are built with `lawkeep.ui` (Rich: colour and boxes on a
  terminal, plain ASCII text when not a terminal, in CI or with `NO_COLOR`) and the shared
  sentences in `lawkeep.explain`. `--json` never goes through Rich.
- **Honest wording.** Never "proven" / "foolproof" below L4. The promise is: *the AI never changes
  your laws silently; weakening needs your yes.* lawkeep records and shows; it never forces a
  team process (no mandatory reviews, no branch protection, no blocking by default).
- **Setup problems** are raised as `lawkeep.errors.SetupError(message, hint=...)` (or a
  subclass); `cli.py` turns them into a standard JSON/text message and result code 3. Unexpected
  crashes also become code 3 (set `LAWKEEP_DEBUG=1` to get the traceback).
- **Paths in data** are relative to the project root with forward slashes (`"laws/refunds.py"`);
  use `paths.rel(root, p)`.
- **Timestamps** are UTC ISO 8601 with microseconds and `Z`: `models.utc_now_iso()`
  (`"2026-11-21T10:00:00.123456Z"`, sorts correctly as text); parse with `models.parse_iso()`.
- **Actors**: `"agent:<name>"` (`agent:claude-code`, `agent:codex`, `agent:cursor`,
  `agent:copilot`, `agent:other`), `"person:<name>"` (default from `history.default_person(root)`:
  git `user.name`, else `$USER`), `"lawkeep"` (automatic, e.g. saving a new failing example).
- **Function names in data**: `"module.path:qualname"`, e.g. `"billing.refunds:refund"`.
- **Wrap, don't rebuild**: pytest, Hypothesis, CrossHair (`hypothesis-crosshair` backend),
  coverage.py, mutmut, git. Explain in your output when wrapping was impractical.
- **Tests** live in `tests/` with your workstream prefix, use made-up projects in `tmp_path`,
  never call a real coding agent or the network. `tests/` uses `--import-mode=importlib`
  (test files cannot import each other; there is no shared `tests/conftest.py`, on purpose,
  to avoid edit conflicts. Put helpers in your own test files).
- Optional dependencies (`crosshair`, `mcp`, `mutmut`) must be imported lazily; when missing,
  raise `SetupError` with the install hint (`uv add 'lawkeep[deep]'`, `pip install 'lawkeep[mcp]'`).

## 2. Ownership

Only edit files you own. Need a change elsewhere? Work around it in your files and report it.

| Workstream | Owns |
| --- | --- |
| A Foundation | `pyproject.toml`, `uv.lock`, `.gitignore`, `.python-version`, `LICENSE`, `src/lawkeep/{__init__,__main__,_law,strategies,config,paths,models,exitcodes,errors,lock,history,discovery,output,cli}.py`, `src/lawkeep/commands/__init__.py`, `docs/ARCHITECTURE.md`, `tests/test_core_*.py` |
| B Gate | `lawrun.py` + `_lawrun_child.py` + `_boot.py` (the law-running core, shared by B, C and D), `runner.py`, `pytest_plugin.py`, `integrity.py`, `ledger.py`, `commands/check.py`, `tests/test_gate_*.py` |
| C Strength & protection | `strength/` (package, any submodules), `protection.py`, `commands/strength.py`, `commands/report.py`, `tests/test_strength_*.py`, `tests/test_protection_*.py`, `tests/test_report_*.py` |
| D Law lifecycle | `permissions.py`, `direction.py`, `examples_table.py` + `_probe_worker.py`, `agent_launcher.py`, `lawchanges.py`, `waiting.py`, `approvals.py`, `presence.py`, `commands/draft.py`, `commands/approve.py`, `commands/propose.py`, `tests/test_lifecycle_*.py` |
| E Adapters | `adapters/` (package), `mcp_server.py`, `commands/init.py`, `commands/hook.py`, `commands/mcp.py`, `tests/test_adapters_*.py` |
| F CI & proof | `action.yml`, `.github/workflows/`, `examples/`, `tests/tamper/`, `README.md`, `docs/site/` |

(Test-file prefixes for B–F are suggestions if your task gives none; the orchestrator's task text wins.)
Only A edits `pyproject.toml` in this phase: report needed dependencies instead (`uv run --with <pkg>` for experiments).

## 3. Project layout on disk (a user's project)

```
lawkeep.toml                    settings + permissions            fingerprinted in laws.lock
laws.lock                       fingerprints (TOML)               written only via history.record_change
laws/                           approved laws + helpers           fingerprinted (every file)
laws/strategies.py              project input generators (st.*)   fingerprinted
laws/conftest.py                law fixtures (optional)           fingerprinted
laws/history.jsonl              law history, append-only          line count + prefix hash in laws.lock
laws/failing_examples.jsonl     saved failing inputs, append-only line count + prefix hash in laws.lock
laws/drafts/                    drafts + pending proposals        NOT fingerprinted, ignored by the gate
laws/drafts/drafts.json         who drafted which file (actor, request, module, created_at)   (D)
laws/drafts/strategies.py       new generators parked until a draft is approved                (D)
laws/drafts/proposals/<id>/     a pending proposal: proposed.py.txt + meta.json                (D)
laws/drafts/proposals/undo/<id>/  earlier bytes of the files an approval made without a terminal
                                changed (manifest.json + N.txt), for a later undo               (D)
.lawkeep/                       local state (session.json, caches) not committed, not protected
```

- A pending proposal's `proposed.py.txt` ends in `.txt` so neither the gate nor draft
  discovery collects it. The waiting history entry's `details` hold `proposal_path`,
  `target_file`, `base_sha256` (target file when proposed), `proposal_sha256`, `delete`,
  `evidence`, `direction_evidence`, `explanation`, `examples`, `permission_key`. `approve`
  trusts these (append-only history) over `meta.json` and refuses a proposal whose file or
  target changed since it was recorded.
- Edits the drafting agent of `lawkeep draft` makes to a fingerprinted file (an approved law,
  an existing generator in `laws/strategies.py`, `lawkeep.toml`, a helper in `laws/`) are put
  back on disk and parked the same way, one proposal per file (`lawkeep.draft_edits`,
  `propose.park_proposal`). Their `details` also hold `whole_file: true` (the proposal is the
  complete new file, applied byte for byte; with `delete` the whole file is removed),
  `from_draft: true`, `kind` (`law` | `generators` | `settings` | `file`), `changes` (plain
  English), `laws` (law ids in the file that changed), `diff` (short unified diff),
  `new_version_runs`, `waits_because` and, when the agent wrote a `Changed <path>: <why>` line,
  `agent_reason`. They are never applied automatically, even when stricter, and `approve
  --yes` without ids never decides them.
- `propose --file laws/drafts/x.py` removes `x.py` once the proposal is applied or parked, so it
  does not show up again as a new draft. The guard (E) keeps agents out of `laws/drafts/proposals/`.
- When `approve` records a yes without a terminal (`details.terminal: false`), it keeps the
  earlier bytes of every file that approval changed in `laws/drafts/proposals/undo/<history
  id>/` (`approvals.keep_copies`). `approvals.undo` uses a copy only when its fingerprint
  matches what the append-only history says the file was before the approval; otherwise it
  looks in git (last 50 commits of that file), and refuses when it finds nothing. Confirming or
  undoing removes the copies.

- Project root = nearest folder upward with `lawkeep.toml`, else nearest with `laws/`
  (`paths.find_root(start)`). `--root PATH` sets the start; without it, env `LAWKEEP_ROOT`
  (if set) is used, else the current folder.
- **Law files**: any `*.py` under `laws/` except `strategies.py`, `conftest.py`, `drafts/**`,
  cache folders. **A law is any function or class decorated with `@law`**, whatever its name
  (`discovery.iter_python_files`, `discovery.NON_LAW_FILES`). pytest's default collection only
  finds `test_*` names in `test_*.py` files, so the gate's plugin (B) must collect `@law` items
  itself; users may still name laws `test_*` so plain `pytest laws/` also works.
- Fingerprinted = `lock.is_fingerprinted(root, path)`; excluded: `laws/drafts/`, the two
  append-only files, `__pycache__`, `.hypothesis`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`,
  `*.pyc`, `*.pyo`. Stray bytecode is a side door that the integrity check (B) reports separately.

## 4. Data formats

### 4.1 `lawkeep.toml`

Parsed by `config.load_config(root)` → `Config`. Every key optional.

```toml
[permissions]            # "auto" (go ahead, tell me) or "ask" (wait for my yes)
add_law       = "auto"   # add a new law                                   (stricter)
add_example   = "auto"   # add an example / saved failing case             (stricter)
rename_target = "auto"   # update a law after a rename, same meaning confirmed (same)
change_law    = "ask"    # change what a law checks                        (unclear)
weaken_law    = "ask"    # loosen, delete, skip, fewer cases               (looser; ALWAYS "ask")

[check]
profile = "pr"           # default profile for `lawkeep check`

[check.pr]               # any [check.<name>] table defines/overrides a profile
examples    = 200        # Hypothesis max_examples per law (>= 1)
derandomize = true       # fixed seed: same code -> same verdict
backend     = "hypothesis"   # or "crosshair" (L3, experimental, needs lawkeep[deep])
deadline_ms = 0          # 0 = no per-example deadline
# seed = 123             # only meaningful with derandomize = false

[check.deep]
examples    = 2000
derandomize = false

[project]
source = ["src"]         # code under test; default "src" if it exists, else "."

[strength]
mutation_tool   = "mutmut"
quick_check     = true
min_bugs_caught = 1

[agent]                  # how `lawkeep draft` starts the user's coding agent
name    = "claude-code"  # claude-code | codex | cursor | copilot | other | ""
command = ""             # overrides the preset; {prompt} / {prompt_file} placeholders; else stdin
timeout_seconds = 900
```

Rules: invalid values → `ConfigError` (code 3); unknown keys/sections → `cfg.warnings` with a
"did you mean" hint; `weaken_law = "auto"` → forced to `"ask"` plus a warning. Commands should show
`cfg.warnings` (text: as notes; JSON: in `notes`/`data`).
`config.AGENT_PRESETS` holds best-guess launch commands per agent; **they are not yet confirmed**
against each agent's current CLI (D/E: verify and report).

### 4.2 `laws.lock` (TOML, `lock.LockFile`)

```toml
# laws.lock - written by lawkeep; do not edit by hand.
version = 1
generated_at = "2026-11-21T10:00:00.000000Z"
lawkeep_version = "0.1.0.dev0"

[files]                                  # every fingerprinted file -> sha256 of its bytes
"lawkeep.toml" = "sha256:<64 hex>"
"laws/refunds.py" = "sha256:<64 hex>"

[laws."refunds.refund_is_capped"]        # per law, from static discovery (no code run)
sentence = "A refund never exceeds the original charge"
file = "laws/refunds.py"
hash = "sha256:<64 hex>"                 # the law's own source incl. decorators

[append_only."laws/history.jsonl"]
lines = 12                               # lines present when the lock was written
prefix_sha256 = "sha256:<64 hex>"        # hash of exactly those lines
[append_only."laws/failing_examples.jsonl"]
lines = 3
prefix_sha256 = "sha256:<64 hex>"
```

`sentence` / `hash` are omitted when unknown. The lock is rewritten **only** by
`history.record_change()` (and nothing else should call `lock.write_lock` in production code).

### 4.3 `laws/history.jsonl` (`models.HistoryEntry`)

One JSON object per line, keys sorted, UTF-8, always newline-terminated, append-only.

| key | type | meaning |
| --- | --- | --- |
| `v` | int | entry format version, `1` |
| `id` | str | `"h-<8 hex>"`, unique |
| `timestamp` | str | UTC ISO 8601 `...Z` |
| `action` | str | `init`, `add_law`, `add_example`, `rename_target`, `change_law`, `remove_law`, `skip_law`, `change_settings`, `reject_draft`, `accept_unrecorded_change`, `relock`, `confirm_approval` (a person in a terminal confirmed approvals recorded without a terminal: `details.entries` [ids], `details.terminal: true`; nothing on disk changes), `undo_approval` (a person in a terminal undid them: the files go back to their earlier versions, `details.entries`, `details.undone_action`, direction the opposite of the undone change; an undone draft approval puts the file back in `laws/drafts/`), `add_strategy` (the drafting agent only added input generators to `laws/strategies.py`; recorded automatically under `add_law`, direction `stricter`, `law_id` null), `change_strategy` (a waiting or decided change to existing generators in `laws/strategies.py`, made by the drafting agent; `law_id` null), `change_law_file` (a waiting or decided change by the drafting agent to another fingerprinted file that holds no law, e.g. a helper in `laws/` or the lawkeep workflow; `law_id` null) (others accepted; document new ones here). `change_settings` is also used for the drafting agent's `lawkeep.toml` edits (`law_id` null) |
| `law_id` | str \| null | law affected |
| `direction` | `stricter`\|`same`\|`looser`\|`unclear`\|null | decided by evidence (D's `direction`) |
| `actor` | str | who made the change (`agent:…`, `person:…`, `lawkeep`) |
| `reason` | str | why (the user's request, the agent's reason) |
| `permission_used` | `auto`\|`ask`\|`none` | which permission value allowed it |
| `approved_by` | str \| null | `person:<name>` when a person said yes |
| `status` | `applied`\|`waiting`\|`rejected` | `waiting` = needs a person's decision |
| `sentence_before` / `sentence_after` | str \| null | for the report |
| `files` | {path: sha256 \| null} | fingerprinted files changed by this entry, hash AFTER (null = deleted). Filled by `record_change` |
| `details` | object | free-form; recommended keys: `evidence` (plain-English string shown in reports, e.g. `"catches 4 of 4 planted bugs"`), `examples` (list of ExampleRow dicts), `proposal_path` (for waiting proposals), `permission_key` |
| `refers_to` | str \| null | id of the `waiting` entry this entry decides (approve/reject) |

Pending decisions = `history.pending(entries)`: `waiting` entries no later entry `refers_to`.

### 4.4 `laws/failing_examples.jsonl` (ledger; format owned by B)

Append-only JSONL, one object per line, keys sorted, newline-terminated. Never rewritten.

| key | meaning |
| --- | --- |
| `v` | `1` |
| `ts` | ISO timestamp |
| `law_id` | the law that failed |
| `found_by` | `"lawkeep"`, `"agent:<name>"` or `"person:<name>"` |
| `example` | `{arg: readable repr}` or null |
| `choices` | base64 of Hypothesis's choice bytes, or null |
| `choices_format` | `"hypothesis-choices"` or null |
| `hypothesis_version` | version that recorded `choices` |
| `failure` | first line of the failure message, or null |
| `profile` | the check profile that found it, or null |

Rules: lines with `choices` are replayed for that law on every run (each law gets an in-memory
Hypothesis database whose main key returns them; keyed by law id, so a saved failure survives
edits to the law). Only `check` adds lines (`found_by="lawkeep"`) and it never touches
`laws.lock`; the runner itself never writes the ledger (planted-bug and draft runs cannot pollute
it). Deduplication is by `(law_id, choices)`. Lines without `choices` are shown but cannot be
replayed (use `@example`). Known gap: lines added after the last lock write are protected only by
git once committed (`lock.check_append_only` knows only the line count at lock time).

### 4.5 `.lawkeep/session.json`

`{"started_at": "<iso>", "agent": "<name or null>"}`, written by `history.mark_session_start`
(E's `hook session-start`), read by `history.session_start(root)`. Local only, not protected.

### 4.6 JSON reports (all commands)

Every top-level report has these keys first: `kind`, `schema_version` (=1), `exit_code`,
`summary` (one plain-English line), `lawkeep_version`. Shapes are the `to_dict()` of:

| Command | Model | `kind` | extra keys |
| --- | --- | --- | --- |
| check | `CheckReport` | `check` | `profile`, `root`, `laws` [LawResult], `integrity` [IntegrityIssue], `waiting` [LawChange], `notes` [str], `started_at`, `duration_seconds`, `only_laws` [str] (the `--law` ids; empty = every law ran), `laws_known` (int or null), `waiting_for_person` {WaitingList}, `person_present` (bool), `person_present_reason` (str) |
| strength | `StrengthReport` | `strength` | `mode` (`quick`\|`full`), `laws` [StrengthResult], `uncovered_functions` [str], `notes` |
| report | `LawChangeReport` | `report` | `since`, `changes` [LawChange], `integrity` [IntegrityIssue], `protection` ProtectionReport\|null, `notes`, `waiting_for_person` {WaitingList}, `person_present`, `person_present_reason` |
| (protection) | `ProtectionReport` | `protection` | `base_ref`, `functions` [ProtectionResult], `notes` |
| propose | `ProposalResult` | `propose` | `law_id`, `direction`, `decision` (`applied`\|`waiting`\|`rejected`\|`unchanged`\|`refused`), `permission_key`, `permission_value`, `reason`, `evidence` {}, `examples` [ExampleRow], `history_id`, `person_present` (bool\|null; set when the proposal waits), `next_step` (str\|null: "Show this to the person ..." or, when nobody is there, "Parked as h-... Continue with work that does not depend on this law; list h-... in your final summary ...") |
| init, draft, approve, hook, errors | `SimpleReport` | command name | `lines` [str], `data` {}, `hint` |

- `draft` `data`: `module`, `drafts` [{`law_id`, `sentence`, `file`, `probe`, `quick_check`,
  `quick_check_text`}], `files`, `waiting_changes` [{`history_id`, `file`, `kind`
  (`law`\|`generators`\|`settings`\|`file`), `action`, `direction`, `law_id`, `laws`,
  `sentence_before`, `sentence_after`, `reason`, `explanation`, `evidence`, `changes`,
  `examples`, `new_version_runs`, `deleted`, `created`}] (the drafting agent's edits to approved
  files, now waiting proposals; empty when there are none), `agent`, `agent_output`.
- `approve` `data.waiting` / `data.decided` items for proposals also carry `action` and
  `target_file`, and for the drafting agent's edits `from_draft: true`, `change_kind`,
  `changes`, `laws`. Added 2026-11-23 (additive): every item has `group` (its kind in the one
  waiting list: `draft`\|`proposal`\|`draft_edit`\|`unrecorded`\|`unconfirmed`; `kind` keeps
  its old values, with the new `unconfirmed`) and `batch_safe`; unconfirmed items carry
  `approval` {`history_ids`, `law_ids`, `action`, `direction`, `approved_by`, `channel`,
  `sentences`, `timestamp`}; `data.waiting_for_person` {WaitingList}; `data.person_present`,
  `data.person_present_reason`; `decided[].decision` may also be `confirmed` or `undone`.
  `approve` with no ids lists all five kinds (laws changed outside lawkeep included) and,
  without a terminal or with `--json`, decides nothing.
- **WaitingList** (`waiting_for_person`, from `waiting.collect`, static, never raises):
  `count`, `ids` [what to type after `lawkeep approve`], `by_kind` {`draft`, `proposal`,
  `draft_edit`, `unrecorded`, `unconfirmed`: int}, `items` [{`kind`, `ref`, `title`, `ids`}],
  `command` (`"lawkeep approve"`). Named `waiting_for_person` because `check`'s `waiting` already
  means "pending proposals". It never changes a result code.
- `hook session-start --json` `data` also carries `waiting_for_person`, `person_present`,
  `person_present_reason`.

Item shapes:

- **LawResult**: `law_id`, `sentence`, `status` (`holds`\|`fails`\|`error`\|`skipped`\|`not_run`),
  `level` (`L1` fixed examples only · `L2` Hypothesis · `L3` CrossHair backend · `L4` reserved),
  `examples_tried` (int), `simplest_failing_example` ({arg: repr} or `{"call": "<text>"}` or null),
  `failure_message`, `duration_seconds`, `evidence` {recommended: `profile`, `seed`, `backend`,
  `max_examples`, `saved_failures_replayed`, `explicit_examples`, `stop_reason`, and for L3
  `exhausted` (true only when CrossHair reports it explored all paths)}, `file`, `nodeid`.
- **IntegrityIssue**: `kind`, `message` (plain English), `path`, `severity`
  (`error` → needs a person's decision, makes `check` return at least 2; `warning`/`info` → shown only),
  `details` {}. Kinds (B may add more; list them here):
  `lock_missing`, `unrecorded_law_change` (file differs from lock), `unrecorded_law_added`,
  `unrecorded_law_removed`, `lock_rewritten` (lock not explained by history:
  `history.unexplained_lock_paths`), `append_only_violation`, `history_unreadable`,
  `side_door_file` (conftest.py outside laws/, sitecustomize.py, usercustomize.py, `*.pth`),
  `bytecode_file` (stray `.pyc` near laws), `skip_marker` (skip/xfail in laws), `discovery_problem`
  (warning: e.g. sentence not a string literal, duplicate law id). Added by B: `lock_unreadable`,
  `git_unavailable` (info), `weakened_settings` (max_examples below the profile, phases,
  register/load_profile, reproduce_failure in `laws/`; error when the file differs from the lock,
  else warning), `laws_conftest_hook` (hooks in `laws/conftest.py` or conftest files in its
  sub-folders: ignored by the gate and flagged), `site_packages_side_door` (warning:
  sitecustomize / usercustomize / code-running `.pth` in the interpreter's site-packages changed
  after the lock; the gate never runs them because it starts Python with `-S`; the `.pth` files
  every virtualenv has are skipped), `source_side_door` (code under test that imports lawkeep,
  pytest or Hypothesis, mentions `LAWKEEP_*`/`HYPOTHESIS_*`, raises skips, defines comparisons
  that always return `True`, or shadows a standard-library or installed module; error when the
  file is new or changed since the git base, else warning), `approval_unconfirmed` (warning:
  history entries added since the git base that claim a person's approval without
  `details.terminal: true`, unless a later `confirm_approval`/`undo_approval` lists them;
  `details.entries` holds their ids).
- LawResult `evidence` keys added by B: `derandomize`, `other_failing_examples`, `cases`,
  `bounded` (L3: true unless CrossHair reported every path explored), `inputs_thrown_away`
  (generated inputs rejected by `assume()`/`filter()`).
- A skip raised while a law runs (call phase), or during set-up without a `skip`/`skipif`
  marker, makes the law `error`, not `skipped`; so does `assume()`/`reject()` called from a
  file outside `laws/` inside the project.
- **Law ids in strength results**: when two target files define the same law id (an approved law
  and a draft of it), `StrengthResult.law_id` and `CatchMatrix` keys are `"<law_id>@<relative
  file>"`; otherwise the plain id. Look results up with `strength.result_for(results, law_id, file)`.
- Report kind `list_laws` (SimpleReport, `data.laws` = [LawInfo], `data.problems`) is returned
  only by the MCP tool of that name.
- **LawChange** (report row): `change` (`added`\|`updated`\|`removed`\|`waiting`\|`rejected`\|`unrecorded`\|`confirmed`\|`undone`),
  `law_id`, `sentence`, `sentence_before`, `direction`, `permission_used`, `approved_by`, `actor`,
  `reason`, `evidence` (str), `examples` [ExampleRow], `timestamp`, `history_id`.
  `LawChange.from_history(entry)` builds one from a history entry.
- **ExampleRow**: `inputs` {arg: readable value}, `result` (str), `holds` (bool), `old_holds`
  (bool, proposals), `note`.
- **StrengthResult**: `law_id`, `sentence`, `functions_touched` [str], `quick_check`
  [{`function`, `variant`, `caught`, `note`}], `planted_bugs_total`, `planted_bugs_caught`,
  `mutation_score` (derived, float\|null), `missed_bugs` [{file, line, description}], `vacuous`,
  `vacuity_reason`, `weak_data` [str], `flags` [str] (empty = no problem found).
- **ProtectionResult**: `function`, `file`, `status` (`protected`\|`partly`\|`not_protected`),
  `changed_lines`, `planted_bugs_total`, `planted_bugs_caught`, `laws` [law ids], `note`.

`Model.from_dict(d)` inverts `to_dict()` (unknown keys ignored), e.g. to read a report produced
by a subprocess. Commands may pass their own text rendering with `emit(report, as_json, text=...)`.

## 5. Foundation modules (implemented and tested)

### `lawkeep` (`__init__.py`)
Lazy public API: `law`, `given`, `st`, `example`, `settings`, `assume`, `note`, `event`,
`get_law`, `is_law`, `LawMeta`, `__version__` (single source of the package version).

### `_law.py`
- `law(sentence: str, *, id: str | None = None, inputs: dict[str, str] | None = None) -> Callable[[T], T]`
  — `inputs` (added 2026-11-22, optional) describes each input in plain words for the example
  tables; it is stored as `LawMeta.inputs` (omitted from `LawMeta.to_dict()` when `None`). Marks a function, a
  Hypothesis-wrapped function (above or below `@given`), or a `RuleBasedStateMachine` class (its
  cached `.TestCase` is marked too). Attaches `LawMeta` as `__lawkeep_law__` and the pytest marker
  `@pytest.mark.law(sentence, law_id=...)`. Sentence whitespace is collapsed. `@law` without a
  sentence → `TypeError` with an example.
- `LawMeta(sentence, law_id, qualname, file, kind, inputs=None)`; `kind` ∈ `function`, `state_machine`, `class`.
- `get_law(obj) -> LawMeta | None` (works on wrappers, inner functions, machines and their
  TestCase classes); `is_law(obj) -> bool`.
- `make_law_id(qualname, *, file, laws_dir, module=None) -> str`: path inside `laws/` with dots,
  no `.py`, leading `drafts` dropped, `__init__` dropped, plus qualname
  (`laws/billing/refunds.py::refund_is_capped` → `billing.refunds.refund_is_capped`); outside
  `laws/`: `module.qualname`. `@law(..., id="R7")` overrides.
- Constants: `LAW_ATTR = "__lawkeep_law__"`, `MARKER_NAME = "law"`.

### `strategies.py` (`st`)
Everything in `hypothesis.strategies` plus `money(min_value=0, max_value=1_000_000, *, places=2)`
(Decimal), `percentages(*, places=2)`, `non_empty_text(*, max_size=50)`, `ids(*, prefix="", max_value=10_000)`.
Unknown names are looked up in the project's `laws/strategies.py` (`st.charges()`), found via
`find_root()` (`LAWKEEP_ROOT` or cwd) and imported once as module `lawkeep_project_strategies`;
`reset_project_cache()` forgets it.

### `config.py`
`load_config(root) -> Config` (missing file → defaults), `loads(text, *, source=None) -> Config`,
`parse_config(data, *, source=None) -> Config`, `default_config()`, `render_default_toml(*, agent_name="", source=None) -> str`,
`DEFAULT_TOML`, constants `PERMISSION_KEYS`, `PERMISSION_VALUES`, `FIXED_ASK`, `BACKENDS`, `AGENT_NAMES`, `AGENT_PRESETS`.
`Config` fields: `permissions: Permissions` (`.get(key) -> "auto"|"ask"`), `check: CheckConfig`
(`.profile`, `.profiles`, `.get_profile(name=None) -> Profile` raising ConfigError), `project: ProjectConfig`
(`.source_dirs(root) -> list[Path]`), `strength: StrengthConfig`, `agent: AgentConfig`
(`.effective_command()`, `.is_set`, `.argv(prompt, prompt_file=None) -> (argv, stdin_text|None)`),
`warnings: list[str]`, `path`, `raw`, `to_dict()`.
`Profile(name, examples, derandomize, backend, deadline_ms, seed)`.

### `paths.py`
Constants (`CONFIG_FILENAME`, `LOCK_FILENAME`, `LAWS_DIRNAME`, `DRAFTS_DIRNAME`, `HISTORY_FILENAME`,
`LEDGER_FILENAME`, `STRATEGIES_FILENAME`, `STATE_DIRNAME`, `ROOT_ENV_VAR`);
`find_root(start=None) -> Path | None`; `require_root(start=None) -> Path` (raises `ProjectNotFound`, code 3);
`config_path`, `lock_path`, `laws_dir`, `drafts_dir`, `history_path`, `ledger_path`, `strategies_path`,
`state_dir`, `session_file` (each `(root) -> Path`); `project_paths(root) -> ProjectPaths`;
`rel(root, path) -> str`; `is_draft(root, path) -> bool`.
Commands start with `root = paths.require_root(args.root)` and `cfg = config.load_config(root)`.

### `errors.py`
`LawkeepError(message, *, hint=None)` (`.exit_code = 3`) ← `SetupError` ← `ProjectNotFound`,
`ConfigError`, `LockError`, `HistoryError`.

### `exitcodes.py`
`ALL_HOLD`, `SOME_FAIL`, `WAITING`, `SETUP_PROBLEM`, `VERDICTS`, `combine(*codes) -> int`, `verdict(code) -> str`.

### `models.py`
Dataclasses listed in 4.6 plus `LawInfo(law_id, sentence, file, qualname, line, kind, source_hash, is_draft, explicit_id)`,
`HistoryEntry` (4.3), `QuickCheckOutcome(function, variant, caught, note)`, base `Report`
(`kind`, `schema_version`, `exit_code`, `summary`, `lawkeep_version`; `.verdict`, `.to_text()`).
`CheckReport.finalize()` sets `exit_code`/`summary` from contents (fails/error → 1; integrity
`error` issues or `waiting` items → 2; else 0) and `CheckReport.to_text()` renders the gate output.
Choice tuples: `LAW_STATUSES`, `LEVELS`, `DIRECTIONS`, `HISTORY_STATUSES`, `PERMISSION_USED`,
`SEVERITIES`, `PROTECTION_STATUSES`, `CHANGE_KINDS`, `PROPOSAL_DECISIONS`, `HISTORY_ACTIONS`;
invalid values raise `ValueError` at construction. `utc_now_iso()`, `parse_iso()`.

### `discovery.py` (static, never runs code)
`discover_laws(root, *, include_drafts=False) -> DiscoveryResult(laws: list[LawInfo], problems: list[str])`
(`.by_id()`), `laws_in_file(path, root)`, `laws_in_source(source, *, file, root)`,
`iter_python_files(root, *, include_drafts=False) -> list[Path]`, `NON_LAW_FILES`, `SKIP_DIRS`.
Recognises `@law(...)`, `@lawkeep.law(...)`, aliases (`import lawkeep as lk`, `from lawkeep import law as keep`).
Ids match `_law.make_law_id`. Problems: syntax errors, non-literal sentences, duplicate ids.
Added: `describe_inputs(source, qualname) -> {input: plain description}` (from `@law(inputs=...)`,
else "made by lawkeep from <the @given generator>") and `describe_inputs_in_file(path, qualname)`.

### `lock.py` (never runs code)
`fingerprint(root) -> dict[str, str]`, `iter_fingerprinted_files(root) -> list[Path]`,
`is_fingerprinted(root, path) -> bool`, `hash_file(path) -> str`, `sha256_bytes(data) -> str`,
`build_lock(root) -> LockFile`, `read_lock(root) -> LockFile | None` (raises `LockError`),
`write_lock(root, lock) -> Path` (atomic), `dumps_lock`/`loads_lock`,
`compare(old, new) -> LockDiff` (old/new = LockFile or {path: hash} or None),
`diff_against_lock(root) -> LockDiff`, `append_only_mark(path) -> AppendOnlyMark`,
`check_append_only(root, lock) -> list[AppendOnlyProblem(path, message)]`.
`LockFile(files, laws: {id: LockedLaw(law_id, sentence, file, hash)}, append_only: {path: AppendOnlyMark(lines, prefix_sha256)}, version, generated_at, lawkeep_version)`;
`LockDiff(changed, added, removed)` with `.is_empty`, `.paths()`.

### `history.py`
- `append(root, entry) -> HistoryEntry` (fills `id`, `timestamp`); `read(root) -> list[HistoryEntry]`
  (raises `HistoryError` with the line number); `since(root, timestamp | None)`; `find(entries, id)`;
  `pending(entries)`; `latest_hashes(entries)`; `explains(entries, path, sha)`;
  `unexplained_lock_paths(lock, entries) -> list[str]`; `default_person(root=None) -> "person:<name>"`;
  `mark_session_start(root, *, agent=None) -> str`; `session_start(root) -> str | None`.
- **`record_change(root, *, action, actor, law_id=None, direction=None, reason="", permission_used="none", approved_by=None, status="applied", sentence_before=None, sentence_after=None, details=None, refers_to=None) -> RecordedChange(entry, diff, lock, notes)`**
  — the one way to change laws. Make the change on disk first, then call it. For `applied`, it
  stores every changed fingerprinted file (new hash / null) in `entry.files`, appends the entry,
  and rewrites `laws.lock`. For `waiting`/`rejected`, it only appends.
  **Gotcha:** it sweeps in *every* difference from the lock, including earlier unrecorded edits.
  Before applying a change, call `lock.diff_against_lock(root)`; if it is not empty, stop and
  report the unrecorded change (only a person's explicit "accept" may record it, with
  `action="accept_unrecorded_change"`).

### `output.py`
`emit(report, as_json, *, text=None, stream=None)`, `dumps(obj) -> str`, `to_jsonable(obj)`,
`render_text(report) -> str`, `setup_problem(command, message, as_json, *, hint=None, data=None) -> 3`
(added: `setup_problem_text(command, message, hint)` is its human screen),
`not_implemented(command, as_json) -> 3`, `plain_example(example) -> str`, `table(rows, headers=None) -> str`,
`yes_no(question, *, default=None, stream_in=None, stream_out=None) -> bool | None`
(returns `None` when stdin is not a terminal: then return `WAITING` instead of blocking; never ask in `--json` mode).

### `ui.py` and `explain.py` (added 2026-11-22)
`ui`: `console(stream=None, *, width=None, plain=None)`, `render(*items, stream=None, width=None, plain=None) -> str`,
`show(*items)`, `plain_wanted(stream)`, `banner(title, detail, tone=)`, `panel(*body, title=, tone=)`,
`table(headers, rows, ...)`, `heading`, `status(tone, text)`, `warning`, `next_step`, `dim`,
`label_value(rows)`, `ask_yes_no(question)`, `plural(n, word)`. Tones: ok, fail, wait, warn,
problem, info. `LAWKEEP_COLOR=always` forces colour.
`explain`: `probe_status(probe)`, `strength_status(result, missing=) -> Strength(tone, text, weak, measured, reason)`,
`examples_table(rows, proposal=False)`, `inputs_block`, `similar_law(sentence, approved)`,
`recommendation(probe, strength, similar)`, `draft_law_panel(...)`, `direction_text(direction)`,
`plain_explanation(text)`, `failure_lines(message, details=)`, `tidy(text)`.

### `cli.py`
Discovers `lawkeep.commands.<name>` for `COMMANDS = (init, draft, approve, check, strength, propose, report, hook, mcp)`.
Each module exposes `HELP: str`, `add_arguments(parser)`, `run(args) -> int`. `cli.py` adds `--json`
and `--root`; never edit `cli.py` to add arguments. A module that fails to import only breaks its own command.
`python -m lawkeep` and the `lawkeep` console script both call `cli.main(argv=None) -> int`.

### Packaging
`pyproject.toml`: hatchling; console script `lawkeep = lawkeep.cli:main`; pytest plugin entry point
`pytest11: lawkeep = lawkeep.pytest_plugin` (so plain `pytest` knows the `law` marker; the plugin must
stay passive unless the runner activates it). Extras: `deep` (crosshair-tool, hypothesis-crosshair),
`mcp` (mcp), `mutation` (mutmut). Dev group: pytest, ruff, pyright, tomli (so pyright can check
the Python 3.10 `tomli` import branch). The wheel ships `lawkeep/py.typed` (PEP 561).
Installed versions at foundation time:
hypothesis 6.170, pytest 9.2, coverage 7.17, crosshair-tool 0.0.114, hypothesis-crosshair 0.0.32,
mcp 2.3, mutmut 3.8.

## 6. Workstream modules (as built)

All stubs are implemented. The contract signatures below still work; additions are marked
"added".

### The law-running core (`lawrun.py`, `_lawrun_child.py`; merged 2026-11-23)

Every command that runs project code uses ONE way to run laws, in one of three modes
(decision 2026-11-22, approved 2026-11-23 as option B: merge the three ways before the first
commit):

| Mode | Callers | Child handler | What comes back |
| --- | --- | --- | --- |
| `check` | `lawkeep check` (`runner.run_laws` → `run_pytest`) | `pytest_plugin.run_check`: pytest with `-p _hypothesis_pytestplugin -p lawkeep.pytest_plugin` | one `{"type": "check", ...}` record (the gate's results), then the channel is closed |
| `strength` | `strength`, the protection report, `direction`'s planted bugs (`strength.core.run_worker`, request `kind` "map" or "probe") | `strength._worker.run`: pytest with the strength plugin (coverage contexts per law, Hypothesis statistics, in-memory swaps and planted bugs) | `law`, `coverage`, `statements`, `quick`, `mutant`, `collection_error`, `note`, `worker_error` records as they happen, then `done` |
| `probe` | example tables and direction evidence for `draft`, `approve`, `propose` (`examples_table.run_probe`) | `_probe_worker.run`: Hypothesis without pytest, a recorder per input | one `{"type": "probe", "result": ...}` record, then `done` |

- `lawrun.run(root, cfg, mode, request=None, *, pytest_targets=None, pytest_plugins=None, pytest_extra=None, extra_sys_path=None, timeout=None) -> LawRunResult`
  — the only function that starts a law-running process. Command:
  `python -I -S -B -X pycache_prefix=<empty temp dir> _boot.py <site dirs> lawkeep._lawrun_child`
  (`lawrun.python_command`), cwd = root. `_boot.py` adds site-packages and the folder lines of
  `.pth` files without running their code. Environment (`lawrun.clean_env`):
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`; `PYTEST_ADDOPTS`,
  `PYTEST_PLUGINS`, `PYTHONSTARTUP`, `PYTHONPATH`, `PYTHONHOME`, the coverage start-up
  variables and every `LAWKEEP_*` variable of the caller removed; then `LAWKEEP_ROOT`, a private
  `HYPOTHESIS_STORAGE_DIRECTORY` in the temp dir and, where `lawrun.MODES[mode].fixed_hash_seed`
  (strength, probe), `PYTHONHASHSEED=0`. The temp dir is removed afterwards; nothing is written
  into the project.
- Request: one JSON object on the child's stdin (then stdin is `/dev/null`): the mode's own
  fields plus `mode`, `root`, `work_dir`, `sys_path` (`extra_sys_path`, then
  `lawrun.sys_path_entries`: existing source folders, then the root), `source_dirs`,
  `pytest_args` for pytest modes (`lawrun.pytest_args`: `-c <empty ini> --rootdir=<root>
  --noconftest --import-mode=importlib --continue-on-collection-errors -p no:cacheprovider -q`,
  then `-p` per plugin, the extra options and the targets), and `results_fd` (POSIX) or
  `results_file` (elsewhere, untested).
- Results: JSON lines on an inherited pipe whose number is only in the request, never in the
  environment; read by a thread as they arrive, so a run killed at its time limit keeps its
  partial records. The child closes the pipe when its handler returns; the gate closes it right
  after its one record. `LawRunResult(mode, records, returncode, stdout, stderr, timed_out,
  unreadable)` with `of_type(kind)`, `first(kind)`, `finished` (a `done` record arrived) and
  `output_tail(n)`. A crash in lawkeep's own child code becomes a `fatal` record plus a
  traceback on stderr. `SetupError` only when Python cannot start ("lawkeep could not start
  Python to <MODES[mode].purpose>").
- Child (`_lawrun_child.main`): read the request, open the channel, delete every `LAWKEEP_*`
  variable except `LAWKEEP_ROOT`, put `sys_path` first on `sys.path`, set
  `sys.dont_write_bytecode`, call `HANDLERS[mode]` with `(request, channel)`. Standard library
  only until the handler runs.
- Per-mode differences kept on purpose (unchanged behaviour): the gate keeps the caller's
  `PYTHONHASHSEED`; strength runs without Hypothesis's pytest plugin (it has its own statistics
  hook) and with `-W ignore::pytest.PytestAssertRewriteWarning`; the probe does not use pytest;
  the skip / `assume()`-outside-laws rules are the gate's (strength and probe only measure).
  Shared since the merge: `pytest_plugin.load_laws_fixtures` (only the fixtures of
  `laws/conftest.py`, hooks ignored) is used by the gate and by strength, which used to register
  the whole file, hooks included.
- Gotcha: Hypothesis adds constants from every loaded module outside site-packages to the
  inputs it tries. In an editable install (this repository) lawkeep's own modules count, so
  changing which lawkeep modules a child imports can change the inputs a probe draws (seen
  once during the merge: two rows of one billing example table). Installed from a wheel,
  lawkeep lives in site-packages and does not count.

### B Gate

- `runner.run_pytest(root, cfg, targets, *, profile=None, law_ids=None, extra_plugins=None, extra_sys_path=None, extra_args=None, ledger=None, timeout=None) -> RunOutcome`
  — the `check` mode of `lawrun.run` (see above) with `runner.GATE_PLUGINS` and
  `runner.GATE_PYTEST_OPTIONS`; the request's `gate` holds `profile`, `law_ids` and, when
  given, `ledger`. Changed 2026-11-23: `extra_env` was replaced by `extra_sys_path` (folders
  before the source folders, e.g. for an `extra_plugins` module) and `ledger` ("" = replay
  nothing). Raises `SetupError` when no results record arrives or the channel holds unreadable
  lines; an unknown `law_ids` entry (in `run_laws`) raises `SetupError`. Added: `profile` may also be a
  `config.Profile` (how `--deep-check` switches the backend).
- `runner.run_laws(root, cfg, *, profile=None, law_ids=None, include_drafts=False, timeout=None) -> RunOutcome`
  (added `timeout`). A law found by reading the files that did not run gets an `error` result.
- `RunOutcome(results, notes, collection_errors, returncode, stdout, stderr, new_failures, ignored, timed_out)`
  (added the last three). The runner never writes the ledger; `check` saves `new_failures`.
- `pytest_plugin`: passive (marker only) unless `run_check(request, channel)` switched it on
  (changed 2026-11-23: no environment variable switches it on any more; the gate's settings
  come from the request: `root`, `gate.profile`, `gate.law_ids`, `gate.ledger` (`""` skips
  replaying saved failures)). Collects `@law` items whatever their names; tests in `laws/` without `@law` are
  listed as `ignored` with a note. Loads only the fixtures of `laws/conftest.py` (hooks there
  are ignored and flagged). Forces on every law: the profile's max_examples (a law may raise
  it, not lower it), all phases, the profile deadline, `print_blob` off, a fixed per-law seed
  (sha256 of the law id) on the "pr" profile, and the per-law ledger database.
- `integrity.check_integrity(root, cfg, *, base_ref=None) -> list[IntegrityIssue]` — no code runs.
- `integrity.scan_side_doors(root, *, base_ref=None, cfg=None, unrecorded=None, view=None)` (added keywords).
- `ledger.load(root)`, `ledger.add(root, law_id, example, *, found_by="lawkeep", choices=None, failure=None, profile=None)`.

### C Strength & protection

- `strength.run_strength(root, cfg, *, law_ids=None, full=False, include_drafts=False) -> StrengthReport`.
- `strength.run_quick_check(root, cfg, *, law_ids=None, include_drafts=False, sample_bugs=3) -> list[StrengthResult]`.
- `strength.catch_matrix(root, cfg, targets, *, functions=None, max_bugs=None) -> CatchMatrix`;
  `max_bugs` = at most N bugs **per function**, evenly spread. `CatchMatrix` added `tested`
  (law id → bug ids it ran against), `laws_by_function`, `failing_laws`. `PlantedBug.id` looks
  like `src/shop/refunds.py::refund#3` and is stable for the same source.
- Added: `strength.result_for(results, law_id, file=None)` (handles `id@file` keys).
- Planted bugs come from lawkeep's own ast mutator (`strength/mutants.py`, operators modelled on
  mutmut's), in memory only; the user's files are never written. `[strength] mutation_tool` is
  currently ignored (pending maintainer review: the plan said "wrap mutmut").
- `protection.changed_functions(root, cfg, *, base_ref=None)`, `protection.protection_report(root, cfg, *, base_ref=None)`;
  added `protection.change_set()` / `ChangeSet`, `parse_diff()`, `resolve_base()`. Its result
  code is always 0 (it shows; it does not block).

### D Law lifecycle

- `permissions.permission_key(action, direction)`, `permissions.decide(cfg, action, direction)`.
  Mapping (pending maintainer review): `stricter` → `add_law` (or `add_example`); `same` →
  `rename_target`; `unclear` → `change_law`; `looser` / delete / skip / fewer cases →
  `weaken_law` (always ask, even if the config was tampered with).
- `direction.decide_direction(root, cfg, law_id, old_file, new_file, *, planted_bugs=None) -> DirectionResult`
  (`LAWKEEP_DIRECTION_PLANTED_BUGS=0` turns planted bugs off). "same" needs at least one case both
  versions reject **and** `direction.rename_only(...)`: the new law differs from the old one only
  in names. Any other edit with the same results is "unclear", so a person decides (added during
  integration after `<= total` → `<= total + 1` was judged "same"). Also `static_weakening`,
  `is_skip_edit`, `DirectionResult.new_version_broken`, `bound_direction(old_src, old_qualname,
  new_src, new_qualname) -> ("looser" | "stricter", why) | None` (one moved limit in an assert:
  widened → always looser; narrowed → stricter when no tried input contradicts it),
  `direction_seed(law_id, old_source, new_source)` and `DIRECTION_EXAMPLES = 100` (the evidence
  is deterministic: same change, same inputs, same label).
- `examples_table.run_probe(..., seed=None)`: the `probe` mode of `lawrun.run` (child code in
  `_probe_worker.py`, which also holds `readable`); Hypothesis draws from `seed` (default
  `probe_seed(versions)`, a hash of the versions' files), with `PYTHONHASHSEED=0` and a private
  `HYPOTHESIS_STORAGE_DIRECTORY`.
- `examples_table.example_rows(...)`, `render_rows(rows)`; added `probe_law(root, cfg, law_file, law_id, *, count, examples, use_draft_strategies) -> LawProbe`, `run_probe(...)`.
- `agent_launcher.launch(agent, prompt, *, cwd, timeout=None, runner=None) -> LaunchResult`;
  added `build_argv`, `effective_agent`, `VERIFIED_PRESETS` (= `config.AGENT_PRESETS`),
  `DRAFTING_ENV = "LAWKEEP_DRAFTING"` (set for the drafting agent; the guard lets that session
  write `laws/strategies.py`).
- `lawchanges.changes_since`, `list_pending`, `render_since(root, since, *, integrity=None, protection=None, as_markdown=False, waiting_list=None)`
  (with `waiting_list` the closing line is the one-waiting-list count);
  added `build_report(root, since, *, integrity, protection) -> LawChangeReport`.
- `commands.propose.propose(root, cfg, law_id, *, new_text, reason, actor, delete, source_name=None) -> (ProposalResult, text)`;
  `propose.parked_next_step(pid)`.
- `waiting.collect(root, *, issues=None) -> WaitingList` (the one waiting list; static; `line()`
  is "N things wait for your decision (...) — run `lawkeep approve`."), `waiting.KINDS`,
  `LABELS`, `EXPLAIN`.
- `approvals.unconfirmed_groups(entries, also=())`, `settled_ids`, `snapshot`, `keep_copies`,
  `confirm(root, group, *, person, channel)`, `undo(...)` (both refuse while laws differ from
  `laws.lock`; only `approve` in a terminal calls them).
- `presence.detect(env=None, *, stdin_tty=None) -> Presence(present, reason)`: the
  `person_present` guess. First match: `LAWKEEP_PERSON_PRESENT` (1/0) · `CI` set → no · stdin is
  a terminal → yes · Claude Code `CLAUDE_CODE_SESSION_ATTENDED` (1/0), else
  `CLAUDE_CODE_ENTRYPOINT` `cli` → yes, `sdk-*` → no (seen in Claude Code 2.1, not a documented
  contract) · otherwise no. Codex, Cursor and Copilot set nothing lawkeep knows, so their
  interactive sessions read as "no"; the agent instructions say a person chatting in the
  session counts as present. The guess never changes what lawkeep allows.

### E Adapters

- `adapters.base.Adapter` (`name`, `detect(root)`, `install(root, *, hooks=True) -> InstallResult(agent, files_changed, notes, warnings)`),
  `all_adapters()`, `get_adapter()`, `detect_agents()`; modules `claude_code`, `codex`, `cursor`,
  `copilot`, plus `adapters/guard.py` (one decision function for every agent's pre-tool-use hook:
  `decide(payload) -> Decision(action, message, paths, root)`, `protected_rel(path, cwd)`). Shell
  commands are judged by what they write to: `adapters/shellwords.py` (`parse(command) ->
  [Command]`, a small POSIX lexer), `adapters/writes.py` (`analyse(command, cwd) -> Findings(targets,
  recursive, unsure, mentions, forced, approval)`) and `adapters/pywrites.py` (inline Python, read
  from its syntax tree). A write the guard cannot see is denied only when the command names a
  protected path or runs decoded code.
- `mcp_server.serve(root=None, *, actor=None)`, `LawkeepTools`, `build_server(root, *, actor, tools)`.
  Tools `check`, `propose`, `report` run `python -m lawkeep <cmd> --json` and return that JSON;
  `list_laws` uses static discovery. There is deliberately no `approve` tool. Proposals over MCP
  are always recorded as `agent:<name>`.
- `init` installs `adapters/templates/lawkeep-workflow.yml` (uses only inputs defined in
  `action.yml`; a test checks this).

### F CI & proof
`action.yml` (composite action: `lawkeep check --json`, then `lawkeep report` (Markdown first;
the JSON run skips the protection step when the Markdown worked, so planted bugs run once) → one
PR comment, never blocking by itself), `.github/workflows/` (`ci.yml`, `nightly.yml`,
`templates/`), two made-up `examples/`, `tests/tamper/` (cheating suite), `README.md`, `docs/site/` (the docs website; it replaced `docs/guide/` on 2026-11-24).

## 7. Commands (as built)

Every command also takes `--json` and `--root PATH`.

| Command | Owner | Arguments | Result codes |
| --- | --- | --- | --- |
| `init` | E | `[--agent claude-code\|codex\|cursor\|copilot\|all\|other\|none ...] [--no-hooks] [--ci \| --no-ci]` | 0 done · 2 laws changed outside lawkeep, or laws.lock deleted while the history has entries (nothing touched) · 3 problem |
| `draft` | D | `[module] [--request TEXT] [--docs PATH ...] [--dry-run] [--timeout N] [--actor agent:NAME]` (missing module → setup problem) | 2 drafts (or the agent's edits to approved files, now waiting proposals) waiting for a person · 1 a draft fails on today's code or is weak · 3 agent not set up, failed, or wrote nothing (and changed no approved file) |
| `approve` | D | `[ID ...] [--yes \| --no] [--by NAME] [--channel TEXT] [--accept-unrecorded]`; ID = law id, history id, or draft path/name. No ids, in a terminal: the one waiting list (five kinds), changes made outside lawkeep first, then an optional "approve all recommended new drafts and stricter changes" (only new drafts that work, are measured strong and are not likely duplicates, and stricter/same-meaning proposals; never looser, unclear, deletions, skips, weak new laws, drafting-agent edits, unrecorded changes or unconfirmed approvals; offered when at least 2 qualify), then one by one; an unconfirmed approval is answered confirm / undo / skip. With an unconfirmed approval's id in a terminal, `--yes` confirms and `--no` undoes; without a terminal it is never decided | 0 decided · 2 still waiting (no terminal / `--json` and no `--yes`/`--no`) · 1 a decision could not be applied · 3 |
| `check` | B | `[--profile NAME] [--deep-check] [--law LAW_ID ...] [--base REF] [--no-save] [--timeout SECONDS] [--details\|-v]` | 0 · 1 · 2 (integrity errors / pending decisions) · 3 |
| `strength` | C | `[--full] [--law LAW_ID ...] [--drafts] [--details\|-v]` | 0 no law flagged · 1 some law flagged (or fails today) · 3 |
| `propose` | D | `LAW_ID --file PATH --reason TEXT [--actor agent:NAME]` or `LAW_ID --delete --reason TEXT` | 0 applied · 2 waiting for a person · 1 rejected (new version broken) · 3 |
| `report` | C | `[--since ISO \| --session \| --all] [--base REF] [--no-protection] [--format text\|markdown]` | 0 · 2 if integrity errors or pending decisions · 3 |
| `hook` | E | `<event> [--agent claude-code\|codex\|cursor\|copilot\|other\|git]` (or `<agent> [event]`); events `pre-tool-use` (alias `pre-edit`), `session-start`, `session-end`, `pre-commit` | agent hooks always 0 (the decision is in the agent's own JSON; exit 2 would mean "block" to agents but "waiting" to lawkeep) · pre-commit 0, or 1 only with `git config lawkeep.precommit block` / `LAWKEEP_PRECOMMIT=block` |
| `mcp` | E | `[--agent NAME]` | 0 when the client disconnects · 3 if `mcp` is not installed |

## 8. How the modules call each other

```
check    : paths.require_root → config.load_config → integrity.check_integrity (no code runs)
           → runner.run_laws → ledger.add (new failures only) → lawchanges.list_pending
           → waiting.collect (count, never changes the result) + presence.detect
           → CheckReport(...).finalize() → output.emit
strength : config → strength.run_strength [coverage map → quick check → catch_matrix (--full)
           → vacuity / weak data → uncovered functions] → output.emit
report   : since = --since | history.session_start → lawchanges.changes_since + list_pending
           + integrity.check_integrity + protection.protection_report(base) + waiting.collect
           → LawChangeReport; text = strength.render (protection) + lawchanges.render_since
draft    : config.agent → agent_launcher.launch (agent writes laws/drafts/*.py; additive
           laws/strategies.py changes recorded (add_strategy) or parked in
           laws/drafts/strategies.py) → draft_edits.capture_and_restore (every other changed
           fingerprinted file put back) → draft_edits.make_proposals (direction.decide_direction
           per changed law → propose.park_proposal: waiting, never auto)
           → discovery.laws_in_file → examples_table.probe_law (holds today? example table)
           → strength.run_quick_check(include_drafts=True) → SimpleReport(kind="draft")
approve  : drafts / history.pending (proposals) [/ --accept-unrecorded or no ids: lock diff +
           unexplained lock paths] [/ no ids or ids: approvals.unconfirmed_groups]
           → examples_table.probe_law + strength.run_quick_check → batch_safe marks
           → output.yes_no | --yes/--no → move draft into laws/ (or apply proposal after the
           hash checks) → history.record_change(..., approved_by=person, refers_to=id)
           (no terminal: approvals.keep_copies; unconfirmed: approvals.confirm / undo)
propose  : lock.diff_against_lock (must be clean) → direction.decide_direction
           (examples_table.run_probe + strength.catch_matrix + rename_only)
           → permissions.decide → auto: write file + history.record_change(status="applied")
                                → ask : park under laws/drafts/proposals/<id>/ + waiting entry
           → ProposalResult (the --file under laws/drafts/ is removed)
init     : write lawkeep.toml (config.render_default_toml), laws/, laws/drafts/, laws/strategies.py,
           empty laws/history.jsonl and laws/failing_examples.jsonl → history.record_change(action="init")
           → .gitignore gets .lawkeep/ → shared base (AGENTS.md, pre-commit) → adapters → workflow
hook     : session-start → history.mark_session_start + presence.detect + waiting.collect (count);
           session-end → lawchanges.render_since(session_start, waiting_list=waiting.collect);
           pre-commit → integrity.check_integrity; pre-tool-use → adapters.guard.decide
mcp      : mcp_server.serve → `python -m lawkeep <cmd> --json` (check / propose / report);
           list_laws → discovery
```

## 9. Open points for the maintainer

The six foundation choices (fingerprinted `lawkeep.toml`, unrecorded change → code 2, the
permission mapping, pre-commit shows without blocking, `draft` returns 2, agent presets) and
every deviation found by the workstreams and the integration step are listed in
`docs/PLAN.md` → "Decisions", marked **(pending maintainer review)**.
