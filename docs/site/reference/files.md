# Files and formats

## Project layout

```text
lawkeep.toml                    settings and permissions             fingerprinted in laws.lock
laws.lock                       fingerprints (TOML)                  written only by lawkeep
laws/                           approved laws and helpers            fingerprinted (every file)
laws/strategies.py              your input generators (st.*)         fingerprinted
laws/conftest.py                law fixtures (optional)              fingerprinted
laws/history.jsonl              law history, append-only             line count + hash in laws.lock
laws/failing_examples.jsonl     saved failing inputs, append-only    line count + hash in laws.lock
laws/drafts/                    drafts and waiting proposals         not fingerprinted, ignored by the gate
laws/drafts/proposals/<id>/     one waiting proposal
.lawkeep/                       local state (session marker)         not committed, not protected
.github/workflows/lawkeep.yml   the lawkeep workflow (with --ci)     fingerprinted
```

Commit everything except `.lawkeep/`.

- **Project folder**: the nearest folder upward with `lawkeep.toml`, else the nearest with `laws/`.
  `--root PATH` or `LAWKEEP_ROOT` sets where the search starts.
- **Law files**: every `*.py` under `laws/` except `strategies.py`, `conftest.py` and `drafts/`. A law
  is any function or class marked with `@law`, whatever its name.
- **Fingerprinted**: every file under `laws/` except `laws/drafts/`, the two append-only files and
  caches (`__pycache__`, `.hypothesis`, `*.pyc` ...), plus `lawkeep.toml` and the lawkeep workflow.

## `laws.lock`

TOML, written only by lawkeep (together with a history entry). Do not edit it.

```toml
# laws.lock - written by lawkeep; do not edit by hand.
version = 1
generated_at = "2026-11-21T10:00:00.000000Z"
lawkeep_version = "0.1.0"

[files]                                  # every fingerprinted file -> sha256 of its bytes
"lawkeep.toml" = "sha256:<64 hex>"
"laws/refunds.py" = "sha256:<64 hex>"

[laws."refunds.refund_is_capped"]        # per law, found without running code
sentence = "A refund never exceeds the original charge"
file = "laws/refunds.py"
hash = "sha256:<64 hex>"                 # the law's own source

[append_only."laws/history.jsonl"]
lines = 12                               # lines present when the lock was written
prefix_sha256 = "sha256:<64 hex>"        # hash of exactly those lines
```

## `laws/history.jsonl`

One JSON object per line, append-only. The main keys:

| Key | Meaning |
| --- | --- |
| `id` | `"h-<8 hex>"`, unique; the id you pass to `lawkeep approve` |
| `timestamp` | UTC, ISO 8601 |
| `action` | `init`, `add_law`, `add_example`, `rename_target`, `change_law`, `remove_law`, `skip_law`, `change_settings`, `reject_draft`, `accept_unrecorded_change`, `confirm_approval`, `undo_approval`, ... |
| `law_id` | the law affected, or null |
| `direction` | `stricter`, `same`, `looser`, `unclear` or null |
| `actor` | who made the change: `agent:<name>`, `person:<name>` or `lawkeep` |
| `reason` | why |
| `permission_used` | `auto`, `ask` or `none` |
| `approved_by` | `person:<name>` when a person said yes |
| `status` | `applied`, `waiting` or `rejected` |
| `sentence_before`, `sentence_after` | the law's sentence before and after |
| `files` | fingerprinted files changed by this entry, with their new hash (null = deleted) |
| `details` | evidence, examples and other details |
| `refers_to` | the id of the waiting entry this entry decides |

## `laws/failing_examples.jsonl`

Every failing input `check` found, one per line, append-only. Lines with Hypothesis's recorded
choices are replayed for that law on every later check, keyed by law id, so a saved failure survives
edits to the law. Main keys: `ts`, `law_id`, `found_by`, `example` (a readable form of the input),
`choices`, `failure`, `profile`.

## Full detail

The complete formats, with every key, are in
[llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt) section 8 and in the code contract
[docs/ARCHITECTURE.md](https://github.com/lawkeep/lawkeep/blob/main/docs/ARCHITECTURE.md).
