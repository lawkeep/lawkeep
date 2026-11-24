# Developer daily workflow

This page is for developers who use the `lawkeep` command directly, usually next to a coding agent.

## Set up once

```bash
uv add --dev lawkeep
lawkeep init --agent claude-code     # or codex, cursor, copilot, all, other
git add lawkeep.toml laws.lock laws/ AGENTS.md && git commit -m "chore: set up lawkeep"
```

Commit everything `init` creates except `.lawkeep/` (local state). See
[Getting started](../getting-started.md) for what each file is.

## A normal day

```bash
lawkeep check                  # before you push: ALL LAWS HOLD?
lawkeep report --base main     # law changes on this branch + what no law protects
```

- `check` returns 0 when all laws hold. When a law fails, it shows the simplest input that breaks it.
  Fix the code and run `check` again. If you believe the law itself is wrong, propose a change (see
  [Changing a law](changing-a-law.md)); do not edit `laws/` by hand.
- `report` lists every law change with who made it and why, anything changed outside lawkeep, and
  the [protection report](../concepts/protection.md): changed functions that no law protects. Read
  those; the protected ones were checked by your laws.

Your coding agent follows the same loop on its own: the instructions `init` puts in `AGENTS.md` tell
it to run `lawkeep check` before finishing and to show you `lawkeep report` at the end of the session.

## Adding laws

```bash
lawkeep draft billing.refunds --request "refunds can never exceed the payment"
lawkeep approve
```

Or write a law by hand in `laws/` and run `lawkeep approve --accept-unrecorded` to record it, or put
it in `laws/drafts/` and approve it as a draft. Patterns for good laws:
[Writing good laws](../writing-laws/index.md).

## Checking the laws themselves

```bash
lawkeep strength               # quick: deliberately broken versions of each function
lawkeep strength --full        # every planted bug; slower, good before important approvals
```

See [Law strength](../concepts/strength.md).

## Useful options

| You want to | Run |
| --- | --- |
| see law ids, timings and every note | `lawkeep check --details` |
| check one law while you work on it | `lawkeep check --law refunds.refund_never_exceeds_payment` |
| a deeper random search | `lawkeep check --profile deep` |
| machine-readable output | add `--json` to any command |
| run from another folder | add `--root path/to/project` (or set `LAWKEEP_ROOT`) |
| compare with your main branch after a local commit | `lawkeep check --base main` |
| not save newly found failing inputs | `lawkeep check --no-save` |

Every command and option: [Commands](../reference/commands.md).

## The pre-commit hook

`init` adds a block to `.git/hooks/pre-commit` that shows law changes made outside lawkeep when you
commit. It does not block the commit unless you ask it to:

```bash
git config lawkeep.precommit block    # or set LAWKEEP_PRECOMMIT=block
```

If you use the `pre-commit` framework, add `lawkeep hook pre-commit` as a local hook so it keeps
running.

## Files to know

| File | What it is |
| --- | --- |
| `lawkeep.toml` | settings and permissions ([Configuration](../reference/configuration.md)) |
| `laws/*.py` | approved laws |
| `laws/strategies.py` | your input generators (`st.charges()`) |
| `laws/history.jsonl` | every law change, append-only |
| `laws/failing_examples.jsonl` | every failing input found, replayed on every check |
| `laws/drafts/` | drafts and waiting proposals; ignored by the gate |
| `laws.lock` | fingerprints; written only by lawkeep |

Never edit `laws/`, `laws.lock` or `lawkeep.toml` by hand unless you mean to record the change with
`lawkeep approve --accept-unrecorded` afterwards. Details: [Files and formats](../reference/files.md).
