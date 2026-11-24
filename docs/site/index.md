# lawkeep

**Only review what your laws don't protect.**

lawkeep is an open-source tool for working safely with AI coding agents. You decide on a short
list of **laws**: rules your code must obey for every input, each written as one plain-English
sentence. Your coding agent writes and maintains the checks behind them. lawkeep records every
law change, asks you before any law gets weaker, runs one gate that says `ALL LAWS HOLD` or
`SOME LAWS FAIL`, and shows you which changed code no law protects, so that is the only code you
still need to read.

:::{note}
**Status: lawkeep 0.1.0 is released on [PyPI](https://pypi.org/project/lawkeep/) (Alpha).**
It works with Python 3.10 and newer, on Linux and macOS (macOS is untested; Windows is not
supported). Commands and file formats may still change. Read the
[known limits](faq.md#known-limits) before you rely on it.
:::

## The problem

Coding agents write a lot of code quickly. Reading all of it is slow, and skipping it is risky.
Tests help, but an agent that is asked to make the tests pass can also change the tests: delete
one, loosen a check, or skip a hard case. Nobody notices until something breaks.

lawkeep gives you a small set of rules that the agent may not quietly change, checks them
against hundreds of inputs on every run, and tells you where your rules do not reach.

## The promise, honestly

- **Every law runs** on every `lawkeep check`, against many generated inputs. Every failure comes
  with the simplest input that breaks it.
- **The AI never changes your laws silently.** Every law change is recorded: what changed, which
  agent changed it, why, and who said yes. A change made by editing files directly is flagged as
  an *unrecorded law change*.
- **Weakening a law needs your yes.** Stricter changes can go ahead on their own if you allow it.
  Loosening, deleting or skipping a law, or trying fewer cases, always waits for a person.
- **Weak laws get flagged.** lawkeep plants bugs in a copy of your code and tells you when no law
  notices them.

What lawkeep does **not** promise: that your code is correct beyond what your laws say, or that an
agent *cannot* get around it. lawkeep records and shows; it does not force a review process on your
team. See [FAQ and known limits](faq.md).

## A 30-second example

A law is a sentence plus a check. This one is about refunds in a made-up shop:

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

You never have to read that code. When the law is proposed, you see the sentence and a table of
real examples ("payment $40, refund $50 → refused → follows the law: yes") and say yes or no.
From then on, every `lawkeep check` tries the law with hundreds of different payments and refund
amounts. If the code breaks a law, you get the simplest case (output from the billing example
project with a planted bug, shortened):

```text
SOME LAWS FAIL
3 of 6 laws broke on your current code. Fix the code, not the law.
...
“Refunding exactly what was paid gives back exactly the payment and the whole card fee”
The input that breaks it: charge: a charge of $0.25 with no discount code
Why it failed:            The law expected 0.25, but the code gave 0.26.
```

That failing input is saved and tried again on every later check, so the bug cannot quietly come
back.

## Install

```bash
uv add --dev lawkeep        # or: pip install lawkeep
lawkeep init --agent claude-code   # or codex, cursor, copilot, all, other
```

Then follow [Getting started](getting-started.md). If you do not type commands yourself, ask your
coding agent: "Set up lawkeep for this project." See
[Using lawkeep by talking to your agent](guides/talking-to-your-agent.md).

## Where to go next

- **New here:** [Getting started](getting-started.md), then [Concepts](concepts/index.md).
- **You use a coding agent and do not write code:**
  [Using lawkeep by talking to your agent](guides/talking-to-your-agent.md).
- **You are a developer:** [Daily workflow](guides/developer-workflow.md),
  [Writing good laws](writing-laws/index.md) and the [command reference](reference/commands.md).
- **Your agent:** [Claude Code](agents/claude-code.md), [Codex](agents/codex.md),
  [Cursor](agents/cursor.md), [GitHub Copilot](agents/copilot.md).
- **Pull requests:** [CI and the GitHub Action](guides/ci.md).
- **For LLMs and coding agents:** [llms.txt](https://lawkeep.github.io/lawkeep/llms.txt) and
  [llms-full.txt](https://lawkeep.github.io/lawkeep/llms-full.txt) (the whole reference in one
  Markdown file). Every page of this site is also available as Markdown: add `.md` to its
  address instead of `.html`.

## Links

- Source code: [github.com/lawkeep/lawkeep](https://github.com/lawkeep/lawkeep)
- Package: [pypi.org/project/lawkeep](https://pypi.org/project/lawkeep/)
- Questions and ideas: [Discussions](https://github.com/lawkeep/lawkeep/discussions)
- Bugs and features: [Issues](https://github.com/lawkeep/lawkeep/issues)
- Licence: Apache-2.0

```{toctree}
:hidden:
:caption: Start here

getting-started
concepts/index
```

```{toctree}
:hidden:
:caption: Guides

guides/talking-to-your-agent
guides/developer-workflow
guides/ci
guides/long-runs
guides/changing-a-law
guides/unrecorded-changes
```

```{toctree}
:hidden:
:caption: AI tools

agents/index
agents/claude-code
agents/codex
agents/cursor
agents/copilot
agents/mcp
```

```{toctree}
:hidden:
:caption: Writing good laws

writing-laws/index
writing-laws/recipes
writing-laws/weak-laws
```

```{toctree}
:hidden:
:caption: Reference

reference/commands
reference/configuration
reference/result-codes
reference/files
reference/json
reference/python-api
reference/github-action
```

```{toctree}
:hidden:
:caption: Project

faq
contributing/index
changelog
```
