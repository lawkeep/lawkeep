# Result codes

Every lawkeep command ends with one of four result codes (exit status). They are the same for every
command, so scripts, CI and agents can rely on them.

| Code | Verdict | Meaning |
| --- | --- | --- |
| 0 | `ALL LAWS HOLD` | all laws hold (other commands: done) |
| 1 | `SOME LAWS FAIL` | some laws fail, or a law could not run |
| 2 | `WAITING FOR YOUR DECISION` | something waits for a person: an unrecorded law change, a side door, a waiting proposal or draft |
| 3 | `SETUP PROBLEM` | no project, a bad `lawkeep.toml`, a missing tool, bad usage or a crash |

- When several apply, the most important wins: **3, then 1, then 2, then 0**.
- Bad usage (an unknown option) returns 3, never 2, so 2 always means "a person needs to decide".
- In text output the verdict is the first line. In JSON it is `exit_code` plus `summary`.
- The waiting list and the protection report never change the result code on their own.

## Per command

| Command | Result codes |
| --- | --- |
| `check` | 0, 1, 2 (integrity errors or decisions waiting), 3 |
| `strength` | 0 no law flagged, 1 some law flagged (or fails today), 3 |
| `propose` | 0 applied, 2 waiting for a person, 1 rejected (the new version is broken), 3 |
| `approve` | 0 decided, 2 still waiting (no terminal or `--json`, and no `--yes`/`--no`), 1 a decision could not be applied, 3 |
| `draft` | 2 drafts (or the agent's edits to approved files) waiting for a person, 1 a draft fails on today's code or is weak, 3 the agent is not set up, failed, or wrote nothing |
| `report` | 0, 2 integrity errors or decisions waiting, 3 |
| `init` | 0 done, 2 laws changed outside lawkeep or `laws.lock` deleted while the history has entries (nothing touched), 3 |
| `hook` | agent hooks always 0 (their decision is in the agent's own JSON); `pre-commit` 0, or 1 only when set to block |
| `mcp` | 0 when the client disconnects, 3 if the `mcp` extra is not installed |

The exact text per command is also on the [Commands](commands.md) page.

## In GitHub Actions

The lawkeep action fails the job only on 3, unless you set `fail-on-broken-laws: "true"` (also fail on
1) or `fail-on-waiting: "true"` (also fail on 2). See [CI and the GitHub Action](../guides/ci.md).
