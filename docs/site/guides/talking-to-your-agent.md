# Using lawkeep by talking to your agent

You do not need to type commands or read code to use lawkeep. You talk to your coding agent
(Claude Code, Codex, Cursor, Copilot or another), and it runs lawkeep for you. Your job is to
decide which rules matter and to say yes or no when a rule would change.

This guide follows a made-up shop owner through one week.

## The idea in one minute

- A **law** is a rule your software must always follow, written as one plain sentence:
  "A refund never exceeds the original payment."
- Your coding agent turns each sentence into an automatic check and tries it with hundreds of
  different inputs, including odd ones (a $0.01 order, a refund of exactly the full amount).
- **You decide** which laws exist. Making a law stricter can happen automatically if you allow
  it. Making a law weaker always waits for your yes.
- Every law change is **recorded**: what changed, who changed it, why, and who agreed.
- On every change, lawkeep tells you which parts of the code **no law protects**. Those are the
  only parts someone still needs to look at.

## A week with lawkeep

Priya runs the Corner Shop's online store (a made-up shop). She is not a developer. A coding
agent writes most of the shop's code.

### Monday: setting up

Priya asks her agent:

> Set up lawkeep for this project.

The agent installs lawkeep, creates a `laws` folder and a settings file, and tells her what the
default permissions are:

```
lawkeep is set up.
  The agent may add new laws and saved examples on its own, and tell you.
  Changing what a law checks waits for your yes.
  Loosening, deleting or skipping a law always waits for your yes (this cannot be turned off).
```

### Tuesday: deciding on the first laws

> Add laws for refunds: a refund can never be more than the customer paid, and a full refund
> gives back exactly what they paid.

