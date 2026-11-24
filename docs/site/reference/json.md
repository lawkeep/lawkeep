# JSON output

Every command takes `--json`. It then prints **exactly one JSON document** on standard output and
nothing else, and uses the same [result code](result-codes.md). Keys are only ever added across
versions; `schema_version` is 1.

## Keys every report has

| Key | Meaning |
| --- | --- |
| `kind` | which report: `check`, `strength`, `report`, `propose`, or the command name |
| `schema_version` | `1` |
| `exit_code` | the result code |
| `summary` | one plain-English line |
| `lawkeep_version` | the lawkeep version that wrote it |

## Per command

| Command | `kind` | Main extra keys |
| --- | --- | --- |
| `check` | `check` | `profile`, `laws` (one result per law), `integrity` (issues), `waiting` (waiting proposals), `notes`, `duration_seconds`, `only_laws` (the `--law` ids; empty = every law ran), `waiting_for_person`, `person_present`, `person_present_reason` |
| `strength` | `strength` | `mode` (`quick` or `full`), `laws` (one result per law), `uncovered_functions`, `notes` |
| `report` | `report` | `since`, `changes` (law changes), `integrity`, `protection` (or null), `notes`, `waiting_for_person`, `person_present`, `person_present_reason` |
| `propose` | `propose` | `law_id`, `direction`, `decision` (`applied`, `waiting`, `rejected`, `unchanged`, `refused`), `permission_key`, `permission_value`, `reason`, `evidence`, `examples`, `history_id`, `person_present`, `next_step` |
| `init`, `draft`, `approve`, `hook`, errors | the command name | `lines` (the text lines), `data` (command-specific), `hint` |

## A law result (in `check`)

| Key | Meaning |
| --- | --- |
| `law_id`, `sentence` | which law |
| `status` | `holds`, `fails`, `error`, `skipped` or `not_run` |
| `level` | `L1`, `L2`, `L3` (see [Laws](../concepts/laws.md#levels)) |
| `examples_tried` | how many inputs were tried |
| `simplest_failing_example` | the input that breaks it, as `{name: readable value}`, or null |
| `failure_message` | why it failed |
| `duration_seconds`, `evidence`, `file`, `nodeid` | details |

## An integrity issue

`kind` (for example `unrecorded_law_change`, `side_door_file`, `skip_marker`, `source_side_door`),
`message` (plain English), `path`, `severity` (`error` makes `check` return at least 2; `warning` and
`info` are only shown) and `details`.

## The waiting list

`waiting_for_person` in `check`, `report` and `approve`: `count`, `ids` (what to type after
`lawkeep approve`), `by_kind` (`draft`, `proposal`, `draft_edit`, `unrecorded`, `unconfirmed`),
`items` and `command` (`"lawkeep approve"`).

## A typical agent loop

```bash
lawkeep check --json > result.json
```

- `exit_code` 0: done.
- 1: read `laws[]` where `status` is `"fails"`, look at `simplest_failing_example` and
  `failure_message`, fix the code, run again.
- 2: something waits for a person (`integrity`, `waiting`, `waiting_for_person`).
- 3: read `summary` and `hint`.

## Full detail

Every field of every report, including the protection report, strength results and `draft` /
`approve` data, is listed in [llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt)
section 7.
