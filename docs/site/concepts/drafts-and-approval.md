# Drafts and approval

## Drafts

A **draft** is a law a coding agent wrote that nobody has approved yet. Drafts live in
`laws/drafts/`. The gate (`lawkeep check`) ignores them until a person approves them.

Drafts come from two places:

- `lawkeep draft <module> --request "..."` starts a **separate session of your own coding agent**
  (Claude Code, Codex, Cursor or Copilot; no extra account or API key). That session sees your
  request, any documents you pass with `--docs`, and the function signatures, but not the function
  bodies, so it writes the law from what you asked for rather than from what the code does today.
- An agent in your normal session can write a draft file under `laws/drafts/` and propose it.

Before you see a draft, lawkeep runs it on your current code ("does it work?") and on deliberately
broken versions of the code ("would it catch a mistake?").

The drafting session may only write new drafts and new input generators. If it edits a law you
already approved, an existing generator or `lawkeep.toml`, lawkeep puts your approved version back
and turns the edit into a waiting proposal. Such an edit is never applied on its own, even when it
would make a law stricter, and `lawkeep approve --yes` without ids never decides it.

## Approval

An **approval** is a person's yes or no, given with `lawkeep approve`. With no arguments it shows
the whole [waiting list](waiting-list.md): new drafts, proposed law changes, edits by the drafting
agent, law files changed outside lawkeep, and approvals made without a terminal.

For each item you see:

- the law's sentence (and, for a change, the sentence before and after);
- whether it works with your current code ("lawkeep tried 50 different inputs and the law was never
  broken");
- whether it is strong ("lawkeep made 6 deliberately broken versions of the code and this law
  caught all 6"), with a loud warning and "Think twice" when it is weak;
- a table of examples: the input, what the code did, and whether that follows the law;
- what each input means;
- a recommendation.

In a terminal, `approve` asks one item at a time and offers to "approve all recommended new drafts
and stricter changes" together. Anything that would loosen a law, anything unclear, anything changed
outside lawkeep and anything the drafting agent changed is never in that group: you see each of those
on its own.

Every decision is recorded in the [law history](history-and-lock.md) with the name of the person who
decided (`--by`, default: your git user name) and where (`--channel`).

## Who approved?

lawkeep records who *claimed* to approve; it cannot check who typed "yes". An approval made without a
terminal (for example by a coding agent after you confirmed its permission prompt) is recorded with
`terminal: false` and stays on the waiting list until someone in a terminal **confirms** or **undoes**
it. Undoing puts the law files back as they were. Both are recorded.

Agents are told never to run `lawkeep approve` unless you ask them to, and the agent adapters make
your coding agent ask you before it runs it. See [AI tools](../agents/index.md).

## Command summary

```bash
lawkeep approve                       # everything waiting, one by one
lawkeep approve refunds.refund_is_capped --yes   # decide one item without being asked
lawkeep approve h-1a2b3c4d --no       # reject a waiting proposal by its id
lawkeep approve --accept-unrecorded   # also decide about law files changed outside lawkeep
```

All options: [`lawkeep approve`](../reference/commands.md#lawkeep-approve).
