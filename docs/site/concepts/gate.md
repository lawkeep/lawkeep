# The gate and result codes

The **gate** is `lawkeep check`. It gives one answer for the whole project: `ALL LAWS HOLD` or
`SOME LAWS FAIL` (or that something waits for a person, or that lawkeep could not run).

## What `lawkeep check` does

1. **Integrity check, before any code runs.** Every law file is compared with `laws.lock`, and the
   lock with the history. Unrecorded law changes and side doors are flagged (see
   [Law history and lock](history-and-lock.md)).
2. **Every approved law runs in a fresh, separate Python process.** Only `laws/` is collected (never
   your normal test suite). Outside `conftest.py` files, auto-loaded pytest plugins,
   `sitecustomize.py`, `.pth` code, `PYTHONPATH` and cached bytecode are all switched off. Results
   come back through a private channel.
3. **Each law first replays its saved failing examples**, then tries new inputs. Any failure is
   shrunk to the simplest input and saved.
4. **The answer**: the verdict first, a table of laws, each failure with the input that breaks it and
   why, then the next step.

A law that skips itself while it runs counts as an error, not a pass. Checking only some laws
(`--law <id>`) says so in the result: it was a partial run.

## Profiles

A **profile** is a set of check settings:

| Profile | Inputs per law | Seed | Use |
| --- | --- | --- | --- |
| `pr` (default) | up to 200 | fixed: the same code always gets the same verdict | everyday runs and pull requests |
| `deep` | 2,000 | new each run | nightly runs that search for rare failures |

```bash
lawkeep check                  # the pr profile
lawkeep check --profile deep   # a deeper random search
```

Profiles are set in `lawkeep.toml` (`[check.pr]`, `[check.deep]`, or your own `[check.<name>]`).
See [Configuration](../reference/configuration.md).

## Result codes

Every lawkeep command returns one of four result codes, the same everywhere:

| Code | Verdict | Meaning |
| --- | --- | --- |
| 0 | `ALL LAWS HOLD` | all laws hold (other commands: done) |
| 1 | `SOME LAWS FAIL` | some laws fail, or a law could not run |
| 2 | `WAITING FOR YOUR DECISION` | something waits for a person: an unrecorded law change, a side door, a waiting proposal or draft |
| 3 | `SETUP PROBLEM` | no project, a bad `lawkeep.toml`, a missing tool, bad usage or a crash |

When several apply, the most important wins: 3, then 1, then 2, then 0. Details per command:
[Result codes](../reference/result-codes.md).

## For agents and scripts

`lawkeep check --json` prints exactly one JSON document. Each failing law has
`simplest_failing_example` and `failure_message`. An agent reads it, fixes the code, and runs `check`
again until it returns 0. See [JSON output](../reference/json.md).

## The code under test is trusted

Your code runs in the same process as the law runner. Code written on purpose to cheat could still
change the result from inside, for example by patching Hypothesis. lawkeep flags source files that
look like they do this, but flagged is not prevented. See [Known limits](../faq.md#known-limits).
