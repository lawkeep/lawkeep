# lawkeep

[![PyPI](https://img.shields.io/pypi/v/lawkeep)](https://pypi.org/project/lawkeep/)
[![Python versions](https://img.shields.io/pypi/pyversions/lawkeep)](https://pypi.org/project/lawkeep/)
[![CI](https://github.com/lawkeep/lawkeep/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lawkeep/lawkeep/actions/workflows/ci.yml?query=branch%3Amain)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Typed: pyright strict](https://img.shields.io/badge/typed-pyright%20strict-blue)](https://github.com/microsoft/pyright)
[![Downloads](https://img.shields.io/pypi/dm/lawkeep)](https://pypi.org/project/lawkeep/)
[![Docs](https://img.shields.io/badge/docs-lawkeep.github.io-blue)](https://lawkeep.github.io/lawkeep/)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/lawkeep/lawkeep/badge)](https://securityscorecards.dev/viewer/?uri=github.com/lawkeep/lawkeep)

**Only review what your laws don't protect.**

lawkeep is an open-source layer for AI-assisted coding. You decide on a short list of *laws*:
rules your code must obey for every input, each with one plain-English sentence. Your coding
agent writes and maintains the checks behind them. lawkeep records every law change, asks you
before any law gets weaker, runs one gate that says `ALL LAWS HOLD` or `SOME LAWS FAIL`, and
shows you which changed code no law protects, so that is the only code you still need to read.

> **Status: lawkeep 0.1.0 is released on [PyPI](https://pypi.org/project/lawkeep/) (Alpha).**
> Commands and file formats may still change. Read the [known limits](#known-limits) before you
> rely on it. Documentation: **[lawkeep.github.io/lawkeep](https://lawkeep.github.io/lawkeep/)**.

## The promise, honestly

- **Every law runs** on every `lawkeep check` (unless you name single laws with `--law`, and then
  the result says it was a partial run), against many generated inputs, and every failure comes
  with the simplest input that breaks it. A law that skips itself while it runs counts as an
  error, not a pass.
- **The AI never changes your laws silently.** Every law change is recorded: what changed, which
  agent changed it, why, and who said yes. A change made by editing files directly is flagged
  as an unrecorded law change.
- **Weakening a law needs your yes.** Stricter changes can go ahead automatically if you allow
  it; loosening, deleting or skipping a law, or trying fewer cases, waits for a person. lawkeep
  decides the direction from evidence (sample inputs and planted bugs) plus a few code rules;
  when it cannot tell, it asks.
- **lawkeep tells you when your laws are too weak** to catch real bugs (it plants bugs and
  checks whether any law notices). A new law must pass this quick check before it goes in
  without asking.

What lawkeep does **not** promise: that your code is correct beyond what your laws say, or that
an agent *cannot* get around it. lawkeep records and shows; it does not force a review process
on your team. Nothing in v0.1 is "proven": that word is reserved for machine-checked proofs
(level L4, planned for v0.5).

### Known limits

These are the honest edges of v0.1. Each is shown to you when lawkeep can see it, but none is
made impossible:

- **The code under test is trusted.** Laws call your code in the same Python process as
  lawkeep's law runner, so code written to cheat could change the results from inside (for
  example by patching Hypothesis). lawkeep flags source files that import lawkeep, pytest or
  Hypothesis, read lawkeep's settings, raise skips, or shadow a standard-library or installed
  module, and results travel through a private channel that is closed before your code's
  clean-up runs. Flagged is not prevented: read flagged files before trusting a green result.
- **Approvals record who claimed to approve.** lawkeep cannot check who typed "yes". Approvals
  made without a terminal (for example by an agent after its permission prompt) are recorded as
  such and stay on the `lawkeep approve` list until someone in a terminal confirms or undoes
  them (both are recorded).
- **"Is a person there?" is a guess.** Agents use it to choose between stopping to ask and
  parking a change for later. lawkeep reads `LAWKEEP_PERSON_PRESENT`, `CI`, whether the command
  was typed in a terminal, and two Claude Code variables; other agents' interactive sessions
  read as "nobody there". The guess never changes what lawkeep allows.
- **"Same meaning" and "stricter" are evidence, not proof.** They come from sample inputs,
  deliberately broken versions and planted bugs, plus code rules (only a consistent rename
  counts as the same meaning; a change to a law's input generators always asks).
- **Objects that lie about comparisons.** Code that returns values whose `==` or `<=` always say
  "yes" passes equality and bound laws. lawkeep flags comparison methods that always return
  `True`, but cannot catch every disguise.
- **Git decides what is "new".** Several checks compare with a git base (`HEAD` locally, the
  pull request's base in CI). Once a change is committed locally, `lawkeep check --base main`
  (or CI) still shows it; plain `lawkeep check` may not.
- **Filtered inputs.** A law that throws most generated inputs away (with `assume()`) checks
  fewer cases than it seems; the report says how many inputs were thrown away. `assume()` called
  from your code instead of a law counts as an error.

## What a law looks like

```python
# laws/refunds.py
from billing.refunds import RefundTooLarge, refund
from lawkeep import given, law, st

@law("A refund never exceeds the original payment")
@given(charge=st.charges(), amount=st.money(0, 1000))
def refund_never_exceeds_payment(charge, amount):
    try:
        result = refund(charge, amount)
    except RefundTooLarge:
        return
    assert result.total <= charge.total
```

A law is a normal pytest test written with [Hypothesis](https://hypothesis.readthedocs.io/),
plus a sentence. You judge the sentence and a table of concrete examples
("payment $40, refund $50 → refused"); you never have to read the code.

## Quick start: just ask your coding agent

You do not need to type commands or read code. Once lawkeep is installed in your project, talk
to your coding agent (Claude Code, Codex, Cursor, Copilot or another):

- "Set up lawkeep for this project."
- "Add a law that refunds can never be more than the customer paid."
- "Show me the laws waiting for my approval." Then answer yes or no to each, after looking at
  the examples it shows you.
- "Check the laws." / "Did any law change in this session?"
- "Which parts of this change are not protected by a law?"

The agent runs the same `lawkeep` commands a developer would and explains the results in plain
English. If a law blocks what you asked for, a well-behaved agent stops and asks you instead of
weakening the law; lawkeep treats that as a normal, successful outcome.

**Long runs without you** (overnight, or in CI): the agent **parks and keeps going**. When a law
blocks it, it proposes the change with its reason (anything that loosens a law waits for you),
never works around the law or approves anything, finishes everything that does not depend on
that law, and ends with a summary: done / waiting for you / not done because blocked. In the
morning, `lawkeep approve` shows **one waiting list** of everything that piled up, grouped and
counted, with a suggestion for each kind; "N things wait for your decision" also shows at the
start of the next session, in `lawkeep check`, in `lawkeep report` and in the pull-request
comment.

The guide [Using lawkeep by talking to your agent](https://lawkeep.github.io/lawkeep/guides/talking-to-your-agent.html) walks
through a week with lawkeep.

## Quick start: developers

```bash
uv add --dev lawkeep            # or: pip install lawkeep
lawkeep init --agent claude-code
lawkeep draft billing.refunds --request "refunds can never exceed the payment"
lawkeep approve                 # one waiting list: drafts, proposals, unrecorded edits, unconfirmed approvals
lawkeep check                   # ALL LAWS HOLD / SOME LAWS FAIL
lawkeep strength                # are the laws strong enough to catch planted bugs?
lawkeep report --base main      # law changes + which changed functions no law protects
```

Every command takes `--json` (one JSON document, for agents and scripts) and returns a stable
result code:

| Code | Meaning |
| --- | --- |
| 0 | all laws hold |
| 1 | some laws fail |
| 2 | waiting for a person's decision (for example an unrecorded law change, or a weakening proposal) |
| 3 | setup problem |

What `lawkeep check` prints when a law fails (the billing example with its planted bug,
plain text as in a CI log, shortened; in a terminal it is in colour):

```
+------------------------------------------------------------------------------+
| SOME LAWS FAIL                                                               |
| 3 of 6 laws broke on your current code. Fix the code, not the law.           |
+------------------------------------------------------------------------------+

Law                                                                       Result
--------------------------------------------------------------------------------
“Refunding exactly what was paid gives back exactly the payment and the   Fails
whole card fee”
“Rounding money gives whole cents and is never off by more than half a    Holds
cent”
...

+-  This law fails  -----------------------------------------------------------+
| “Refunding exactly what was paid gives back exactly the payment and the      |
| whole card fee”                                                              |
|                                                                              |
| The input that breaks it: charge: a charge of $0.25 with no discount code    |
| Why it failed:            The law expected 0.25, but the code gave 0.26.     |
|                                                                              |
| What the inputs mean                                                         |
|   charge: a sample charge that lawkeep made up for testing                   |
| ...                                                                          |
| law id refunds.full_refund_gives_back_exact_payment · file laws/refunds.py   |
+------------------------------------------------------------------------------+

lawkeep tried up to 200 inputs per law (the same inputs every run, so the same
code gives the same result) · profile pr · took 3.1s
Next step: Fix the code so each failing law holds for the example shown, then
           run `lawkeep check` again. If you think a law itself is wrong, stop
           and ask a person (`lawkeep propose`); do not edit laws/ directly.
```

`lawkeep check --details` adds law ids, timings and every note; `--json` gives the same
result as one JSON document for agents. Output is plain text (no colour) when it is not a
terminal, in CI, or with `NO_COLOR` set.

A $0.25 payment would be refunded as $0.26. The failing input is saved and retried on every
later run.

More in [Getting started](https://lawkeep.github.io/lawkeep/getting-started.html), the
[developer workflow](https://lawkeep.github.io/lawkeep/guides/developer-workflow.html) and the
[law recipes](https://lawkeep.github.io/lawkeep/writing-laws/recipes.html).

## In pull requests

The lawkeep GitHub Action runs the gate on a fresh checkout and posts one comment per pull
request (updated, never duplicated) with the verdict, the law changes and their approvals, and
the protection report. It does not block merges unless you set `fail-on-broken-laws: "true"`.

```yaml
# .github/workflows/lawkeep.yml
on: pull_request
permissions: { contents: read, pull-requests: write }
jobs:
  laws:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: lawkeep/lawkeep@v0.1.0
```

Full templates (pull requests and a nightly deep search) are in
[.github/workflows/templates/](.github/workflows/templates/); see
[CI and the GitHub Action](https://lawkeep.github.io/lawkeep/guides/ci.html). (The workflow `lawkeep init --ci` writes in 0.1.0
uses `@v0`, a tag that is not published yet: pin `@v0.1.0` instead.)

## Supported coding agents

v0.1 supports Claude Code, OpenAI Codex, Cursor and GitHub Copilot from day one, and any other
agent through a shared base: the `lawkeep` CLI, an MCP server (`lawkeep mcp`, tools `check`,
`propose`, `report`), an `AGENTS.md` snippet and a git pre-commit hook. Agents with their own
hooks and permission prompts get a richer adapter on top, so "yes" comes from the prompt you
already use. `lawkeep draft` starts a fresh, separate session of your own agent to write laws
from what you asked for (no extra account or API key). So far only Claude Code has been run for
real; the Codex, Cursor and Copilot launch commands are still to be tried by hand.

## What v0.1 covers

- Python 3.10+, laws as `@law` pytest tests on Hypothesis (level L2), CrossHair as an
  experimental symbolic backend (L3).
- `init`, `draft`, `approve`, `check`, `strength`, `propose`, `report`, plus `hook` and `mcp` for
  agents.
- Permissions in `lawkeep.toml`, the law history (`laws.lock` + `laws/history.jsonl`), flags for
  unrecorded law changes and side-door files (`conftest.py` outside `laws/`, `sitecustomize.py`,
  `.pth`, stray `.pyc`, skip markers).
- Saved failing inputs replayed on every run; fixed examples on pull requests; nightly deep search.
- Law strength: quick check with dumb function versions, planted bugs (mutmut), vacuity, coverage.
- The protection report on pull requests and at the end of each agent session.
- A [cheating test suite](tests/tamper/) that plays known tricks against an example project.
- Two made-up [example projects](examples/).

**Not in v0.1:** other programming languages (TypeScript and others come last, v0.6), laws
against a real database, fake outside services and replay, race conditions, machine-checked
proofs (Dafny, v0.5), strict blocking mode (v1.0, optional), and any hosted service. See the
roadmap in [docs/PLAN.md](docs/PLAN.md).

## Working on lawkeep itself

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first: branch names,
Conventional Commits, pull requests, versions, tags and releases. Good places to start are the
[good first issues](https://github.com/lawkeep/lawkeep/labels/good%20first%20issue); questions go
to [Discussions](https://github.com/lawkeep/lawkeep/discussions). Security issues: see
[`SECURITY.md`](SECURITY.md). Everyone taking part follows the
[Code of Conduct](CODE_OF_CONDUCT.md).

```bash
uv sync --all-extras                                          # install lawkeep + dev tools
uv run pytest -q                                              # the whole suite (~9 minutes)
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts   # lint and format
uv run pyright                                                # type check
uv run lawkeep check                                          # lawkeep checks its own laws
```

- **Types:** lawkeep is fully typed. `src/lawkeep` passes pyright in strict mode and the tests
  pass it in standard mode (settings in `[tool.pyright]` in `pyproject.toml`; basedpyright reads
  the same settings). The package ships a `py.typed` marker, so your editor and type checker use
  lawkeep's types in your project too.
- **lawkeep checks itself:** this repository has its own `lawkeep.toml`, `laws.lock` and `laws/`
  (laws about `lawkeep.exitcodes`), a guard hook for Claude Code and a `lawkeep.yml` workflow.
  Change those laws only through `lawkeep propose` / `lawkeep approve`, like in any project.

## Learn more

- **Documentation: [lawkeep.github.io/lawkeep](https://lawkeep.github.io/lawkeep/)**: getting started, concepts, guides
  (also for people who only talk to their coding agent), AI tools, writing good laws, the command
  reference, FAQ and known limits.
- **For LLMs and coding agents:** [llms.txt](https://lawkeep.github.io/lawkeep/llms.txt) (index,
  [llmstxt.org](https://llmstxt.org) convention) and
  [llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt) (the whole reference in one
  Markdown file), generated from the source by `scripts/build_llms_docs.py`.
- [docs/PLAN.md](docs/PLAN.md): design, principles, roadmap, risks, decisions.
- [Onboarding guide for contributors](https://lawkeep.github.io/lawkeep/contributing/onboarding.html): how lawkeep works
  inside (every command, architecture, repository tour, data formats, safety model).
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): module contract for contributors.
- [AGENTS.md](AGENTS.md): instructions for coding agents working on lawkeep itself.

Licence: [Apache-2.0](LICENSE).
