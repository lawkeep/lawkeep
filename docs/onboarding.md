<!-- Generated from docs/onboarding.html by scripts/build_llms_docs.py; do not edit. -->

> Markdown version of the lawkeep onboarding guide for contributors (https://lawkeep.github.io/lawkeep/contributing/onboarding.html). The user documentation is at https://lawkeep.github.io/lawkeep/. For a compact reference written for LLMs and coding agents, read [llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt); the index of LLM-ready pages is [llms.txt](https://lawkeep.github.io/lawkeep/llms.txt).

# lawkeep onboarding guide

Everything a new developer needs to understand lawkeep: what it is for, how each part works, why it is built this way, and where to find the code. You do not need to know anything about this codebase, or about property-based testing, to start.

> **Status as of 2026-11-24**
>
> lawkeep **0.1.0 is released on PyPI (Alpha)**. All nine commands exist. CI runs on Python 3.10, 3.12 and 3.13 on Linux; macOS was never tested and Windows is not supported. The Codex, Cursor and Copilot adapters have never run inside the real agents. This guide is for people working on lawkeep's code; the user documentation is at [lawkeep.github.io/lawkeep](https://lawkeep.github.io/lawkeep/). These gaps are named again where they matter. The design source of truth is `docs/PLAN.md`. The code contract is `docs/ARCHITECTURE.md`.

## 0. How to read this guide

This guide is written for two kinds of readers at once: interns who are new to all of this, and senior developers who want exact detail.

Each topic is written in two layers:

- **The plain layer** comes first. Short sentences, analogies, and a running example. You can read only this layer and still understand the whole system.
- **The technical layer** is in boxes marked **UNDER THE HOOD**. They hold exact module and function names, data flow, file formats, process details, and design trade-offs. Click a box to open or close it. Seniors can open them all; interns can skip them on a first read.

Callout boxes mean: Tip a helpful hint, Watch out a common trap, Limit something lawkeep does not do, Example a worked example.

### The running example

> **Corner Shop billing (made up)**
>
> All through this guide we use one made-up shop. It takes card payments. The card company keeps a 2% fee. When the shop refunds a customer, it gets back the matching share of that fee. The one rule we care about most is:
>
> **"A refund never exceeds the original payment."**
>
> This project really exists in the repository as `examples/billing`. You can run every command in this guide against a copy of it.

### Learning path for interns

**Day 1: the idea**: Sections 1 and 2. Read only the plain layer. Then skim the glossary (section 10).

**Day 1: see it work**: Section 3, then run the billing example yourself (section 9, "Try it in five minutes").

**Day 2: the commands**: Section 4, plain layer. Run `check`, `strength` and `report` on a copy of the example.

**Day 3: the code**: Section 5 (architecture) and section 6 (repository tour). Now open the "Under the hood" boxes.

**Day 4: the details**: Sections 7 (data formats) and 8 (safety model). Then section 9 before you change anything.

Senior developers can go straight to section 5, then 7, 8 and 9, and use sections 2 to 4 as reference.

## 1. What lawkeep is and why it exists

### The problem

Coding agents (AI tools such as Claude Code, Codex, Cursor and Copilot) now write a lot of code. The usual safety net is tests: small programs that check the code. Tests were designed for human authors. With an AI author they fail in four ways:

1. **Examples miss cases.** A normal test checks a few inputs, for example "refund $10 of a $40 payment". The code can still be wrong for inputs nobody tried, such as a $0.25 payment.
2. **The agent can move the goalposts.** Asked to make a failing test pass, an agent may edit the test instead of the code: weaken a check, skip the test, or special-case the one input that failed. To the reviewer this looks like any other edit. Research (ImpossibleBench, CircumEval, cited in `docs/PLAN.md`) shows agents really do this.
3. **Nobody knows how strong the tests are.** A test that checks almost nothing still shows green.
4. **Nobody wants to write rules by hand.** Not even developers.

The result: a human has to read every line the agent writes. That does not scale.

### The answer: laws

lawkeep gives you **laws**. A law is a rule the code must obey for *every* input, written as one plain sentence plus an automatic check. Think of laws as the house rules of your codebase. The agent writes the code and even writes the checks, but it may not quietly rewrite the house rules.

- **Agents write laws; people decide.** A coding agent drafts each law. A person approves it by reading the sentence and a table of concrete examples, not code.
- **Every law change is recorded.** What changed, who changed it, why, and who said yes.
- **Weakening needs a person's yes.** Making a law stricter can happen on its own, if you allow it. Making it looser always waits for a person.
- **One gate.** `lawkeep check` answers `ALL LAWS HOLD` or `SOME LAWS FAIL`.
- **Laws get graded.** lawkeep plants bugs on purpose and checks whether your laws notice, so you know when a law is too weak.

> **The promise, in one line**
>
> "The AI never changes your laws silently; weakening needs your yes."

> **The headline**
>
> "**Only review what your laws don't protect.**" On every change, lawkeep shows which changed functions are protected by laws, and which ones a person still needs to read.

### What lawkeep does NOT promise

> **Limit**
>
> - It does not promise that your code is correct beyond what your laws say. A guarantee is only as strong as the laws.
> - It does not promise that an agent *cannot* get around it. The promise is "never **silently**": tricks get flagged, not made impossible.
> - Nothing in v0.1 is "proven". That word is reserved for machine-checked proofs (level L4, planned for v0.5). Never write "proven" or "foolproof" in code, docs or output.
> - It does not police your team. No forced reviews, no branch protection, no blocking by default. It records and shows; people decide.

### Where the idea comes from

The inspiration is Bend 2, a language where humans own a `LAWS.bend` file and a compiler checks proofs against it. lawkeep brings that idea to the languages and coding agents people already use, without a new language. v0.1 is Python only.

## 2. Key ideas in plain words

This section explains every idea you need, one at a time, each with the billing example.

### 2.1 Laws and property-based testing

A normal test (an "example test") says: "for *this* input, expect *this* answer". A **property** says: "for *any* input, this must be true". A law is a property with a plain-English sentence on top.

**Property-based testing** means: a tool invents many inputs for you (hundreds or thousands), runs your check on each, and reports any input that breaks it. Think of a tireless tester who tries every strange case: a $0.00 payment, a refund of exactly the full amount, a refund of one cent.

The tool lawkeep uses for this is **Hypothesis**, a well-known Python library. lawkeep does not re-invent it. It wraps it.

Here is the real law from the example (`examples/billing/laws/refunds.py`):

```text
# laws/refunds.py
from billing.refunds import RefundTooLarge, refund
from lawkeep import given, law, st

@law("A refund never exceeds the original payment")      # the sentence people read
@given(charge=st.charges(), amount=st.money(0, 1000))     # Hypothesis invents the inputs
def refund_never_exceeds_payment(charge, amount):
    try:
        result = refund(charge, amount)                   # call the real code
    except RefundTooLarge:
        return                                            # refusing a too-large refund is fine
    assert result.total <= charge.total                   # the rule itself
```

Words you will see:

- **Input**: a value lawkeep feeds the law. Here: `charge` and `amount`.
- **Generator** (Hypothesis calls it a *strategy*): a recipe for making inputs. `st.money(0, 1000)` makes amounts from $0.00 to $1,000.00. `st.charges()` is a project-specific generator defined in `laws/strategies.py`.
- **Law id**: a stable name, built from the file path inside `laws/` plus the function name: `refunds.refund_never_exceeds_payment`.

> **Tip**
>
> A law may describe its inputs in words for people: `@law("...", inputs={"charge": "a payment the customer made"})`. Without that, lawkeep says something like "a sample charge that lawkeep made up for testing" and suggests adding descriptions.

**Under the hood: The @law decorator and st**

- `src/lawkeep/_law.py`: `law(sentence, *, id=None, inputs=None)`. It does not change how the test runs. It attaches a `LawMeta` object as `__lawkeep_law__` and a pytest marker `@pytest.mark.law(...)`. Works above or below `@given`, on plain functions (an L1 example law), and on Hypothesis `RuleBasedStateMachine` classes.
- `make_law_id`: path inside `laws/` with dots, no `.py`, a leading `drafts` folder dropped (so a draft keeps its id when approved), plus the qualname. `@law(..., id="R7")` overrides.
- `src/lawkeep/strategies.py` is `st`: everything in `hypothesis.strategies`, plus `money()` (Decimal), `percentages()`, `non_empty_text()`, `ids()`. Any unknown name is looked up in the project's `laws/strategies.py`, imported once as module `lawkeep_project_strategies`. Names Hypothesis already has (`times`, `dates`, `text`) always mean Hypothesis's version.
- `src/lawkeep/__init__.py` exposes `law, given, st, example, settings, assume, note, event, get_law, is_law, LawMeta` lazily, so CLI start-up does not import Hypothesis or pytest.
- A law is *any* function or class decorated with `@law`, whatever its name. Plain pytest only collects `test_*` names, so lawkeep's pytest plugin collects `@law` items itself.

### 2.2 Shrinking and saved failing examples

When Hypothesis finds an input that breaks a law, the first one it finds is often big and messy, such as a $734.18 payment with a discount code. Hypothesis then **shrinks** it: it keeps trying smaller, simpler inputs that still break the law, until it cannot simplify further. You get the **simplest failing example**.

> **Example: the planted bug**
>
> The example ships a patch, `planted_bug.patch`, that makes a refund also hand back the fee share. With it applied, `lawkeep check` reports (in words): "The input that breaks it: a charge of $0.25 with no discount code. The law expected at most 0.25, but the code gave 0.26." A tiny, readable case that a developer (or an agent) can fix right away.

Every failing input lawkeep finds is **saved** in `laws/failing_examples.jsonl` and tried again on *every* later run, forever. Agents may add to this list but never remove from it. So a bug that was found once can never quietly come back.

**Under the hood: How replay works**

Hypothesis already knows how to replay failures: it stores the *choice sequence* (the random decisions that built the input) in an example database. lawkeep wraps that. During a gate run, each law gets its own in-memory Hypothesis database (`pytest_plugin._make_database`). Reading the law's main key returns every choice sequence saved for that law in the ledger, so Hypothesis replays them first. Entries are keyed by **law id**, not by Hypothesis's hash of the test source, so a saved failure keeps replaying after the law is edited or reformatted. New failing sequences come back to the parent, and only `commands/check.py` appends them, through `ledger.add`. The runner itself never writes the ledger, so strength and draft runs cannot pollute it.

Input values are shown in words by `src/lawkeep/readable.py`: it parses Python text such as `charge(price=Decimal('0.25'), discount_code=None)` with `ast` (never executes it) and returns "a charge of $0.25 with no discount code". "$" is used only for money-like names (price, amount, total, fee...). When unsure it returns `None` and the raw value is shown. `--details` and `--json` always keep the raw value.

### 2.3 Drafts, proposals and approval

- A **draft** is a new law a coding agent wrote that nobody has approved yet. It lives in `laws/drafts/`. The gate ignores drafts until a person approves them.
- A **proposal** is a requested change to an approved law (or its deletion). Weakening proposals wait for a person's yes.
- **Approval** is a person saying yes or no. The person sees the law's sentence, whether it works with today's code, how strong it is, and a table of real examples: "charge $40.00, refund $50 → refund() refused (RefundTooLarge) → follows the law: yes". They never have to read code.

Why a *separate* agent session writes drafts: if the same agent that wrote buggy code also wrote the law, the law might just describe the bug. So `lawkeep draft` starts a fresh session of your own coding agent and gives it what you *asked for* and the function signatures, not the function bodies.

### 2.4 Permissions by direction

Every change to a law has a **direction**:

| Direction | Meaning | Billing example | Default |
| --- | --- | --- | --- |
| **stricter** | the law demands more | add "a refund is never negative" | automatic; you are told |
| **same** | same meaning, only names changed | `refund` renamed to `issue_refund` everywhere | automatic; you are told |
| **looser** | the law demands less | "a refund never exceeds the payment plus $1" | **always asks** (cannot be turned off) |
| **unclear** | lawkeep cannot tell | the check was rewritten in a different way | asks |

lawkeep decides the direction by **evidence**, not by trusting the agent: it runs the old and new versions of the law on the same inputs and on the same deliberately broken code, and compares what each one rejects. Deleting a law, skipping it, or trying fewer cases is always "looser". The person sets the rules once in `lawkeep.toml`:

```text
[permissions]          # "auto" = go ahead and tell me; "ask" = wait for my yes
add_law       = "auto" # stricter
add_example   = "auto" # stricter (a saved case)
rename_target = "auto" # same meaning
change_law    = "ask"  # unclear
weaken_law    = "ask"  # looser: ALWAYS "ask" ("auto" is ignored with a warning)
```

> **Example from a real run while writing this guide**
>
> An agent proposed changing `<= charge.total` to `<= charge.total + 1`. Both versions gave the same answers on 200 inputs and on 40 broken versions of the code (today's code never produces such a refund). lawkeep did **not** call it "same": the check itself changed, not just names. It labelled it **unclear** and parked it for a person's yes. Being cautious here is the point.

**Under the hood: Mapping and evidence rules**

`src/lawkeep/permissions.py`: `permission_key(action, direction)` maps: looser / `remove_law` / `skip_law` → `weaken_law`; `add_example` → `add_example`; stricter → `add_law`; same → `rename_target`; anything else → `change_law`. `decide(cfg, action, direction)` forces `weaken_law` to "ask" again even if a hand-built `Config` says otherwise (`config.FIXED_ASK`).

`src/lawkeep/direction.py`: `decide_direction(root, cfg, law_id, old_file, new_file)`. Rules:

- Static weakening first (`static_weakening`, `is_skip_edit`): deletion, skip/xfail, lower `max_examples`, fewer `assert`s, added `assume()` → looser regardless of evidence.
- Evidence: inputs from both versions' generators, the `@example`s of either, and saved failing inputs; then the same inputs against deliberately broken versions of the functions the law calls; then planted bugs via `strength.catch_matrix` (switch off with `LAWKEEP_DIRECTION_PLANTED_BUGS=0`).
- new rejects a superset → stricter; same set and at least one rejection → candidate "same"; new accepts cases old rejected → looser; mixed or nothing comparable → unclear.
- "same" also needs `rename_only(...)`: a consistent one-to-one renaming of names (two old names may not become one), identical attribute/keyword names and decorators, no renamed built-ins, and a renamed outside function must no longer exist under its old name. Any other edit with equal results is unclear.
- A change to input generators or settings is never stricter or same on its own (`generators_changed`): it asks.
- A moved limit is read from the code (`bound_direction`): when the only change is one comparison in an assert (`x <= b` → `x <= b + c`, `b - c`, a changed number, `<` ↔ `<=`, `==` → `<=`/`>=`, with `c` a number literal such as `Decimal("0.05")`), the old and new accepted values are compared as intervals: wider → looser (always), narrower → stricter (when no tried input contradicts it). Multiplication, `not`, `if`, `try`/`with` around the assert, or two changed comparisons go to the evidence.
- The evidence is deterministic: Hypothesis draws from a seed made from the law id and both versions' source hashes, always 100 inputs, no example database, `PYTHONHASHSEED=0`, so the same change always gets the same label.

All of this is evidence from samples plus code rules, not proof. The reports say so.

### 2.5 Law history, fingerprints and the lock

lawkeep keeps two records:

- **`laws/history.jsonl`**, the law history: one line per law change, in order. It says what changed, which agent did it, why, which permission allowed it, and who said yes. It is **append-only**: lines are added, never edited or removed.
- **`laws.lock`**, the lock file: a **fingerprint** of every law file. A fingerprint (a SHA-256 hash) is a short code computed from a file's exact bytes. Change one character and the fingerprint changes completely. Think of it as a tamper seal on a jar.

If a law file's fingerprint no longer matches the lock, and the history does not explain the change, someone edited it without going through lawkeep. That is an **unrecorded law change**, and lawkeep flags it loudly.

What counts as "part of the laws": everything in `laws/` (including `laws/strategies.py` and `laws/conftest.py`), plus `lawkeep.toml` and `.github/workflows/lawkeep.yml`. Why the settings too? Because "try 1 input instead of 200" in `lawkeep.toml` weakens every law at once.

Lawkeep also watches for **side doors**: files that could change test results without touching a law, such as a `conftest.py` outside `laws/` (pytest loads it automatically), `sitecustomize.py` (Python runs it at start-up), `.pth` files, stale compiled `.pyc` files, and skip markers.

> **Example (verified)**
>
> In a copy of the billing example, editing `laws/refunds.py` by hand (adding `+ 1` to the limit) made `lawkeep check` say **WAITING FOR YOUR DECISION** (result code 2), "laws/refunds.py was edited directly, without lawkeep (an unrecorded law change)", naming the affected law and saying how to fix it: put the file back with git, or a person runs `lawkeep approve --accept-unrecorded`.

### 2.6 The gate and result codes

The **gate** is `lawkeep check`. It runs every approved law and gives one verdict. Every lawkeep command ends with a **result code** (also called an exit code): a number a program returns to whoever started it. Scripts, CI and agents read this number.

| Code | Verdict | Meaning |
| --- | --- | --- |
| 0 | ALL LAWS HOLD | every law held (for other commands: done) |
| 1 | SOME LAWS FAIL | at least one law broke, or could not run |
| 2 | WAITING FOR YOUR DECISION | a person must decide something: an unrecorded change, a side door, a waiting proposal |
| 3 | SETUP PROBLEM | lawkeep could not run: no project, bad settings, missing tool, crash |

When several apply, the most important wins: **3 > 1 > 2 > 0**. A setup problem hides everything. Failing laws must be fixed before a pending decision matters.

A **profile** is a set of gate settings. `pr` (the default) tries up to 200 inputs per law with a fixed seed, so the same code always gets the same verdict. `deep` tries 2,000 new random inputs each run, for nightly searches.

> **Watch out**
>
> argparse normally exits with 2 on bad command-line usage. In lawkeep, 2 means "waiting", so `cli.py` overrides it: usage errors exit with 3.

Every command also takes `--json`: then it prints exactly one JSON document and nothing else on standard output. That is what agents and scripts read.

### 2.7 Law strength

A green gate only means "the code matches the laws". What if a law checks almost nothing? lawkeep grades the laws themselves:

- **Quick check with deliberately broken versions.** lawkeep temporarily swaps each function a law calls for dumb versions: "always returns None", "always returns 0", "returns its first argument unchanged", "always raises an error". A good law should break on each of them. If it still passes, it is weak.
- **Planted bugs** (also called *mutation testing*; each changed copy is a *mutant*). lawkeep makes small changes to a copy of your code, one at a time: `<` becomes `<=`, `+` becomes `-`, a line is deleted, a function returns None. Then it checks whether any law notices.
- **Weak test data.** If most generated inputs are thrown away (for example by `assume()`), the law checks far fewer cases than it seems.
- **Coverage**: which functions each law actually runs, measured with coverage.py. Public functions no law touches are listed as gaps.

Two words lawkeep uses for weak laws:

- **One-sided**: the law checks a limit ("never more than"), not the right answer. "A refund never exceeds the payment" is one-sided: code that refuses every refund passes it.
- **Vacuous** (internally; the screen says "does not really check"): the law holds whatever the function does.

The fix for one-sided laws is a **companion law** that pins down the exact answer: "Refunding exactly what was paid gives back exactly the payment and the whole card fee". When another approved law catches every broken version a limit law lets through, lawkeep gives **companion credit**: the limit law is shown as "Fairly strong", with a note naming its companions, instead of being flagged. Drafts never count as companions, because the gate does not run them.

> **Example (verified)**
>
> `lawkeep strength` on the billing example says "NO WEAK LAWS FOUND". Four laws are "Strong". The two limit laws ("A refund never exceeds the original payment", and the discount bounds law) are "Fairly strong ... other laws catch what it lets through". Both examples now have 6 laws and no weak laws.

### 2.8 The protection report

This is the headline feature. On a change (a pull request, or an agent session), lawkeep:

1. asks git which lines changed since a base (for example `main`);
2. maps those lines to the functions they are in;
3. plants bugs only in those functions;
4. runs the laws and labels each function **Protected** (every planted bug caught), **Partly protected**, or **Not protected, read this one**.

> **Example (verified)**
>
> The example's `unprotected_change.patch` adds `refund_v2()`, a new refund function with a real bug, but no law tests it. `lawkeep check` still says ALL LAWS HOLD (the laws only test `refund()`). `lawkeep report --base HEAD` says "SOME CHANGED CODE IS NOT PROTECTED": `refund_v2()`, "Not protected — read this one", "your laws caught none of 6 planted bugs · no law runs this function". That function is exactly what a human should read.

### 2.9 The guarantee ladder

Each law is checked by the strongest method that fits, and the report names the level:

| Level | Method | Tool | In v0.1? |
| --- | --- | --- | --- |
| L1 | fixed examples only | pytest | yes |
| L2 | many generated inputs with shrinking | Hypothesis | yes (the normal case) |
| L3 | symbolic search with a solver | CrossHair | experimental (`check --deep-check`, needs `lawkeep[deep]`; not tried while writing this guide) |
| L4 | machine-checked proof | Dafny | no (v0.5). The only level allowed to say "proven". |

## 3. A day in the life

Here is the whole flow, from setup to the end of a coding session. Each step shows what the person sees and what happens inside. A non-technical person can do all of this by talking to their coding agent; the agent runs the same commands.

1. **Set up: `lawkeep init`** *You see:* "LAWKEEP IS SET UP", the files created, which agents were set up, and the next step. *Inside:* lawkeep writes `lawkeep.toml` and the `laws/` folder, records an `init` line in the history, writes the first `laws.lock`, and installs the instructions and hooks for your coding agent.
2. **Ask for laws: `lawkeep draft billing.refunds --request "refunds can never exceed the payment"`** *You see:* each draft as a box: the sentence, "works with your current code", "strong law" or a yellow "weak law" warning, and an example table. *Inside:* lawkeep builds a prompt (your request, your docs, the module's function signatures), starts a fresh session of your coding agent, and lets it write files into `laws/drafts/`. Then it runs each draft on today's code and quick-checks it. Result code 2: drafts are waiting.
3. **Decide: `lawkeep approve`** *You see:* each draft with its examples and a recommendation, then "Approve this law? [y/N]". *Inside:* on yes, the draft file moves from `laws/drafts/` into `laws/`, and lawkeep records an `add_law` history line with your name and refreshes `laws.lock`. On no, the draft is removed and the rejection recorded.
4. **Code: the agent changes `refunds.py`** *Inside:* if the agent tries to edit `laws/` directly, its pre-tool-use hook asks lawkeep, and lawkeep's guard says "deny: use `lawkeep propose`". (Only where the agent supports hooks; anything missed still shows up as an unrecorded change later.)
5. **Check: `lawkeep check`** *You see:* ALL LAWS HOLD, or SOME LAWS FAIL with "the input that breaks it" and "why it failed" for each failing law. *Inside:* integrity check first (no code runs), then all laws in a clean, isolated Python process, then new failing inputs are saved. The agent fixes the code and checks again.
6. **If a law seems wrong: `lawkeep propose`** *Inside:* the agent writes a new version of the law file under `laws/drafts/` and proposes it with a reason. lawkeep decides the direction by evidence. Stricter: applied (if allowed). Looser or unclear: parked under `laws/drafts/proposals/<id>/`, waiting for a person (result code 2). Stopping to ask is a normal, successful outcome.
7. **End of session: `lawkeep report`** *You see:* which changed functions are protected and which you must read, every law change since the session started, anything waiting for you, and anything changed outside lawkeep. *Inside:* the session start time was recorded by the agent's session-start hook in `.lawkeep/session.json`.
8. **Pull request: the GitHub Action** *Inside:* on a fresh checkout it runs `check --json` and `report --format markdown`, then posts or updates one comment. It does not block merging unless you opt in.

## 3b. Long runs without a person

Sometimes nobody is watching the coding agent: you start a big task in the evening and read the result in the morning, or the agent runs in CI. Two rules keep that safe and useful.

### Park and keep going (what the agent does)

When a law blocks the agent and nobody is there to ask, the agent:

1. **parks** the law change it needs: it writes the new version under `laws/drafts/` and runs `lawkeep propose ... --reason "why"`. A change that weakens a law (or that lawkeep cannot judge) waits for you. lawkeep answers "Parked as h-…: continue with work that does not depend on this law; list h-… in your final summary".
2. **never works around the law**: it does not edit `laws/`, does not special-case the failing input, and never runs `lawkeep approve`.
3. **keeps going** with every part of the task that does not depend on the blocked law.
4. **ends with a summary** in three lists: done; waiting for you (with the ids); not done because a law blocked it.

When you *are* there, nothing changes: the agent stops and asks you, which is a successful outcome.

### One waiting list (what you do)

In the morning, everything that piled up is in one place: run `lawkeep approve`. It shows one list, grouped and counted, each kind with a plain explanation and what lawkeep suggests:

- **new drafts**: laws an agent wrote; not checked until you approve them;
- **proposed law changes**: looser, unclear, a deletion or a skip; they need your yes;
- **changes by the drafting AI**: files it changed although it was asked to write drafts only (the approved versions are still in place);
- **law changes made outside lawkeep**: law files someone edited directly;
- **approvals made without a terminal**: an agent recorded someone's yes from its own permission prompt; you **confirm** (you did say yes) or **undo** (the law files go back to how they were; recorded).

You decide one by one. When at least two items are safe, lawkeep offers "approve all recommended new drafts and stricter changes". That batch never includes anything looser or unclear, any change by the drafting AI, any change made outside lawkeep, or any unconfirmed approval: you see each of those on its own.

You also see the count in other places: "3 things wait for your decision (…) — run `lawkeep approve`" at the start of an agent session, at the end of `lawkeep check`, in `lawkeep report` and in the pull-request comment.

> **An overnight example**
>
> At 22:00 you ask your agent: "Add bulk refunds, a refund history page, and let refunds of tiny amounts skip the fee." The tea-shop law "the fee is always 2%" blocks the last part.
>
> - The agent builds bulk refunds and the history page; `lawkeep check` says ALL LAWS HOLD for them.
> - For the fee, it proposes "the fee is 2%, or $0 under $1" with the reason "you asked for no fee on tiny refunds". lawkeep labels it **looser** and parks it as `h-3f9a1c2b`. The agent does not touch the fee code.
> - Its final message: *Done*: bulk refunds, refund history page. *Waiting for you*: h-3f9a1c2b (fee law change for tiny refunds). *Not done because blocked*: no fee on tiny refunds (needs h-3f9a1c2b).
> - At 08:00 you run `lawkeep approve`: "1 thing waits for your decision". You read the change and its examples and say yes (or no). Then you ask the agent to finish the fee part.

**Under the hood: Under the hood**

- **Is a person there?** `presence.detect` makes a documented guess, reported as `person_present` (plus `person_present_reason`) in `check --json`, `report --json`, `approve --json` and the session-start hook. First match wins: `LAWKEEP_PERSON_PRESENT=1/0`; `CI` set → no; standard input is a terminal → yes; Claude Code's `CLAUDE_CODE_SESSION_ATTENDED` (1/0), else `CLAUDE_CODE_ENTRYPOINT` `cli` → yes, `sdk-*` (`claude -p`) → no; otherwise no. The Claude Code variables were seen in version 2.1; they are not a documented contract. Codex, Cursor and Copilot set nothing lawkeep knows, so an interactive session of theirs reads as "no"; the instructions say a person chatting with the agent counts as present. The guess never changes what lawkeep allows: weakening still needs a person's yes.
- **Where the rules live:** the AGENTS.md snippet ("When no person is there"), the session-start reminder (`hook.REMINDER` + `hook.NO_PERSON`), the MCP server instructions and the `propose` tool description, Cursor's rule and Copilot's instructions (both from the snippet), and the draft prompt (the drafting agent is always alone).
- **`propose` without a person:** `ProposalResult.next_step` is "Parked as h-…. Continue with work that does not depend on this law; list h-… in your final summary …"; `person_present` is set. Exit code 2 still means "waiting for a person's decision".
- **The count:** `waiting.collect(root)` is static (no project code runs) and never raises. It is the additive JSON field `waiting_for_person` {`count`, `ids`, `by_kind`, `items`}; it is not called `waiting` because `check`'s `waiting` already means pending proposals. It never changes a result code.
- **The batch:** `approve._is_batch_safe` takes a draft only when every law in it works on today's code, is measured strong and is not a likely duplicate, and a proposal only when it is stricter or same-meaning and is not a deletion, a skip, a weak new law or a drafting-agent edit.
- **Confirm and undo:** an approval recorded with `details.terminal: false` stays on the list until a person in a terminal confirms it (`confirm_approval` history line) or undoes it (`undo_approval`: the files go back; an undone draft returns to `laws/drafts/`). To undo safely, `approve` keeps the earlier bytes of the files such an approval changed in `laws/drafts/proposals/undo/<id>/`; a copy is used only when its fingerprint matches what the append-only history says, else lawkeep looks in git, else it refuses. Neither can be done without a terminal.

## 4. Every command

There are nine commands. Seven are for people and agents. Two (`hook`, `mcp`) are plumbing that agents and git call. Every command accepts `--json` and `--root PATH` (the project folder; by default lawkeep searches upward for `lawkeep.toml`, or uses `LAWKEEP_ROOT`).

| Command | Purpose | Who runs it | Result codes |
| --- | --- | --- | --- |
| `init` | set up the project and agent adapters | person or agent, once | 0 done · 2 laws changed outside lawkeep (nothing touched) · 3 |
| `draft` | a separate agent session drafts laws | person or agent | 2 drafts waiting · 1 a draft fails today or is weak · 3 agent missing/failed/wrote nothing · 0 with `--dry-run` |
| `approve` | say yes or no to drafts and proposals | a person (or an agent after the person's yes) | 0 decided · 2 still waiting · 1 could not apply · 3 |
| `check` | the gate | everyone, often | 0 · 1 · 2 · 3 |
| `strength` | grade the laws | person, CI, agent | 0 no law flagged · 1 some law weak or failing · 3 |
| `propose` | request a law change | agent | 0 applied · 2 waiting · 1 rejected (new version broken) · 3 |
| `report` | law changes + protection report | person, agent at session end, CI | 0 · 2 decision or integrity error · 3 |
| `hook` | entry point for agent and git hooks | agents, git | agent hooks always 0 · pre-commit 0 (1 only if blocking was switched on) |
| `mcp` | MCP server for agents | agents | 0 when the client disconnects · 3 if `mcp` is not installed |

### lawkeep init

**Purpose:** make a project ready for lawkeep. Safe to run again: it only creates what is missing and never overwrites.

**Options:** `--agent claude-code|codex|cursor|copilot|all|other|none` (repeatable; default: agents whose folders are present, such as `.claude/` or `CLAUDE.md`), `--no-hooks`, `--ci` / `--no-ci` (the GitHub workflow; default only if `.github/` exists).

**Under the hood: Step by step (commands/init.py)**

1. If laws changed outside lawkeep, or `laws.lock` was deleted while the history has entries, touch nothing and return 2.
2. Write `lawkeep.toml` (`config.render_default_toml`), `laws/`, `laws/drafts/`, `laws/strategies.py` (from `adapters/templates/strategies.py`), empty `laws/history.jsonl` and `laws/failing_examples.jsonl`.
3. `history.record_change(action="init")`: first history line and first `laws.lock`.
4. Add `.lawkeep/` to `.gitignore`.
5. Shared base (`adapters/base.py`): the lawkeep section in `AGENTS.md` between `<!-- lawkeep:begin -->` markers, and the git pre-commit hook block.
6. Each chosen adapter's `install(root, hooks=...)`. For Claude Code (verified): `.claude/settings.json` hooks and permission rules, `.mcp.json`, and `@AGENTS.md` in `CLAUDE.md`.
7. With `--ci`: `.github/workflows/lawkeep.yml` from `adapters/templates/lawkeep-workflow.yml` (fingerprinted in `laws.lock`).

**Writes:** the files above. **Gotcha:** the lawkeep repository already has its own lawkeep setup (lawkeep checks itself, see section 6), so tests must run `init` in a `tmp_path` copy, never in the repository.

### lawkeep draft

**Purpose:** get draft laws written by a fresh, separate session of your own coding agent, from what you asked for. No extra account or API key is needed.

**Options:** `module` (for example `billing.refunds`), `--request TEXT`, `--docs PATH ...`, `--dry-run` (print the prompt, start nothing), `--timeout N`, `--actor agent:NAME`.

**Under the hood: Step by step (commands/draft.py, agent_launcher.py, examples_table.py)**

1. Collect the request, the docs (size-capped) and the module's **public** function signatures and docstrings, read with `ast`. Function bodies are not sent, on purpose: laws should follow what the person wants, not what the code does today. Existing law sentences are listed so the agent does not duplicate them.
2. Snapshot `laws/`, then launch the agent once, non-interactively (`agent_launcher.launch`). The command comes from `[agent]` in `lawkeep.toml` or a preset (table below). The environment variable `LAWKEEP_DRAFTING=1` tells the guard this session may write `laws/strategies.py`.
3. Keep the agent to drafts (`_handle_law_file_changes`). New generators the agent *added* to `laws/strategies.py` are recorded as `add_strategy` (stricter) when `add_law = "auto"`, otherwise parked in `laws/drafts/strategies.py` until a draft is approved. Every other change to a file `laws.lock` fingerprints (an approved law, an existing generator, `lawkeep.toml`, a helper in `laws/`) is **not thrown away and not applied**: `draft_edits.capture_and_restore` keeps the old and new content and puts the approved version back (so `check` keeps testing the approved laws and nothing is unrecorded), then `draft_edits.make_proposals` turns each changed file into one **waiting proposal** (`propose.park_proposal`, `whole_file: true`, `from_draft: true`). The direction is judged as in `propose` (`direction.decide_direction` for each changed law); settings and generator changes are "unclear" with a list of what changed. These proposals never go in on their own, not even stricter ones: the person reviews each one with `lawkeep approve`. The reason is "edited by the drafting agent during `lawkeep draft`", plus the agent's own words when it wrote a `Changed <path>: <why>` line.
4. For each draft file: find its laws (`discovery.laws_in_file`), run the probe (`examples_table.probe_law`: does it import, does it hold today, example rows), and the quick strength check (`strength.run_quick_check(include_drafts=True)`).
5. Record who drafted what in `laws/drafts/drafts.json`.

| Agent | Preset launch command (from docs; never run for real) |
| --- | --- |
| Claude Code | `claude -p --permission-mode acceptEdits {prompt}` |
| Codex | `codex exec --sandbox workspace-write {prompt}` |
| Cursor | `cursor-agent -p --force {prompt}` |
| Copilot | `copilot -p {prompt} --no-ask-user --allow-tool 'read, write(laws/drafts/*), write(laws/strategies.py)' --deny-tool 'shell, url'` (reads, and writes only drafts and `laws/strategies.py`; no shell commands or web access. Changed 2026-11-23 from `--allow-all-tools`, which allowed any shell command) |

A failing draft is shown as "either the code has a bug or the law is wrong: you decide". The agent's edits to approved files are listed under "The drafting AI also changed approved laws or settings — waiting for your review", each with the law before and after (or the changed settings / generators), the direction in plain words and its decision id; the result is 2. JSON: `data.waiting_changes`. The `--dry-run` output was verified while writing this guide; a real agent launch was not (the waiting-proposal flow is tested with a fake agent).

### lawkeep approve

**Purpose:** the only command that records a person's yes. With no ids it shows **one waiting list** of five kinds (new drafts, proposed law changes, changes by the drafting AI, law changes made outside lawkeep, approvals made without a terminal; see 3b). In a terminal it asks about each item, offers "approve all recommended new drafts and stricter changes" when at least two are safe, and asks confirm / undo / skip for an approval made without a terminal. Without a terminal (or with `--json`) it decides nothing, lists what is waiting, and returns 2.

**Options:** `ID ...` (a law id, a decision id such as `h-b4a670cd`, or a draft file), `--yes` / `--no`, `--by NAME`, `--channel TEXT` (where the yes came from, e.g. "agent permission prompt"), `--accept-unrecorded`.

> **Guard rails (an agent could run this command itself)**
>
> - `--yes` without ids never decides a weakening proposal, or a change the drafting AI made to an approved file during `lawkeep draft`. Those are approved one at a time, by id.
> - `--accept-unrecorded` without ids decides only the hand edits, with a static review of what got looser.
> - Without a terminal, `--yes` needs `--by` or `--channel`. The person is never taken from the git user name, and the entry records `terminal: false`. `check` and `report` then list it as an approval made without a terminal.

**Under the hood: Step by step (commands/approve.py)**

1. `collect`: drafts in `laws/drafts/`, pending proposals (`history.pending`: waiting entries no later entry `refers_to`), the lock diff (with no ids or `--accept-unrecorded`), and approvals made without a terminal (`approvals.unconfirmed_groups`).
2. Grade drafts: probe + quick check, plus a "likely duplicate" note when an approved sentence is almost the same (text similarity, not meaning).
3. Mark the items that may go in the batch (`_is_batch_safe`). Show the overview, then each item (`view`, built with `explain.draft_law_panel`) and ask (`_ask`, or `_choose` for confirm / undo / skip), or use `--yes`/`--no`. Changes made outside lawkeep are asked first, then the batch, then the rest.
4. Yes on a draft: move it into `laws/`, install parked generators, `history.record_change(action="add_law", approved_by=person, ...)`. Yes on a proposal: `propose.apply_proposal`, which refuses if the proposal file or the target file changed since the waiting entry recorded their hashes (for the drafting agent's edits it writes the whole file it wrote, byte for byte, or deletes it). No: remove and record `reject_draft` / a rejected entry with `refers_to`.
5. Closing screen (`_final_screen`).

The interactive terminal flow is tested with the questions answered by the test (`tests/test_lifecycle_waiting_list.py`); it was not typed through by hand. The no-terminal path (result 2) was run.

### lawkeep check

**Purpose:** the gate. Runs only the laws in `laws/`, never your normal test suite.

**Options:** `--profile NAME`, `--deep-check` (CrossHair, experimental), `--law LAW_ID` (repeatable; the result then says it was a partial run; an unknown id is a setup problem), `--base REF` (git base for side-door checks, default HEAD), `--no-save`, `--timeout SECONDS`, `--details`/`-v` (law ids, inputs tried, timings, every note).

**What the screen shows:** a verdict banner, a table of laws (sentence and Holds / Fails / Could not run / Skipped), one box per failing law with "the input that breaks it", "why it failed" in words (for example "The law expected 0.25, but the code gave 0.26."), what the inputs mean, then anything that needs a person's decision, notes, a footer (inputs per law, profile, time) and a "Next step" line. On the billing example a full run took about 2.5 seconds.

**Under the hood: Step by step (commands/check.py)**

```text
paths.require_root → config.load_config → integrity.check_integrity   # no code runs
→ runner.run_laws                       # isolated pytest process
→ ledger.add (new failures only, unless --no-save)
→ lawchanges.list_pending               # waiting proposals
→ CheckReport(...).finalize()           # fails/error → 1; integrity errors or waiting → 2; else 0
→ output.emit(report, args.json, text=render(...))
```

**Reads:** `lawkeep.toml`, `laws/`, `laws.lock`, history, ledger, git. **Writes:** only new lines appended to `laws/failing_examples.jsonl`. It never rewrites `laws.lock`. A skipped law counts as neither holding nor failing; a skip raised *while* a law runs is an error.

### lawkeep strength

**Purpose:** grade the laws (section 2.7). **Options:** `--full` (plant every bug in every function, slower), `--law ID`, `--drafts` (include drafts), `--details`.

**What the screen shows:** a banner (for example "NO WEAK LAWS FOUND"), a table: law sentence, Strong / Fairly strong / Weak, and what lawkeep found ("caught 4 of 4 deliberately broken versions; caught 3 of 3 planted bugs"), then suggestions for weak laws. Quick mode plants up to 3 bugs per function a law calls by name. On the billing example quick mode took about 4.5 seconds.

**Under the hood: Step by step (strength/core.py)**

1. **Map run**: every law runs once in an isolated worker process under coverage.py, one coverage *context* per law, with Hypothesis statistics on. Output: functions each law executes, lines it never reaches, inputs thrown away, holds today or not.
2. **Probe run**: for each law that holds, swap each function it calls by name (up to 8) for the quick-check variants (`_worker.quick_variants`: always None, always 0, always an empty value, first argument unchanged, always raises) and plant bugs (`mutants.py`), re-running the law each time. A timeout counts as caught. A per-run time limit uses SIGALRM (POSIX only).
3. Flags: all variants missed → "Vacuous: ..."; some value variants missed → "One-sided: ..."; "raises" missed → "may catch the error itself". Weak test data when at least half of generated inputs were thrown away.
4. `_credit_companions`: a one-sided flag is removed (and a note added) when other approved, non-vacuous laws catch every variant this law missed.
5. Uncovered public functions are listed.

The quick check only swaps names the law calls; the law's own parameters and local variables are excluded (`_worker.law_source_names`). Before that fix, a parameter named `charge` made it swap the function `charge()`, a false "one-sided" flag. The user's files are never written: everything happens in memory in the worker.

### lawkeep propose

**Purpose:** the only legal way for an agent to change a law. **Usage:** `lawkeep propose LAW_ID --file laws/drafts/new.py --reason "why"`, or `lawkeep propose LAW_ID --delete --reason "why"`. `--actor agent:NAME` says who.

**Under the hood: Step by step (commands/propose.py)**

1. Refuse while `laws.lock` shows an unrecorded change (decision `refused`; the proposed file is kept). Otherwise `history.record_change` would sweep the hand edit in.
2. Same text as today → `unchanged`, nothing recorded.
3. `direction.decide_direction` (section 2.4). A new version that does not import → `rejected`, result 1.
4. A **new** law must also pass the quick strength check to go in automatically; otherwise it waits.
5. `permissions.decide`. Auto: write the law, `record_change(status="applied")`, result 0. Ask: park under `laws/drafts/proposals/<history id>/` as `proposed.py.txt` (".txt" so neither the gate nor draft discovery collects it) plus `meta.json`, append a `waiting` entry with the hashes, result 2.
6. The `--file` under `laws/drafts/` is removed once recorded.

Verified: the `+ 1` proposal above was parked as `change_law` / unclear with decision id `h-...`, and the screen said "WAITING FOR YOUR YES" with the exact approve commands.

### lawkeep report

**Purpose:** one plain report for the end of a session or a pull request. **Options:** `--since ISO` / `--session` / `--all`, `--base REF`, `--no-protection`, `--format text|markdown` (markdown is what the Action posts).

**What the screen shows:** a banner, the protection table (function, Protected / Partly protected / Not protected — read this one, what lawkeep found), then the list of recorded law changes (what happened, which law, who, why, evidence), anything waiting, and integrity problems.

**Under the hood: Step by step (commands/report.py, protection.py, lawchanges.py)**

```text
since = --since | history.session_start(root) | everything
→ lawchanges.changes_since + list_pending
→ integrity.check_integrity
→ protection.protection_report(base)      # git diff → changed functions → planted bugs
→ LawChangeReport; text from strength.render + lawchanges.render_since
```

The default base is the merge-base with `origin/main`, `main`, `origin/master` or `master`. The diff includes uncommitted and untracked files, so it works mid-session. Without git, every public function is checked. Up to 20 planted bugs per changed function. The protection part only shows: by itself it never changes the result code.

### lawkeep hook

**Purpose:** what agents and git call. You never run it by hand. A **hook** is a command a tool runs automatically at a certain moment: before the agent uses a tool, when a session starts, before git makes a commit.

| Event | What it does |
| --- | --- |
| `pre-tool-use` (alias `pre-edit`) | reads the agent's hook JSON on stdin and answers in the agent's own format: deny direct edits to the laws, "ask" for `lawkeep approve`, allow everything else |
| `session-start` | writes `.lawkeep/session.json` and prints a reminder of the rules that the agent adds to its context, including what to do when nobody is there, lawkeep's guess whether a person is there, and the count of what waits for the person |
| `session-end` | prints the law change report for the session, ending with the same count |
| `pre-commit` | runs the integrity check (no project code runs) and shows problems; does not block unless `git config lawkeep.precommit block` or `LAWKEEP_PRECOMMIT=block` |

> **Why agent hooks always exit 0**
>
> To agents, exit code 2 means "block". To lawkeep, 2 means "waiting". So the hook always exits 0 and puts the decision inside its JSON output. A broken hook therefore never blocks the agent.

### lawkeep mcp

**Purpose:** an **MCP server**. MCP (Model Context Protocol) is a standard way for coding agents to call outside tools. `lawkeep mcp` offers four tools: `check`, `propose`, `report`, `list_laws`. There is deliberately **no approve tool**: a yes must come from a person.

**Under the hood: How it works (mcp_server.py)**

Needs the optional `mcp` package (`lawkeep[mcp]`), imported lazily; works with the SDK 2.x and 1.x APIs. `check`, `propose` and `report` run `python -m lawkeep <command> --json` in a fresh process and return that exact JSON, so the MCP path and the CLI path can never disagree. `list_laws` uses static discovery (no project code runs). Proposals over MCP are always recorded as `agent:<name>`. Config files fall back to `<project>/.venv/bin/lawkeep` when lawkeep is not on PATH.

## 5. Architecture

lawkeep is a coordinator. It does not test code itself. It wraps existing tools (pytest, Hypothesis, coverage.py, git, your coding agent) and adds what is missing around them: fingerprints, history, permissions, clean runs, strength checks and plain reports.

### 5.1 The big picture

Three kinds of callers (a person, a coding agent, CI) all go through the same CLI. Commands call groups of core modules. Every command that runs laws (the gate, strength and the example tables) goes through one law-running core, `lawrun.py`, which starts an isolated Python process in one of three modes: `check`, `strength` or `probe`.

Groups follow the original build workstreams in `docs/ARCHITECTURE.md` §2: A Foundation, B Gate, C Strength & protection, D Law lifecycle, E Adapters, F CI & proof. Test file prefixes follow the same split.

### 5.2 CLI and output

**What and why:** one small entry point finds every command, and every command talks to people in the same plain style. Commands are independent: a command that fails to import breaks only itself.

|  |  |
| --- | --- |
| Files | `cli.py`, `commands/*.py`, `output.py`, `ui.py`, `explain.py`, `readable.py`, `errors.py`, `exitcodes.py`, `docs/OUTPUT-STYLE.md` |
| How | `cli.COMMANDS` lists the nine names. Each module exposes `HELP`, `add_arguments(parser)`, `run(args) -> int`. `cli.py` adds `--json` and `--root`. `SetupError` (or any crash) becomes a plain message and code 3; `LAWKEEP_DEBUG=1` shows the traceback. |
| Output | Human screens are built with `ui` (Rich: colour and rounded boxes in a terminal; plain ASCII when not a terminal, with `CI`, `NO_COLOR` or `TERM=dumb`; `LAWKEEP_COLOR=always` forces colour) and the shared sentences in `explain` ("works with your current code", strong/weak, example tables, recommendations). JSON never goes through Rich: `output.emit(report, as_json, text=...)`. |
| Gotchas | Never edit `cli.py` to add arguments. Never prompt in `--json` mode or without a terminal: return 2. Keep the JSON schema stable: agents parse it. Text wraps to the terminal width (80 when not a terminal), so tests that search long phrases set `COLUMNS=200`. |

**Under the hood: The output style rules**

`docs/OUTPUT-STYLE.md` is binding for any message, error or `--help` text. In short: lead with the verdict; give every number its meaning ("lawkeep tried 46 different inputs and the law was never broken", not "46 examples"); avoid internal words ("vacuous", "mutant", "probe", "nodeid") on screen; ids and paths dim or behind `--details`; the law sentence is always the primary name; always end with "Next step:"; flag weak laws loudly; say failures in words; never "proven" or "guaranteed" below L4. The glossary there fixes the words to use ("deliberately broken versions", "one-sided", "unrecorded change"...).

### 5.3 Foundation

**What and why:** shared building blocks with no surprises: reading settings, finding the project, describing laws without running them, and one set of data shapes for every report.

|  |  |
| --- | --- |
| `config.py` | `load_config(root) -> Config`. Missing file → defaults. Invalid values → `ConfigError` (code 3). Unknown keys → warnings with a "did you mean" hint. `weaken_law = "auto"` → forced to "ask" plus a warning. Holds `AGENT_PRESETS`. |
| `paths.py` | Project root = nearest folder upward with `lawkeep.toml`, else with `laws/`. `require_root` raises `ProjectNotFound`. `rel()`: paths in data are relative, with forward slashes. |
| `discovery.py` | Finds laws by **reading** files with `ast`, never running them: sentence, id, line, source hash. Recognises aliases (`import lawkeep as lk`). Reports problems (non-literal sentence, duplicate ids). `describe_inputs` reads `@law(inputs=...)`. |
| `models.py` | Dataclasses for every report and record (`CheckReport`, `LawResult`, `IntegrityIssue`, `HistoryEntry`, `StrengthResult`, `ProtectionResult`, `ProposalResult`, `SimpleReport`...). Invalid choice values raise at construction. `to_dict()`/`from_dict()`. Timestamps: UTC ISO 8601 with microseconds and `Z`. |
| Gotcha | `discovery.py`, `lock.py` and `integrity.py` must **never** import or run project code. That is what makes the integrity check safe to run first. |

### 5.4 Lock and history

**What and why:** the memory of every law change, and the tamper seal. Without them lawkeep could not tell a recorded change from a silent one.

|  |  |
| --- | --- |
| Files | `lock.py`, `history.py` |
| Reads/writes | `laws.lock` (TOML), `laws/history.jsonl` |
| The one rule | `history.record_change(root, *, action, actor, ...)` is **the only way to change laws**. Make the change on disk first, then call it. For `applied` entries it stores every changed fingerprinted file's new hash (or null) in `entry.files`, appends the entry, and rewrites `laws.lock`. For `waiting`/`rejected` it only appends. Nothing else calls `lock.write_lock` in production code. |
| Fingerprinted | Every file under `laws/` except `laws/drafts/`, the two append-only files and caches; plus `lawkeep.toml` and `.github/workflows/lawkeep.yml`. The append-only files get a line count and a hash of exactly those lines instead. |
| Gotchas | `record_change` sweeps in *every* difference from the lock, including earlier hand edits. Always check `lock.diff_against_lock(root).is_empty` first, and stop if it is not. It also refuses to record anything while an append-only file has lost lines. |

### 5.5 The gate

**What and why:** run every law in a clean room and return one verdict. "Clean room" matters: an agent cannot help the laws pass by placing a helper file next to them, because lawkeep's run ignores those files.

**How, in plain words:** first lawkeep checks the seals (no code runs). Then it starts a brand-new Python process with strict settings, runs only the law files, and gets the results back through a private one-way channel. Finally it saves new failures and builds the report.

**Under the hood: Process isolation, exactly (the law-running core)**

Every law-running process in lawkeep is started by one function, `lawrun.run(root, cfg, mode, request, ...)`, in one of three modes: `check` (this gate), `strength` (5.7) and `probe` (example tables, 5.6). The gate's `runner.run_pytest` calls it with mode `check`. The command is the same for every mode:

```text
python -I -S -B -X pycache_prefix=<empty temp dir> _boot.py <site dirs JSON> lawkeep._lawrun_child
# request on stdin (JSON), for check mode including:
#   pytest_args: -c <empty ini> --rootdir=<root> --noconftest --import-mode=importlib \
#     --continue-on-collection-errors -p no:cacheprovider -q \
#     -p _hypothesis_pytestplugin -p lawkeep.pytest_plugin --tb=short laws/<law files>
#   gate: {profile, law_ids, ledger}   results_fd: <pipe number>
```

The child (`_lawrun_child.py`) reads the request, points stdin at `/dev/null`, removes every `LAWKEEP_*` variable except `LAWKEEP_ROOT`, puts the source folders and the root first on `sys.path`, then calls the mode's handler: `pytest_plugin.run_check`, `strength._worker.run` or `_probe_worker.run`.

- `-I` isolated mode: ignores `PYTHONPATH`, other `PYTHON*` variables, the user site folder and the current folder.
- `-S`: `site` is not imported, so no `sitecustomize.py`, `usercustomize.py` or code line of a `.pth` file runs. `_boot.py` (standard library only) then adds the site-packages folders and the plain folder lines of their `.pth` files itself, plus the fixed setuptools editable-install finder form. Other `import` lines are not run.
- `-B` and `pycache_prefix`: no bytecode is written and every `__pycache__/*.pyc` in the project is ignored, so patched bytecode is never used.
- Environment: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTHONSTARTUP`, `PYTHONPATH`, `PYTHONHOME` and coverage variables removed; every caller `LAWKEEP_*` variable dropped; only `LAWKEEP_ROOT`, a private `HYPOTHESIS_STORAGE_DIRECTORY` and (strength and probe only) `PYTHONHASHSEED=0` are set.
- `--noconftest`: no `conftest.py` is read. The plugin loads only the *fixtures* of `laws/conftest.py`; hooks there are ignored and flagged. The empty ini means the project's pytest options (e.g. `addopts = -k 'not refund'`) do not apply.
- Results: JSON lines on an inherited pipe whose number is only in the request (POSIX; a results file elsewhere, untested). The gate sends one record and closes the pipe at once; strength streams records, so a run stopped at its time limit keeps what it found. Nothing about the channel is in the environment, and no environment variable can switch the plugin on.

**The plugin** (`pytest_plugin.py`) is passive in every normal pytest run (it only registers the `law` marker through the `pytest11` entry point). When active it: collects `@law` items whatever their names; lists plain tests in `laws/` as ignored; forces the profile on each law (at least `examples` inputs, all phases, the deadline, `print_blob` off, a fixed per-law seed `sha256(law_id)` on `pr`, the per-law ledger database); records status, examples tried, the shrunk falsifying example split into arguments, failure text, time, new failing choice sequences. An `xfail` law that fails is reported as failing. A skip raised during the call, or `assume()` from outside `laws/`, is an **error**.

Why a fixed seed instead of Hypothesis's `derandomize=True`? That setting turns off the example database, so saved failing examples could not be replayed.

|  |  |
| --- | --- |
| Files | `commands/check.py`, `integrity.py`, `runner.py`, `lawrun.py`, `_lawrun_child.py`, `_boot.py`, `pytest_plugin.py`, `ledger.py` |
| Integrity check | 1 lock vs files (unrecorded change/added/removed); 2 append-only files only grew (also vs the git base); 3 lock explained by history (`lock_rewritten`); 4 discovery problems; 5 side doors (`side_door_file`, `bytecode_file`, `skip_marker`, `weakened_settings`, `laws_conftest_hook`, `site_packages_side_door`); 6 source that reaches for the runner (`source_side_door`); 7 approvals without a terminal (`approval_unconfirmed`; not flagged once a person confirmed or undid them). Severity `error` → check returns at least 2; `warning`/`info` → shown only. |
| Gotchas | Several checks compare with a git base (`HEAD` locally). Once a change is committed locally, plain `check` may not show it; `check --base main` (or CI with the PR base) does. |

### 5.6 Law lifecycle

**What and why:** everything about laws being born, changed and approved: launching the drafting agent, building example tables people can read, deciding the direction of a change, applying permissions, and summarising changes.

|  |  |
| --- | --- |
| `agent_launcher.py` | `launch(agent, prompt, *, cwd, timeout, runner=None)`. Builds argv from the preset or `[agent] command` (`{prompt}` / `{prompt_file}` placeholders, else stdin). Sets `LAWKEEP_DRAFTING=1`. Tests inject `runner` and never start a real agent. |
| `examples_table.py` | The **probe**: the law-running core in mode `probe` (child code in `_probe_worker.py`, same isolated start as the gate) swaps the law's `.hypothesis.inner_test` for a recorder, runs Hypothesis with a fixed seed, and records every input and result without stopping at the first failure. Project functions the law calls are wrapped so the table can show "refund() → 40.00"; the same wrappers return deliberately broken results for `direction`. No pytest here. |
| `direction.py` | Stricter / same / looser / unclear (section 2.4). |
| `permissions.py` | Direction → permission key → auto or ask. |
| `draft_edits.py` | After `lawkeep draft`: the drafting agent's edits to approved files (laws, existing generators, `lawkeep.toml`, helpers) are put back and become waiting proposals, one per file, never applied automatically (`capture_and_restore`, `make_proposals`, `additions_only` splits new generators from changed ones). |
| `lawchanges.py` | `changes_since`, `list_pending`, `build_report`, `render_since(..., as_markdown=)`: the law change report used by `check`, `report` and `hook session-end`. |
| Writes | `laws/drafts/*.py`, `laws/drafts/drafts.json`, `laws/drafts/strategies.py`, `laws/drafts/proposals/<id>/`, and (through `record_change`) `laws/`, history and lock. |
| Gotchas | A draft *file* is the unit of approval. `approve` trusts the hashes in the append-only history over `meta.json`. The probe sets an explicit Hypothesis seed: `derandomize` alone is not stable there, because it hashes the recorder function, whose signature holds object addresses (this made a direction label flip between runs until 2026-11-23). |

### 5.7 Strength and protection

**What and why:** grade the laws, and show which changed code no law protects. It also supplies planted-bug evidence to `direction`.

|  |  |
| --- | --- |
| Files | `strength/core.py` (`run_strength`, `run_quick_check`, `catch_matrix`, `result_for`), `strength/_worker.py` (mode `strength` of the law-running core, started by `core.run_worker`: coverage contexts, swaps, bug planting), `strength/mutants.py`, `strength/sourcemap.py` (functions ↔ files by reading code), `strength/render.py` (Rich screens and Markdown), `strength/types.py` (`PlantedBug`, `CatchMatrix`), `protection.py` |
| Reads | source files, laws, git diff. **Writes nothing** in the user's project (a test snapshots every file to prove it). |
| Planted bug ids | Stable for the same source, e.g. `src/shop/refunds.py::refund#3`, so the parent and the worker agree without sending code around. |
| Gotchas | When an approved law and its draft share an id, result keys become `"<law_id>@<file>"`: look results up with `strength.result_for`. The time limit uses SIGALRM, so no Windows. |

**Under the hood: Why lawkeep has its own mutation engine instead of mutmut**

The plan said "wrap mutmut or Cosmic Ray" (rule: wrap, don't rebuild). The build found that mutmut 3 can only be driven through its CLI; it copies the whole project into a `mutants/` folder inside the working tree, reads its own settings from the project, runs the whole test suite, and keeps its own results database. It cannot plant bugs only in chosen functions (the protection report needs exactly the changed ones), cannot say *which law* caught each bug, and does not run on Windows. So `strength/mutants.py` is a small `ast` mutator with operators modelled on mutmut's: comparison swaps (`<`↔`<=`, `==`↔`!=`, `in`↔`not in`...), arithmetic swaps (`+`↔`-`, `*`↔`/`...), boolean and constant changes, `return None`, statement deletion. Bugs exist only in memory in the worker. This choice is marked **pending maintainer review** in `docs/PLAN.md`; `[strength] mutation_tool` is currently ignored.

### 5.8 Agent adapters

**What and why:** each coding agent has its own files for instructions, hooks and MCP servers. Adapters translate lawkeep's rules into each agent's format. They are thin on purpose: the core does the work, so supporting a new agent is small.

**The shared base works with any agent:** the CLI, the MCP server, an `AGENTS.md` section, and a git pre-commit hook. Agents with their own hooks and permission prompts get more on top.

| Agent | What the adapter installs | How the person's yes for approve is asked | Verified? |
| --- | --- | --- | --- |
| Claude Code | `.claude/settings.json` (PreToolUse on Edit\|Write\|MultiEdit\|NotebookEdit\|Bash, SessionStart, `permissions.ask` rules for `lawkeep approve`), `.mcp.json`, `@AGENTS.md` in `CLAUDE.md` | hook answers "ask" + permission rules | run for real once; hook decisions re-checked while writing this guide |
| Codex | `.codex/hooks.json`, `.codex/rules/*.rules`, MCP in `.codex/config.toml`; reads `AGENTS.md` natively | rules file (Codex hooks cannot "ask") | docs and simulated payloads only |
| Cursor | `.cursor/hooks.json`, `.cursor/rules/*.mdc`, `.cursor/mcp.json` | `beforeShellExecution` hook answers "ask" | docs and simulated payloads only |
| Copilot | `.github/hooks/*.json`, `.github/copilot-instructions.md`, `.mcp.json` | hook "ask" (counts as "deny" in the cloud agent and autopilot) | docs and simulated payloads only |

**Under the hood: The guard (adapters/guard.py)**

One decision function for every agent's pre-tool-use hook. No project code runs and nothing is written. It answers **deny** for direct writes to `laws/` (except `laws/drafts/` outside `proposals/`), `laws.lock`, `lawkeep.toml` and `.github/workflows/lawkeep.yml`, with a message telling the agent to write a file under `laws/drafts/` and run `lawkeep propose`; **ask** when the command actually *runs* `lawkeep approve` (also through `uv run`, `python -m lawkeep`, `bash -c`, `xargs`, or Python's `subprocess`), never when it only mentions it in text (a here-document, a commit message, `echo`, a string in code), and not for `lawkeep approve --help`; **allow** otherwise. The ask question is written for the person and lists what would be decided, one line each, for example "lawkeep: your coding agent wants to record YOUR approval of 1 law change: • Loosen “A refund never includes a fee” → “A refund may include a fee of at most $1” (looser: protects less)", and says "Not sure? Say no" (`adapters/approve_preview.py`, which reuses `approve`'s own selection and runs no project code). It reads file paths from many possible keys (`file_path`, `path`, `target_file`...), Codex `apply_patch` bodies, and shell commands by what they *write to*: `shellwords.py` lexes the command (quotes, `$(...)`, here-documents, redirections), `writes.py` follows `cd`, variables, globs and a table of writing commands (`>`, `tee`, `rm`, `mv`, `cp`, `sed -i`, `git checkout`/`restore`/`apply`, `patch`, `find -exec`, `sh -c`, `xargs` ...), and `pywrites.py` reads inline Python's syntax tree (`open(p, "w")`, `Path.write_text`, `os.remove`, `subprocess.run` ...). Reading or merely naming `laws/` is allowed (`cat laws/x.py`, `git commit -m "update laws"`). A write it cannot see (`eval`, paths built at run time, decoded scripts) is denied only when the command names a protected path or runs decoded code. A drafting session (`LAWKEEP_DRAFTING=1`) may write `laws/strategies.py`. `commands/hook.py::agent_output` converts the decision into each agent's JSON format.

The guard is a guard rail, not a wall. Whatever it misses must still show up as an unrecorded law change in `check`. Adapters merge into the user's files, never overwrite them, and must stay idempotent (`init --agent all` twice changes nothing).

### 5.9 GitHub Action and CI

**What and why:** the same gate on every pull request, on a fresh checkout (so stale local files such as cached `.pyc` never reach it), with one comment that is updated rather than duplicated.

|  |  |
| --- | --- |
| `action.yml` | Composite action: set up Python, install lawkeep and the project, run `lawkeep check --json`, then `lawkeep report` (Markdown first; the protection step runs once), post or update one PR comment. Inputs include `working-directory`, `python-version` (3.12), `lawkeep-spec`, `install-project`, `extra-packages`, `profile`, `base-ref`, `comment`, `fail-on-broken-laws` (false), `fail-on-waiting` (false). Outputs: `result-code`, `verdict`, `summary`, `check-json`, `report-markdown`, `comment-url`. |
| Blocking | The job fails only on a setup problem (3), unless you opt in. Fork PRs have a read-only token: the report goes to the job summary. |
| This repository's CI | `.github/workflows/ci.yml`: tests on Python 3.10 / 3.12 / 3.13, ruff, pyright (type check), both examples through the gate, each planted bug failing, a self-test of the action, and the docs website build; on pull requests a first `changes` job skips the jobs whose files the change does not touch (see `.github/workflows/AGENTS.md`). `nightly.yml`: `--profile deep` on the examples. `templates/`: workflows for users to copy (never run here). |
| Not verified | None of this has run on GitHub yet. `lawkeep/lawkeep@v0` needs a release tag that does not exist yet. |

### 5.10 Tools lawkeep wraps

| Tool | Used for | Where |
| --- | --- | --- |
| pytest | finding and running laws (each law is a pytest test) | `runner.py`, `pytest_plugin.py`, `strength/_worker.py` |
| Hypothesis | generating inputs, shrinking, replaying saved failures | everywhere laws run; `st` |
| CrossHair | experimental symbolic input search (L3), as a Hypothesis backend | `check --deep-check`, extra `lawkeep[deep]` |
| coverage.py | which functions each law runs; functions no law touches | `strength/_worker.py` |
| git | what changed (protection report, side-door and append-only checks) | `protection.py`, `integrity.py` |
| Rich | terminal output | `ui.py` |
| your coding agent | writing drafts in a separate, non-interactive session | `agent_launcher.py` |
| mutmut | **not** wrapped in v0.1 (see 5.7); still an optional extra | — |

One way of running laws (merged 2026-11-23): `lawrun.py` starts every law-running process with the same isolation rules, request channel (stdin) and results pipe, in one of three modes: `check` (the gate: per-law verdicts), `strength` (`strength`, protection, planted bugs for `propose`: per-law coverage and hundreds of in-memory swaps in one process) and `probe` (example tables for `draft`, `approve`, `propose`: per-input results). The modes differ only in what runs inside the child; a new kind of law run should be a new mode, not a new way of starting Python.

## 6. A guided tour of the repository

Every project folder has a short `AGENTS.md` describing it (exceptions below). Read the one in a folder before changing anything there.

| Path | What it is |
| --- | --- |
| `AGENTS.md`, `CLAUDE.md` | rules for any agent or person working on lawkeep; **"Current state"** is the live status. `CLAUDE.md` just imports `AGENTS.md`. |
| `docs/PLAN.md` | the design source of truth: principles, concepts, scope, roadmap, risks, **Decisions** (build choices marked "pending maintainer review"), open questions |
| `docs/ARCHITECTURE.md` | the code contract: conventions, data formats, module signatures, commands, call graph |
| `docs/OUTPUT-STYLE.md` | how every command talks to people |
| `docs/site/` | the public documentation website (Sphinx, Furo, MyST Markdown): getting started, concepts, guides, AI tools, writing laws, reference; published at https://lawkeep.github.io/lawkeep/ |
| `docs/onboarding.html` | this guide (published at `/contributing/onboarding.html`) |
| `src/lawkeep/` | the package (section 5): foundation modules at the top level, plus `commands/`, `adapters/` (with `templates/`: the AGENTS.md snippet, pre-commit block, starting `strategies.py`, workflow for `init --ci`), `strength/` |
| `tests/` | 782 tests (collected 2026-11-23). Prefixes: `test_core_*`, `test_gate_*`, `test_strength_*` / `test_protection_*` / `test_report_*`, `test_lifecycle_*`, `test_adapters_*`, `test_ui_output.py` (fits 80 and 60 columns, no ANSI in plain mode, JSON keys unchanged); `*_review_fixes.py` cover the 2026-11-22 review fixes; `test_typing_fixes_*.py` cover bugs found while adding type checking (2026-11-23); `test_lawrun.py` the law-running core (every mode isolated) |
| `tests/tamper/` | the **cheating test suite** (45 tests): every known trick played against a temp git copy of `examples/billing`, each shown to be caught. `test_tamper_tricks.py` (law edits, conftest/sitecustomize/.pth/.pyc side doors, skip/xfail, fewer examples, lock and history rewrites, special-casing the failing input, routing around a law with `refund_v2`), `test_tamper_in_process.py` (tricks from inside the law process: must be defeated or flagged, never a silent pass), `test_tamper_examples.py` (the examples are consistent and fail as expected) |
| `tests/fixtures/` | made-up projects: `gate/refunds_project` (+ `buggy_refunds.py`), `strength/shop` (one deliberately one-sided law, one strong law, one uncovered function), `lifecycle/teashop` + `fake_agent.py` (stands in for a coding agent; modes good, failing, naughty, nothing, crash) + `proposals/` (stricter, looser, renamed, same-results, skip, broken...) |
| `examples/billing` | Corner Shop: charges, 2% card fee, refunds, discount codes, rounding; 6 laws; `planted_bug.patch`, `unprotected_change.patch` |
| `examples/bookings` | Riverside Barbers: one chair's appointment book with a settable clock; 6 laws; `planted_bug.patch` lets two bookings overlap |
| `examples/make_example_history.py` | wrote the examples' first lock and history (rerunning it rebuilds them as approved drafts) |
| `action.yml`, `.github/workflows/` | the GitHub Action and this repository's CI (section 5.9); `lawkeep.yml` there is lawkeep checking itself (see the box below) |
| `lawkeep.toml`, `laws.lock`, `laws/`, `.mcp.json`, `.claude/settings.json` | lawkeep's own lawkeep setup: lawkeep checks itself (see the box below) |
| `pyproject.toml`, `uv.lock`, `.python-version` | packaging (hatchling; console script `lawkeep = lawkeep.cli:main`; pytest11 entry point; extras `deep`, `mcp`, `mutation`; dev group pytest + ruff + pyright; ruff line length 100; `[tool.pyright]` type-check settings) |
| `LOCAL-SETUP.md` | machine-specific notes, not committed |

> **lawkeep checks itself**
>
> The maintainer decided on 2026-11-22 that this repository uses lawkeep on its own code ("eating our own cooking"). These files in the repository root are intentional, so keep them:
>
> - `lawkeep.toml`, `laws.lock` and `laws/`: the settings, the fingerprints and three approved laws about `lawkeep.exitcodes` (for example how `exitcodes.combine` picks one result code from several).
> - `.mcp.json` and `.claude/settings.json`: the lawkeep MCP server and the guard hook for Claude Code, plus an "ask" rule for `lawkeep approve`.
> - `.git/hooks/pre-commit` (local only) and `.github/workflows/lawkeep.yml`, which runs the action from this checkout (`uses: ./` with `lawkeep-spec: "."`).
>
> What it means for you:
>
> - **Run `uv run lawkeep check`** in the repository root before you finish; it should say ALL LAWS HOLD.
> - **Never edit the root `laws/`, `laws.lock`, `lawkeep.toml` or `lawkeep.yml` by hand.** The guard blocks coding agents from doing it, and a hand edit shows up as an unrecorded law change. To change a law, write the new version under `laws/drafts/` and run `lawkeep propose LAW_ID --file laws/drafts/... --reason "..."`; a person decides with `lawkeep approve`.
> - The guard reads shell commands too, but only stops what they *write to* a protected path: reading `laws/`, grepping for "laws" or a commit message about laws is fine. If a command builds its target at run time (`eval`, `$(...)` in a path) and also names a protected path, it is stopped; write the command so its targets are plain to see.
> - Tests never run lawkeep commands that change files with this repository as the project; they use `tmp_path` copies.

> **Where AGENTS.md files are deliberately missing**
>
> - Inside any `laws/` folder: lawkeep fingerprints every file there, so an extra file is an unrecorded law change.
> - Inside the fixture projects `tests/fixtures/<area>/<project>/`: tests copy them, and an `AGENTS.md` changes what `lawkeep init` finds.
> - The repository's own lawkeep setup (root `laws/`, `.claude/`; see "lawkeep checks itself" above), and generated folders (`.venv`, `__pycache__`, `.hypothesis`, caches).

## 7. Data formats

All of these live in the user's project. Paths inside them are relative with forward slashes. Timestamps are UTC with microseconds and `Z`.

### The project layout on disk

```text
lawkeep.toml                  settings + permissions          fingerprinted
laws.lock                     fingerprints (TOML)             written only by history.record_change
laws/*.py                     approved laws                   fingerprinted
laws/strategies.py            project input generators        fingerprinted
laws/conftest.py              law fixtures (optional)         fingerprinted
laws/history.jsonl            law history, append-only        line count + prefix hash in laws.lock
laws/failing_examples.jsonl   saved failing inputs, append-only
laws/drafts/                  drafts + pending proposals      NOT fingerprinted, ignored by the gate
.lawkeep/session.json         local session marker            not committed, not protected
```

Commit everything except `.lawkeep/`.

### lawkeep.toml

```text
[permissions]              # see section 2.4
add_law = "auto"
weaken_law = "ask"         # always ask

[check]
profile = "pr"             # default profile
[check.pr]                 # any [check.<name>] table defines a profile
examples    = 200          # Hypothesis max_examples per law
derandomize = true         # fixed seed: same code → same verdict
# backend = "crosshair"    # L3, experimental; deadline_ms = 0; seed = ...
[check.deep]
examples    = 2000
derandomize = false

[project]
source = ["src"]           # code under test (default "src" if it exists, else ".")

[strength]
quick_check     = true
min_bugs_caught = 1
# mutation_tool = "mutmut"   # currently ignored

[agent]                    # how `draft` starts your agent
name = "claude-code"       # claude-code | codex | cursor | copilot | other
# command = "..."          # override; {prompt} / {prompt_file}; else stdin
timeout_seconds = 900
```

### laws.lock

```text
# laws.lock - written by lawkeep; do not edit by hand.
version = 1
generated_at = "2026-11-22T10:20:39.937575Z"
lawkeep_version = "0.1.0.dev0"

[files]                                     # every fingerprinted file → sha256 of its bytes
"lawkeep.toml" = "sha256:3c14…"
"laws/refunds.py" = "sha256:d0ae…"

[laws."refunds.refund_never_exceeds_payment"]   # per law, from static discovery
sentence = "A refund never exceeds the original payment"
file = "laws/refunds.py"
hash = "sha256:…"                           # the law's own source incl. decorators

[append_only."laws/history.jsonl"]
lines = 7                                   # lines present when the lock was written
prefix_sha256 = "sha256:…"                  # hash of exactly those lines
```

### laws/history.jsonl

One JSON object per line, keys sorted, append-only. A real waiting entry from the `+ 1` proposal, shortened:

```text
{"action": "change_law",               // init, add_law, add_example, rename_target, change_law,
                                       // remove_law, skip_law, reject_draft, accept_unrecorded_change, add_strategy,
                                       // change_settings, change_strategy, change_law_file,
                                       // confirm_approval, undo_approval...
 "actor": "agent:claude-code",          // agent:…, person:…, or "lawkeep"
 "approved_by": null,                   // person:<name> once someone says yes
 "details": {
   "evidence": "both versions gave the same answer on 200 inputs and on 40 deliberately broken versions…",
   "permission_key": "change_law",
   "proposal_path": "laws/drafts/proposals/h-b4a670cd/",
   "base_sha256": "sha256:d0ae…",        // target file when proposed
   "proposal_sha256": "sha256:0721…",    // approve refuses if either changed
   "target_file": "laws/refunds.py"},   // the drafting agent's edits also add from_draft, whole_file, kind, changes, diff
 "direction": "unclear",                // stricter | same | looser | unclear | null
 "files": {},                           // hashes AFTER the change (applied entries only)
 "id": "h-b4a670cd",
 "law_id": "refunds.refund_never_exceeds_payment",
 "permission_used": "ask",              // auto | ask | none
 "reason": "allow a dollar of slack",
 "refers_to": null,                     // the waiting entry an approve/reject decides
 "sentence_after": null, "sentence_before": null,
 "status": "waiting",                   // applied | waiting | rejected
 "timestamp": "2026-11-22T17:2…Z", "v": 1}
```

Pending decisions are `waiting` entries that no later entry `refers_to`. Approvals record `details.channel` and `details.terminal`.

### laws/failing_examples.jsonl (the ledger)

A real line saved by `check` with the planted bug:

```text
{"choices": "QRlBAEEZ",                       // base64 Hypothesis choice sequence (replayed)
 "choices_format": "hypothesis-choices",
 "example": {"amount": "Decimal('0.25')",
             "charge": "charge(price=Decimal('0.25'), discount_code=None)"},
 "failure": "AssertionError: assert Decimal('0.26') <= Decimal('0.25')",
 "found_by": "lawkeep",
 "hypothesis_version": "6.170.17",
 "law_id": "refunds.refund_never_exceeds_payment",
 "profile": "pr", "ts": "2026-11-22T17:17:13.113745Z", "v": 1}
```

Deduplicated by `(law_id, choices)`. Lines without `choices` are shown but cannot be replayed.

> **Known gap**
>
> A failing example that `check` just saved, but that is not yet committed or recorded in `laws.lock`, can still be deleted without a flag. Once committed, git protects it.

### Proposals

`laws/drafts/proposals/<history id>/proposed.py.txt` (the complete new law file) and `meta.json` (`history_id`, `law_id`, `action`, `direction`, `delete`, `target_file`, `qualname`, `base_sha256`, `proposal_sha256`, `actor`, `reason`). `approve` trusts the copy of the hashes in the history, not `meta.json`.

### .lawkeep/session.json

```text
{"started_at": "2026-11-22T09:58:32.932391Z", "agent": "claude-code"}
```

### JSON reports

Every command with `--json` prints one document. The first keys are always `kind`, `schema_version` (1), `exit_code`, `summary`, `lawkeep_version`.

| Command | `kind` | Extra keys |
| --- | --- | --- |
| check | `check` | `profile`, `root`, `laws` [LawResult], `integrity` [IntegrityIssue], `waiting` [LawChange], `notes`, `started_at`, `duration_seconds`, `only_laws`, `laws_known`, `waiting_for_person` {count, ids, by_kind, items}, `person_present`, `person_present_reason` |
| strength | `strength` | `mode` (quick\|full), `laws` [StrengthResult], `uncovered_functions`, `notes` |
| report | `report` | `since`, `changes` [LawChange], `integrity`, `protection` (ProtectionReport or null), `notes`, `waiting_for_person`, `person_present`, `person_present_reason` |
| propose | `propose` | `law_id`, `direction`, `decision` (applied\|waiting\|rejected\|unchanged\|refused), `permission_key`, `permission_value`, `reason`, `evidence`, `examples`, `history_id`, `person_present`, `next_step` |
| init, draft, approve, hook, errors | command name | `lines`, `data`, `hint` |

A real `LawResult` from the billing example:

```text
{"law_id": "discount_amounts.discount_takes_off_exactly_what_it_promises",
 "sentence": "Each discount code takes off exactly what it promises: …",
 "status": "holds",                 // holds | fails | error | skipped | not_run
 "level": "L2",
 "examples_tried": 203,
 "simplest_failing_example": null,  // {arg: repr} when it fails
 "failure_message": null,
 "duration_seconds": 0.1279,
 "evidence": {"profile": "pr", "backend": "hypothesis", "seed": 9787404417585985909,
              "derandomize": true, "max_examples": 200, "explicit_examples": 3,
              "saved_failures_replayed": 0, "inputs_thrown_away": 0,
              "stop_reason": "settings.max_examples=200"},
 "file": "laws/discount_amounts.py",
 "nodeid": "laws/discount_amounts.py::discount_takes_off_exactly_what_it_promises"}
```

The full list of item shapes (`IntegrityIssue` kinds, `StrengthResult`, `ProtectionResult`, `LawChange`, `ExampleRow`) is in `docs/ARCHITECTURE.md` §4.6. Change it only by adding, never by silently renaming.

## 8. The safety model

lawkeep assumes an agent might try to make failing laws pass without fixing the code. Its job is to make every such attempt **visible**. Here is each defence, what it catches, and where it lives.

| Trick | Defence | Where |
| --- | --- | --- |
| edit a law, a generator or `lawkeep.toml` | fingerprints vs `laws.lock` → unrecorded law change (code 2); the guard hook denies the edit up front where the agent supports hooks | `integrity.py`, `lock.py`, `adapters/guard.py` |
| edit the law *and* rewrite `laws.lock` by hand | the lock must be explained by the history (`lock_rewritten`) | `history.unexplained_lock_paths` |
| delete a history line or saved failure | append-only line count + prefix hash, and the git base | `lock.check_append_only` |
| `conftest.py` outside `laws/`, `sitecustomize.py`, `.pth` | never loaded or run (`--noconftest`, `-I -S`), and flagged | `lawrun.py`, `_lawrun_child.py`, `_boot.py` |
| patched `.pyc` files | ignored (`-B`, empty `pycache_prefix`) and flagged | `integrity.check_bytecode` |
| skip / xfail / "try 1 case" | flagged; skips raised at run time are errors; profile minimum forced; such edits are "looser" in `propose` | `pytest_plugin.py`, `direction.py` |
| project pytest options that deselect laws | empty ini, `-c`, plugin autoload off | `runner.py` |
| special-case the printed failing input | Hypothesis keeps searching and finds a different simplest input; saved inputs are replayed | Hypothesis, `ledger.py` |
| write a new function no law tests | protection report: "Not protected — read this one" | `protection.py` |
| code under test that imports pytest/Hypothesis/lawkeep, reads `LAWKEEP_*`, raises skips, always-true comparisons, shadows a module | flagged as `source_side_door` (error if changed since the git base) | `integrity.scan_source` |
| rewrite results at exit (e.g. an `atexit` hook) | results travel through a pipe written once and closed (its number is never in the environment); `LAWKEEP_*` removed before project code imports | `lawrun.py`, `_lawrun_child.py`, `pytest_plugin.py` |
| an agent approves its own change | approve needs ids for weakening, records `terminal: false`, listed by check/report; the agent's own permission prompt asks the person; no MCP approve tool | `commands/approve.py`, adapters |

### Known limits, stated honestly

> **Limit: the code under test is trusted**
>
> Laws call your code in the same Python process as lawkeep's law runner. Code written to cheat (for example by patching Hypothesis from inside) could change results. lawkeep flags suspicious source files and makes cheating harder, but flagged is not prevented. Read flagged files before trusting a green result.

> **Limit: approvals are not authenticated**
>
> lawkeep records who *claimed* to approve. It cannot check who typed "yes". If nobody remembers saying yes, undo the change.

> **Limit: "same" and "stricter" are evidence, not proof**
>
> They come from sample inputs, broken versions and planted bugs, plus code rules.

> **Limit: other edges**
>
> - Objects whose `==` or `<=` always say yes pass equality and bound laws; only comparison methods that visibly return a constant are flagged.
> - Git decides what is "new": a local commit hides some flags from plain `check` (use `--base`).
> - A law that throws most inputs away checks fewer cases; the report says how many were thrown away.
> - The guard reads shell commands on a best-effort basis.
> - Untested: Windows (hooks and the MCP launcher are POSIX `sh`, the strength timer uses SIGALRM, the results pipe is POSIX-only), Python other than 3.12, Codex/Cursor/Copilot in real use, the Action on GitHub.

## 9. How to develop on lawkeep

### Setup

```text
cd lawkeep
uv sync                    # creates .venv, installs lawkeep in editable mode + dev tools
uv sync --all-extras       # also CrossHair, mcp, mutmut (what CI uses)
uv run lawkeep --help
```

**uv** is the Python package and environment manager this project uses. `uv run X` runs X inside the project's environment.

### Try it in five minutes

```text
cp -r examples/billing /tmp/billing && cd /tmp/billing
git init -q && git add -A && git commit -qm base
cd -   # back to the lawkeep checkout
uv run lawkeep check    --root /tmp/billing            # ALL LAWS HOLD, exit 0
uv run lawkeep strength --root /tmp/billing            # NO WEAK LAWS FOUND
(cd /tmp/billing && git apply planted_bug.patch)
uv run lawkeep check    --root /tmp/billing; echo $?   # SOME LAWS FAIL, 1
```

> **Work on copies of examples/, never in place**
>
> Always try commands on copies. Editing anything under an example's `laws/` or its `lawkeep.toml` breaks its fingerprints. In the repository root, `uv run lawkeep check` is fine (lawkeep checks itself), but do not run `init`, `draft` or `propose` there unless you mean to change lawkeep's own laws.

### Tests, lint and type check

```text
uv run pytest tests/test_gate_runner.py      # one file while you work
uv run pytest                                # whole suite: 542 tests, about 6-7 minutes
uv run pytest tests/tamper -rxX              # cheating suite, 45 tests, a few minutes
uv run ruff check src tests && uv run ruff format --check src tests
uv run pyright                               # type check: must say 0 errors
uv run lawkeep check                         # lawkeep's own laws: ALL LAWS HOLD
```

- The slow tests (gate, strength, lifecycle, tamper) start real isolated Python processes.
- Tests run with `--import-mode=importlib` and there is no shared `conftest.py`, on purpose: put helpers in your own test file.
- Use `tmp_path` copies only. Run subprocesses with `cwd=tmp_path`.
- Never call a real coding agent or the network: inject runners or use `tests/fixtures/lifecycle/fake_agent.py`.
- Never add files inside a fixture project, and never put a `conftest.py` anywhere a test project is copied from: this repository's own pytest run would load it.

### Type checking with pyright

Python does not check types before it runs: if a function expects a number and gets `None`, you only find out when that line runs, maybe in a user's project. A **type checker** reads the code without running it and checks that every value fits the type written next to it (`def refund(amount: int) -> int`), so many mistakes show up in your editor or in CI instead. lawkeep uses **pyright**, the checker behind VS Code's Python support (Neovim users often run **basedpyright**, which reads the same settings).

- **Command:** `uv run pyright`. It must report `0 errors`; CI runs it next to ruff, with the pyright version pinned in `uv.lock`.
- **Strict mode for the package:** `src/lawkeep` is checked in *strict* mode: every function has types, and no value may be "unknown". An empty list needs its element type (`out: list[str] = []`). JSON read from disk goes through `models.as_dict` / `models.as_list`, so its shape is checked where it enters.
- **Standard mode for tests:** tests are checked less strictly, but a function that can return `None` still needs `assert value is not None` before you use the value.
- **Silencing an error** is rare and always names the rule and the reason: `# pyright: ignore[reportPrivateUsage] # pytest has no public API for this`. Plain `# type: ignore` is switched off.
- **py.typed:** the package contains an empty file `src/lawkeep/py.typed`. It tells type checkers in other people's projects "this package has type hints, use them", so people writing laws get completions and type errors for `law`, `given` and `st`.
- The settings live in `[tool.pyright]` in `pyproject.toml`. Adding type checking found real bugs, now covered by `tests/test_typing_fixes_*.py`.

### The rules for anyone (person or agent) working here

1. **Follow the plan.** If a change departs from `docs/PLAN.md`, ask the maintainer, or update the plan in the same change and say so.
2. **Open questions stay open.** Items under "Open questions" need a human decision.
3. **Honest wording.** Never "proven" or "foolproof" below L4. Never claim the AI *cannot* get around lawkeep.
4. **Fit the team, don't police it.** No features that force a team process; stricter enforcement is optional and off by default.
5. **Wrap, don't rebuild.** Use Hypothesis, CrossHair, mutation testers and Dafny. If wrapping is impractical, say why (as with mutmut).
6. **No private code.** Examples and tests use made-up projects only.
7. **Every folder has an `AGENTS.md`.** When you add a folder, add one; when you change a folder's code, update it in the same change.
8. **Keep `AGENTS.md` "Current state" and `docs/PLAN.md` "Decisions" current.**

### How to add things

#### A new command

1. Create `src/lawkeep/commands/<name>.py` with `HELP`, `add_arguments(parser)` and `run(args) -> int`.
2. Add the name to `cli.COMMANDS` (and `DEFAULT_HELP`). Do not add arguments in `cli.py`.
3. Pattern: `root = paths.require_root(args.root); cfg = config.load_config(root)`, build a report from `models`, build the human text only when `not args.json` (with `ui` and `explain`, banner first, `ui.next_step` last), `output.emit(report, args.json, text=...)`, return the code.
4. Raise `errors.SetupError(msg, hint=...)` for setup problems. Show `cfg.warnings`. Never prompt in JSON mode or without a terminal.
5. Document it in `docs/ARCHITECTURE.md` §7, the guides and `commands/AGENTS.md`; add tests.

#### A new agent adapter

1. Add `src/lawkeep/adapters/<agent>.py` implementing the `Adapter` protocol (`name`, `detect(root)`, `install(root, *, hooks=True)`), merging into existing files and staying idempotent.
2. Register it in `base.AGENT_ORDER` and `base.all_adapters()`; add a preset to `config.AGENT_PRESETS`; teach `commands/hook.py::agent_output` its hook format and `guard.py` its tool names and path keys if new.
3. Write down which formats you checked against which docs, and say plainly what was not run in the real agent.

#### A new integrity check

1. Add it to `integrity.py` without running project code (hash, read text, or `ast`).
2. Choose severity carefully: `error` makes `check` return 2.
3. List the new `kind` in `docs/ARCHITECTURE.md` §4.6.
4. Add a trick to `tests/tamper/` that first shows the trick really works on plain pytest, then that lawkeep catches it. Never weaken an assertion to make it pass; if lawkeep genuinely misses it, fix the product or mark it `xfail` with the reason and list it as not done in `AGENTS.md`.

### Where decisions are recorded

`docs/PLAN.md` → "Decisions" (dated table). Choices made during the build are marked **(pending maintainer review)**: for example the fingerprinted `lawkeep.toml`, unrecorded change → code 2, the permission mapping, the strict meaning of "same", the own mutation engine, the three ways of running laws, the agent presets, and the output redesign. Don't treat them as settled; don't silently reverse them either.

## 10. Glossary and FAQ

- **Adapter**: The small piece of lawkeep that installs instructions, hooks and the MCP server for one coding agent.
- **Append-only**: A file where lines may only be added. lawkeep's history and saved failures are append-only.
- **Approval**: A person's recorded yes or no on a draft or proposal (`lawkeep approve`).
- **Coding agent**: An AI tool that changes code (Claude Code, Codex, Cursor, Copilot...).
- **Companion law / companion credit**: A law that pins down the exact answer next to a limit law. When companions catch everything a limit law misses, the limit law is "Fairly strong" instead of weak.
- **Coverage**: Which lines and functions ran during a test, measured with coverage.py.
- **CrossHair**: A tool that picks inputs by reasoning about the code with a solver (L3, experimental).
- **Deliberately broken version**: A dumb stand-in for a function ("always returns 0") used by the quick check.
- **Direction**: Whether a law change is stricter, same, looser or unclear.
- **Draft**: A law an agent wrote that nobody approved yet. Ignored by the gate.
- **Exit code / result code**: The number a command returns: 0 hold, 1 fail, 2 waiting, 3 setup problem.
- **Fingerprint**: A SHA-256 hash of a file's bytes. Any change changes it.
- **Gate**: `lawkeep check`: one verdict for all laws.
- **Generator / strategy**: A Hypothesis recipe for making inputs (`st.money()`).
- **Hook**: A command a tool runs automatically at a moment (before a tool call, at session start, before a commit).
- **Hypothesis**: The Python property-based testing library lawkeep wraps.
- **Integrity check**: The part of `check` that compares fingerprints, history and side doors. No project code runs.
- **Law**: A rule the code must obey for every input: one sentence plus an executable check, in `laws/`.
- **Law history**: `laws/history.jsonl`: every law change, who, why, who said yes.
- **Ledger**: `laws/failing_examples.jsonl`: every failing input ever found.
- **Lock**: `laws.lock`: the fingerprints of all law files.
- **MCP**: Model Context Protocol: a standard way for agents to call tools. `lawkeep mcp` offers check, propose, report, list_laws.
- **Mutation / planted bug / mutant**: A copy of the code with one small deliberate change, used to see whether laws notice.
- **One-sided**: A law that checks a limit, not the right answer.
- **Probe**: The isolated process that records each input and result for example tables.
- **Profile**: A set of gate settings: `pr` (repeatable) or `deep`.
- **Property-based testing**: Testing a rule against many generated inputs instead of a few hand-picked ones.
- **Proposal**: A requested change to an approved law (`lawkeep propose`).
- **Protection report**: Which changed functions laws protect, and which a person must read.
- **Shrinking**: Simplifying a failing input until it is as small as possible.
- **Side door**: A file that could change test results without touching a law (`conftest.py`, `sitecustomize.py`, `.pth`, `.pyc`, skip markers).
- **Unrecorded law change**: A law file changed without going through lawkeep.
- **Vacuous**: Internal word for a law that holds whatever the code does.

### FAQ

#### Does lawkeep run my normal tests?

No. `check` runs only the laws in `laws/`. Your existing tests stay as they are.

#### Can an agent just edit the law file?

It can try. Where the agent supports hooks, the guard denies the edit. If it gets through anyway (for example through a shell trick the guard did not recognise), the next `check` says WAITING FOR YOUR DECISION and names the unrecorded change. Never silently.

#### Why does check return 2 and not 1 for a hand edit?

Because the laws may all hold; what is missing is a person's decision. 1 is reserved for laws that break.

#### Why are drafts not checked by the gate?

Nobody has agreed to them yet. A draft that fails could mean the code is buggy or the law is wrong; a person decides.

#### Will the same code always get the same verdict?

With the `pr` profile, yes: each law uses a fixed seed derived from its id, plus the saved failures. The `deep` profile uses new random inputs each run.

#### Do I need an API key for `draft`?

No. It starts your own coding agent's CLI in a separate session. The launch commands are taken from each agent's docs and have not yet been run for real.

#### Does the GitHub Action block merges?

No, not by default. Set `fail-on-broken-laws: "true"` or `fail-on-waiting: "true"` to opt in.

#### Does lawkeep work on Windows, or with TypeScript?

Not in v0.1. Windows is untested and parts are POSIX-only. Other languages come last on the roadmap (v0.6).

#### What is on the roadmap?

v0.2 real apps (database laws, permission laws, free laws, a fast agent profile), v0.3 fake outside services and replay, v0.4 race conditions, v0.5 Dafny proofs (L4), v0.6 other languages, v1.0 stable formats and an optional strict mode. No dates are set.

### What could not be verified for this guide

> **Unverified while writing (2026-11-22)**
>
> - `draft` with a real coding agent (only `--dry-run` was run), and the interactive terminal flow of `approve`.
> - The Codex, Cursor and Copilot adapters inside the real agents; the Action and workflows on GitHub.
> - `check --deep-check` (CrossHair) and `strength --full`.
>
> Verified by running in temporary copies: `init`, `draft --dry-run`, `check` (pass, planted bug, hand edit), `strength`, `propose` (unclear → waiting), `approve --json` without a terminal, `report --base HEAD` with `refund_v2`, and the Claude Code guard hook's deny/ask answers.

lawkeep onboarding guide · written 2026-11-22 against the uncommitted v0.1 code · Apache-2.0 project. When the code changes, update this file with it (see `docs/AGENTS.md`).
