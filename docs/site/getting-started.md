# Getting started

This page takes you from nothing to your first approved law and a green check. It takes about ten
minutes. You need a Python project (Python 3.10 or newer) in a git repository, and ideally a
coding agent such as Claude Code, Codex, Cursor or GitHub Copilot.

Not typing commands yourself? Ask your coding agent to do each step ("Set up lawkeep for this
project", "Add a law that ...", "Show me what waits for my approval"). See
[Using lawkeep by talking to your agent](guides/talking-to-your-agent.md).

## 1. Install

lawkeep is a development tool, so add it next to your other dev tools:

```bash
uv add --dev lawkeep
```

or with pip:

```bash
pip install lawkeep
```

Optional extras:

| Extra | What it adds |
| --- | --- |
| `lawkeep[mcp]` | the MCP server, so agents can call lawkeep as tools ([MCP server](agents/mcp.md)) |
| `lawkeep[deep]` | CrossHair, an experimental way to pick inputs by reading the code (`lawkeep check --deep-check`) |

Check that it works:

```bash
lawkeep --version
```

## 2. Set up your project

```bash
lawkeep init --agent claude-code
```

Use the name of your agent: `claude-code`, `codex`, `cursor`, `copilot`, `all`, `other` or `none`.
Without `--agent`, lawkeep sets up the agents it finds in the folder.

`init` creates:

- `lawkeep.toml`: your settings, including **permissions** (what an agent may do to your laws
  without asking you);
- `laws/`: the folder for your laws, with `laws/strategies.py` (your own input generators) and two
  record files, `laws/history.jsonl` (every law change) and `laws/failing_examples.jsonl` (every
  failing input ever found);
- `laws.lock`: fingerprints of every law file, so edits made outside lawkeep are noticed;
- the lawkeep section in `AGENTS.md`, which tells every coding agent the rules;
- hooks and settings for your agent (see [AI tools](agents/index.md)) and a git pre-commit hook that
  shows law changes made outside lawkeep;
- with `--ci` (or when the project already has a `.github/` folder): a GitHub Actions workflow,
  see [CI and the GitHub Action](guides/ci.md).

`init` is safe to run again: it merges into existing files and never overwrites them. Commit
everything it created except `.lawkeep/` (local state, added to `.gitignore` for you).

The default permissions, in plain words:

```text
The agent may add new laws and saved examples on its own, and tell you.
Changing what a law checks waits for your yes.
Loosening, deleting or skipping a law always waits for your yes (this cannot be turned off).
```

## 3. Write your first law

You can write laws by hand (see [Writing good laws](writing-laws/index.md)), but usually your
coding agent writes them. There are two ways.

**Ask your agent in its normal session:**

> Add a law that refunds can never be more than the customer paid.

The agent writes the law and proposes it through lawkeep. Adding a law is a *stricter* change, so
by default it goes in on its own, and you see it in the end-of-session report.

**Or use `lawkeep draft`:**

```bash
lawkeep draft billing.refunds --request "refunds can never exceed the payment"
```

This starts a **separate** session of your own coding agent (no extra account or API key) that
sees your request and the function signatures, but not the function bodies. That makes it less
likely to write a law that describes today's bugs. The agent writes **drafts** into
`laws/drafts/`. lawkeep then runs each draft on your current code and on deliberately broken
copies of it, to see whether the law would catch a mistake.

## 4. Approve it

```bash
lawkeep approve
```

`approve` shows everything that waits for your decision, one item at a time. For each draft you see
the sentence, whether it works with your current code, whether it is strong, and a table of real
examples:

```text
+-  Draft law 1 of 2  ----------------------------------------------------+
| “A refund never exceeds the original payment”                           |
|                                                                         |
| + Works with your current code — lawkeep tried 50 different inputs and  |
|   the law was never broken.                                             |
| + Strong law — lawkeep made 6 deliberately broken versions of the code  |
|   and this law caught all 6.                                            |
|                                                                         |
| Examples lawkeep tried                                                  |
| Input                       What the code did              Follows      |
|                                                            the law?     |
| charge $40.00, amount $50   refund() raised RefundTooLarge Yes          |
| charge $40.00, amount $40   refund() gave 40.00            Yes          |
|                                                                         |
| + Recommended: approve. It works with your code and catches mistakes.   |
+-------------------------------------------------------------------------+
Approve this law? [y/N]
```

You judge the sentence and the examples, not the code. Your yes is recorded with your name. A
coding agent should only run `lawkeep approve` when you ask it to, and your agent's own permission
prompt asks you to confirm.

## 5. Check

```bash
lawkeep check
```

```text
+--------------------------------------------------+
| ALL LAWS HOLD                                    |
| All 6 of your laws held on your current code.    |
+--------------------------------------------------+
```

`check` first makes sure nobody changed the laws outside lawkeep, then runs every approved law in
a clean, separate Python process, against up to 200 inputs each. The same code always gets the same
answer.

## What the output means

The first line is always the verdict:

| Verdict | Result code | What to do |
| --- | --- | --- |
| `ALL LAWS HOLD` | 0 | nothing; you are done |
| `SOME LAWS FAIL` | 1 | fix the code (not the law) until the law holds for the example shown |
| `WAITING FOR YOUR DECISION` | 2 | a person needs to decide something: run `lawkeep approve` |
| `SETUP PROBLEM` | 3 | lawkeep could not run; read the message and the hint |

When a law fails, lawkeep shows the input that breaks it and says why in words ("The law expected
0.25, but the code gave 0.26"). Add `--details` for law ids, timings and every note, or `--json`
for one machine-readable document. Output is plain text without colour when it is not a terminal,
in CI, or with `NO_COLOR` set. The last line always says what to do next.

## Next steps

- `lawkeep strength`: are your laws strong enough to catch real mistakes? See
  [Law strength](concepts/strength.md).
- `lawkeep report --base main`: which law changes happened, and which changed code no law protects.
  See [Protection report](concepts/protection.md).
- Check laws on every pull request: [CI and the GitHub Action](guides/ci.md).
- Learn the ideas behind lawkeep: [Concepts](concepts/index.md).
