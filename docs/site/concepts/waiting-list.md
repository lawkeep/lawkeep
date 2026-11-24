# Waiting list and person present

## One waiting list

Everything that waits for a person's decision is in **one waiting list**:

| Kind | What it is |
| --- | --- |
| new drafts | laws an agent wrote that nobody approved yet |
| proposed law changes | looser or unclear changes waiting for a yes |
| changes by the drafting agent | edits the `lawkeep draft` session made to approved files |
| law files changed outside lawkeep | unrecorded law changes |
| approvals made without a terminal | a yes an agent recorded for someone; a person confirms or undoes it |

The count shows up as one line in `lawkeep check`, `lawkeep report`, the pull-request comment and at
the start and end of an agent session:

```text
3 things wait for your decision — run `lawkeep approve`
```

`lawkeep approve` shows them all, grouped and counted, with a suggestion for each kind. In JSON the
list is the field `waiting_for_person` (`count`, `ids`, `by_kind`, `items`). The waiting list never
changes a result code on its own.

## Person present

An agent working with you should **stop and ask** when a law blocks it. An agent working alone (an
overnight run, CI) cannot ask, so it should **park the change and keep going**. To choose, agents
read `person_present` in `lawkeep check --json` (also in `report`, `approve` and the session-start
hook).

It is a guess. The first matching signal wins:

| Signal | `person_present` |
| --- | --- |
| `LAWKEEP_PERSON_PRESENT=1` / `0` (set it in your overnight script) | true / false |
| `CI` is set | false |
| the command was typed in a terminal | true |
| Claude Code `CLAUDE_CODE_SESSION_ATTENDED=1` / `0` | true / false |
| Claude Code `CLAUDE_CODE_ENTRYPOINT=cli` / `sdk-*` (`claude -p`) | true / false |
| anything else (Codex, Cursor, Copilot, scripts) | false |

The Claude Code variables were seen in Claude Code 2.1, not taken from a documented contract. Other
agents set nothing lawkeep recognises, so their interactive sessions read as "nobody there"; the
agent instructions say that a person chatting with the agent counts as present.

The guess never changes what lawkeep allows: weakening a law needs a person's yes either way. See
[Long runs without a person](../guides/long-runs.md).