A separate session of the agent (one that has not seen today's code changes) writes draft laws
from what Priya asked for. lawkeep then tries each draft against the real code and against
deliberately broken copies of it, to make sure the law would actually catch a mistake.

Priya is shown each draft as a sentence and a table of real examples:

```
+-  Draft law 1 of 2  ----------------------------------------------------+
| “A refund never exceeds the original payment”                           |
|                                                                         |
| + Works with your current code — lawkeep tried 50 different inputs and  |
|   the law was never broken.                                             |
| + Strong law — lawkeep made 6 deliberately broken versions of the code  |
|   and this law caught all 6.                                            |
|                                                                         |
| Examples lawkeep tried                                                  |
| Input                       What the code did              Follows    |
|                                                            the law?   |
| charge $40.00, amount $50   refund() raised RefundTooLarge Yes        |
| charge $40.00, amount $40   refund() gave 40.00            Yes        |
|                                                                         |
| What the inputs mean                                                    |
|   charge: a payment the customer made                                   |
|   amount: how much the customer asks to get back                        |
|                                                                         |
| + Recommended: approve. It works with your code and catches mistakes.   |
+-------------------------------------------------------------------------+
Approve this law? [y/N]
```

She reads the sentence and the examples, not code, and says yes. The law is now recorded with
her name.

The drafting session is only allowed to write new drafts. If it also changes a law Priya
already approved (or lawkeep's settings), that change is not thrown away and not applied:
lawkeep puts her approved version back and lists the change under "The drafting AI also
changed approved laws or settings — waiting for your review", with the law before and after
and whether it would protect more or less. It waits for her yes or no in `lawkeep approve`,
even when it would make the law stricter.

If a draft is weak, lawkeep says so in yellow, with the reason ("Weak law — lawkeep made 5
deliberately broken versions of the code and this law caught only 2 ...") and recommends
"Think twice", so she can ask for a better one.

### Wednesday: the agent changes code

Priya asks for a new feature: discount codes. The agent writes the code, adds a law on its own
("A discount code never takes the price below zero"), because adding laws is allowed
automatically, and runs the check before finishing:

```
+--------------------------------------------------+
| ALL LAWS HOLD                                    |
| All 6 of your laws held on your current code.    |
+--------------------------------------------------+
```

At the end of the session she sees one short report:

```
Law changes in this session
What happened   Law                                   Who, why and evidence
Added           “A discount code never takes the      by coding agent (claude-code)
                price below zero”                     went in without asking (your
                                                      settings allow it)
```

### Thursday: the agent wants to loosen a law

Priya asks: "No card fee on tiny refunds under $1." That conflicts with an existing law about
fees. A well-behaved agent does not quietly edit the law. It proposes a change, and lawkeep
works out by testing old and new versions on the same examples that the change is **looser**:

```
+-  Proposed law change  ----------------------------------------------+
| ! Looser — the law would allow more, so it protects less.            |
|                                                                      |
| Law now:      “Fee is always 2%”                                     |
| Would become: “Fee is 2%, or $0 for refunds under $1”                |
| Why:          your request "no fees on tiny refunds"                 |
|                                                                      |
| Input           What the code did     Old law OK?   New law OK?      |
| refund $0.50    fee() gave 0.00       NO            Yes              |
|                                                                      |
| ! Think twice: this makes the law protect less. Say yes only if you  |
|   asked for this change or agree with the reason.                    |
+----------------------------------------------------------------------+
```

Priya checks the example, agrees, and says yes. The history records the change, her request,
and her approval. Had she said no, the law would stay as it was, and the agent would have to
find another way or tell her the request is impossible.

What if the agent had edited the law file directly instead? lawkeep would notice the file no
longer matches its record and show **"unrecorded law change"** at the next check, in the end of
session report, and on the pull request, until a person decides what to do about it.

### Friday: the pull request

The shop's code lives on GitHub. When the agent opens a pull request, lawkeep posts one comment:

```
lawkeep report — SOME CHANGED CODE IS NOT PROTECTED
Is the code you changed protected by laws?
  Function                     Protection                      What lawkeep found
  billing.refunds:refund       Protected                       your laws caught all 6 planted bugs
  billing.refunds:refund_v2    Not protected — read this one   no law runs this function
Law changes in this pull request:
  Added  “A discount code never takes the price below zero”  (went in without asking)
```

`refund_v2` is a new function that no law covers yet. Priya asks the agent to "add a law for
refund_v2 too", or asks a developer friend to look at just that function, instead of reading
the whole change.

### Overnight: a long run on its own

On Friday evening Priya gives the agent a bigger job and goes home: "Add bulk refunds, a
refund history page, and no card fee on refunds under $1." Nobody is there to answer
questions. The agent follows lawkeep's rule for that, **park and keep going**:

- it builds bulk refunds and the history page, and checks that all laws hold;
- the fee part needs the fee law to change, and that would make it looser, so the agent
  **parks** the change: it proposes it with its reason, and lawkeep keeps it waiting for Priya.
  The agent does not touch the law or work around it, and it never approves anything itself;
- it ends with a short summary in three lists: **done** (bulk refunds, history page),
  **waiting for you** (the fee law change, with its id), **not done because a law blocked it**
  (no fee on tiny refunds).

On Monday morning Priya sees "1 thing waits for your decision — run `lawkeep approve`" when she
opens the session, and asks the agent: "Show me what is waiting." Everything that piled up is
in **one waiting list**, grouped and counted: new drafts, proposed law changes, changes the
drafting AI made, law files changed outside lawkeep, and approvals an agent recorded for
someone without a terminal. For each kind, lawkeep says what it means and what it suggests.
She decides one by one; when several items are safe (new drafts that work and are strong, and
stricter changes), lawkeep offers to approve those together. Anything that would loosen a law
is never in that group: she sees each of those on its own.

When Priya **is** there, nothing changes: the agent stops and asks her, as on Thursday.

### At night: the deep search

Every night lawkeep tries many more inputs than during the day. If it finds a new problem, the
report shows the simplest input that breaks the rule, and that input is saved and retried on
every check from then on. If the same bug comes back, that saved input catches it, and removing
a saved input is flagged.

## Things you can say

| You want to | Say something like |
| --- | --- |
| Start | "Set up lawkeep for this project." |
| Add a rule | "Add a law that bookings can never overlap." |
| Review waiting decisions | "Show me everything waiting for my decision." |
| Leave the agent working alone | "Work on this overnight; park anything a law blocks and give me the list in the morning." |
| Check | "Check the laws." |
| See what changed | "Which laws changed in this session?" |
| Find unprotected code | "Which parts of this change are not protected by a law?" |
| Check the laws themselves | "Are our laws strong enough? Which ones are weak?" |

## When something goes wrong

- **"SOME LAWS FAIL"**: the code does not follow one of your rules. Ask the agent to fix the code,
  not the law. It gets the exact example that breaks the rule.
- **"WAITING FOR YOUR DECISION"**: something needs your yes or no. Ask "Show me what is waiting"
  and decide each item.
- **"unrecorded law change"**: a law file was changed outside lawkeep. Ask the agent to show you
  the change, then either put it back or accept it. See
  [Handling an unrecorded law change](unrecorded-changes.md).
- **The agent wants to change a law**: it should tell you which law, show the example that fails,
  and say what it would change. You decide. See [Changing a law](changing-a-law.md).

## What lawkeep does not do

- It does not prove your software is correct. It checks exactly the laws you have, as strongly
  as it can, and tells you how strongly ("tried 200 inputs, catches 5 of 6 planted bugs").
- It does not stop an agent from editing files. It makes sure such edits are never silent.
- It does not force your team into a review process. It records and shows; you decide.
