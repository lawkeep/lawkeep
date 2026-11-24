# Configuration (`lawkeep.toml`)

`lawkeep.toml` sits at the root of your project. `lawkeep init` writes it. It is **part of your laws**:
it is fingerprinted in `laws.lock`, so a change made outside lawkeep is flagged as an unrecorded law
change, and a change that weakens the laws (for example fewer inputs) needs a person's yes.

## What `lawkeep init` writes

This is generated from lawkeep's own code (for `--agent claude-code`):

```{literalinclude} default-lawkeep.toml
:language: toml
```

## Every setting

Every key is optional.

### `[permissions]`

What a coding agent may do to your laws without asking. `"auto"` = go ahead and tell me; `"ask"` =
wait for my yes. See [Permissions by direction](../concepts/directions.md).

| Key | Default | Kind of change | Direction |
| --- | --- | --- | --- |
| `add_law` | `"auto"` | add a new law | stricter |
| `add_example` | `"auto"` | add an example or a saved failing case | stricter |
| `rename_target` | `"auto"` | update a law after a rename, when lawkeep confirms the meaning is the same | same |
| `change_law` | `"ask"` | change what a law checks | unclear |
| `weaken_law` | `"ask"` | loosen, delete or skip a law, or try fewer cases | looser; **always** `"ask"` (`"auto"` is ignored with a warning) |

### `[check]` and profiles

| Key | Default | Meaning |
| --- | --- | --- |
| `[check] profile` | `"pr"` | the profile `lawkeep check` uses without `--profile` |
| `[check.<name>] examples` | `200` (`pr`), `2000` (`deep`) | how many inputs each law tries (at least 1) |
| `[check.<name>] derandomize` | `true` (`pr`), `false` (`deep`) | a fixed seed, so the same code always gets the same verdict |
| `[check.<name>] backend` | `"hypothesis"` | or `"crosshair"` (experimental, needs `lawkeep[deep]`) |
| `[check.<name>] deadline_ms` | `0` | a time limit per input in milliseconds; 0 = none |
| `[check.<name>] seed` | — | a fixed seed; only meaningful with `derandomize = false` |

Any `[check.<name>]` table defines a profile or overrides one (`lawkeep check --profile <name>`).

### `[project]`

| Key | Default | Meaning |
| --- | --- | --- |
| `source` | `["src"]` if `src/` exists, else `["."]` | where the code under test lives |

### `[strength]`

| Key | Default | Meaning |
| --- | --- | --- |
| `quick_check` | `true` | run the quick check with deliberately broken versions |
| `min_bugs_caught` | `1` | how many deliberately broken versions a law must catch |
| `mutation_tool` | `"mutmut"` | reserved; lawkeep 0.1 uses its own small bug-planting step and ignores this |

### `[agent]`

How `lawkeep draft` starts your coding agent.

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | set by `init` | `claude-code`, `codex`, `cursor`, `copilot`, `other` or `""` |
| `command` | `""` | your own launch command; `{prompt}` or `{prompt_file}` is replaced, else the prompt goes to standard input |
| `timeout_seconds` | `900` | how long to wait for the agent |

The built-in commands per agent are on the [AI tools](../agents/index.md) pages.

## Errors and warnings

- An invalid value is a setup problem (result code 3) with a hint.
- An unknown key or section gives a warning with a "did you mean" hint.

## Environment variables

| Variable | Meaning |
| --- | --- |
| `LAWKEEP_ROOT` | the project folder, when `--root` is not given |
| `LAWKEEP_PERSON_PRESENT` | `1` / `0`: tell lawkeep whether a person is there ([Long runs](../guides/long-runs.md)) |
| `LAWKEEP_PRECOMMIT=block` | make the pre-commit hook stop commits with unrecorded law changes (or `git config lawkeep.precommit block`) |
| `LAWKEEP_COLOR=always` | force colour output |
| `NO_COLOR` | plain text output, no colour |
