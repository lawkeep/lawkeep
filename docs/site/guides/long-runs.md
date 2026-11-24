# Long runs without a person

Sometimes a coding agent works alone: overnight, on a long task, or in CI. Nobody is there to answer
"may I change this law?". lawkeep's rule for that is **park and keep going**.

## What the agent does

When a law blocks the agent and nobody is there, the agent:

1. **Parks the change.** It writes the change it needs under `laws/drafts/` and runs
   `lawkeep propose <LAW_ID> --file laws/drafts/<file>.py --reason "<why>"`. A looser or unclear
   change waits for a person; lawkeep prints an id such as `h-1a2b3c4d`.
2. **Never works around the law.** It does not edit `laws/`, `laws.lock` or `lawkeep.toml`, does not
   special-case the failing input, and never runs `lawkeep approve`.
3. **Keeps going** with every part of the task that does not depend on the blocked law, and leaves the
   parts that do depend on it undone.
4. **Ends with a summary in three lists:** done; waiting for the person (each `h-...` id, with one
   line on why); not done because a law blocked it.

When a person is there, nothing changes: the agent stops and asks. Stopping to ask is a successful
outcome, not a failure.

These rules are in the `AGENTS.md` section that `lawkeep init` writes, in Cursor's rule file and
Copilot's instructions, in the reminder at the start of each agent session, in the MCP server's
instructions and in the prompt of `lawkeep draft`.

## How an agent knows whether a person is there

Agents read `person_present` (and `person_present_reason`) in `lawkeep check --json`,
`lawkeep report --json`, `lawkeep approve --json` and the session-start hook. It is lawkeep's guess;
the first matching signal wins:

| Signal | `person_present` |
| --- | --- |
| `LAWKEEP_PERSON_PRESENT=1` / `0` (set it in your overnight script) | true / false |
| `CI` set | false |
| standard input is a terminal | true |
| Claude Code `CLAUDE_CODE_SESSION_ATTENDED=1` / `0` | true / false |
| Claude Code `CLAUDE_CODE_ENTRYPOINT=cli` / `sdk-*` (`claude -p`) | true / false |
| anything else (Codex, Cursor, Copilot, scripts) | false |

The Claude Code variables were seen in Claude Code 2.1, not taken from a documented contract. Other
agents set nothing lawkeep recognises, so their interactive sessions read as false; the instructions
say a person chatting with the agent counts as present. The guess never changes what lawkeep allows.

When a proposal waits and nobody is there, `lawkeep propose --json` adds `next_step`: "Parked as h-…
Continue with work that does not depend on this law; list h-… in your final summary …".

## One waiting list

Everything that piled up is counted in one place: new drafts, proposed law changes, edits by the
drafting agent, law files changed outside lawkeep, and approvals made without a terminal. You see
one line ("3 things wait for your decision (…) — run `lawkeep approve`") in `lawkeep check`,
`lawkeep report`, the pull-request comment and at the start and end of the next agent session. In
JSON it is the field `waiting_for_person` (`count`, `ids`, `by_kind`, `items`). It never changes a
result code; 2 still means "waiting for a person's decision".

In the morning, `lawkeep approve` shows the whole list, grouped and counted, with a suggestion for
each kind. It offers to approve the safe items together (new drafts that work and are strong, and
stricter changes); anything that would loosen a law is shown on its own.

An approval made without a terminal stays on the list until someone in a terminal confirms it or
undoes it. Undoing puts the law files back, using a copy lawkeep kept in
`laws/drafts/proposals/undo/` or the version in git; an undone draft goes back to `laws/drafts/`.

## Setting up an overnight run

Tell lawkeep nobody is there, and tell the agent what you expect:

```bash
export LAWKEEP_PERSON_PRESENT=0
claude -p "Add bulk refunds and a refund history page. If a law blocks you, park the change \
with lawkeep propose and keep going. End with: done / waiting for me / not done because blocked."
```

The next morning:

```bash
lawkeep report --all       # what changed overnight
lawkeep approve            # decide everything that waits
```
