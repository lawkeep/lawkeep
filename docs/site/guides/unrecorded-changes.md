# Handling an unrecorded law change

An **unrecorded law change** means a file that is part of your laws (something in `laws/`,
`lawkeep.toml` or the lawkeep workflow) no longer matches its fingerprint in `laws.lock`, and the law
history does not explain why. Someone (or some agent) changed it without going through lawkeep.

## Where you see it

- `lawkeep check` returns result code 2, `WAITING FOR YOUR DECISION`, and names the file;
- `lawkeep report` and the pull-request comment list it as "changed outside lawkeep";
- the git pre-commit hook shows it when you commit;
- it is one of the items on the [waiting list](../concepts/waiting-list.md).

## What to do

First look at the change:

```bash
git diff -- laws/ lawkeep.toml laws.lock
```

Then choose one of two ways.

**Put it back** if nobody meant to change the law:

```bash
git checkout -- laws/refunds.py
lawkeep check
```

**Accept it** if the change is right. A person records it:

```bash
lawkeep approve --accept-unrecorded
```

lawkeep shows each changed file and asks you to accept or skip it. Accepting records the change in
the history with your name and updates the lock. If the change belongs in a proper proposal instead,
put the file back and use [`lawkeep propose`](changing-a-law.md), so lawkeep can judge its direction.

## Why it happens

- An agent edited `laws/` directly although its instructions say not to. The agent adapters block
  this where the agent supports it, but not every edit can be caught.
- A person edited a law by hand, or a merge or rebase changed a law file.
- A tool reformatted files in `laws/` (configure formatters and pre-commit hooks to skip `laws/`,
  `laws.lock` and `lawkeep.toml`).

## Special cases

- **`laws.lock` was deleted** while the history has entries: `lawkeep init` refuses to rewrite it;
  restore it from git.
- **Lines removed from `laws/history.jsonl` or `laws/failing_examples.jsonl`**: these files are
  append-only; lawkeep flags removed lines. Restore them from git.
- **A change is committed locally**: some checks compare with git `HEAD`. Run
  `lawkeep check --base main` to compare with your main branch; CI compares with the pull request's
  base.
