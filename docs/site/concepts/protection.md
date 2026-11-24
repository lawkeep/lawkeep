# Protection report

lawkeep's motto is **only review what your laws don't protect**. The protection report tells you
what that is.

```bash
lawkeep report --base main
```

For each function that changed since the git base, lawkeep plants small bugs in the changed lines
(in a copy of the code) and checks whether a law catches them:

| Status | Meaning |
| --- | --- |
| Protected | your laws caught every planted bug in the changed lines |
| Partly protected | they caught some |
| Not protected — read this one | they caught none, or no law runs this function |

Example (from a pull-request comment):

```text
Is the code you changed protected by laws?
  Function                     Protection                      What lawkeep found
  billing.refunds:refund       Protected                       your laws caught all 6 planted bugs
  billing.refunds:refund_v2    Not protected — read this one   no law runs this function
```

`refund_v2` is the one to read, or to ask the agent to "add a law for refund_v2 too".

## What else `lawkeep report` shows

- every law change since a point in time (`--since`, `--session` for the current agent session,
  `--all`), with who made it, why, and who approved;
- unrecorded law changes and other integrity issues;
- how many things wait for your decision.

The protection part takes a while because it plants bugs. Skip it with `--no-protection`. It never
changes the result code. `--format markdown` gives the text used for the pull-request comment.

Without `--base`, lawkeep compares with the merge-base with `main` (or `master`), plus uncommitted
changes.
