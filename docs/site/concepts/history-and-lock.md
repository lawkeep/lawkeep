# Law history and lock

lawkeep keeps two records so that no law change is silent.

## The law history

`laws/history.jsonl` is an append-only record of every law change: one line per change, saying

- what changed (a law added, changed, removed, a setting changed ...),
- the direction (stricter, same, looser, unclear),
- who made it (`agent:claude-code`, `person:priya`, or `lawkeep` itself),
- why (the request or the agent's reason),
- which permission allowed it, and who said yes.

Lines are only ever added. Removing or editing earlier lines is detected. `lawkeep report` turns the
history into a readable list. The format is in [Files and formats](../reference/files.md).

## The lock

`laws.lock` holds a fingerprint (a SHA-256 hash) of every file that is part of the laws:

- every file in `laws/`, except `laws/drafts/`;
- `lawkeep.toml`;
- `.github/workflows/lawkeep.yml`, if lawkeep installed it.

The two append-only files (`laws/history.jsonl` and `laws/failing_examples.jsonl`) are protected
differently: the lock remembers how many lines they had and a hash of those lines, so lines can be
added but not removed.

Only lawkeep writes the lock, and only together with a history entry that explains the change.

## Unrecorded law changes

If a fingerprinted file no longer matches the lock, and the history does not explain it, someone
changed the laws outside lawkeep. lawkeep calls that an **unrecorded law change**. It is shown in
`lawkeep check`, in `lawkeep report`, in the pull-request comment and by the pre-commit hook, and
`check` returns result code 2 (waiting for your decision) until it is resolved:

- put the file back (for example `git checkout -- laws/refunds.py`), or
- a person accepts the edit with `lawkeep approve --accept-unrecorded`, which records it.

See [Handling an unrecorded law change](../guides/unrecorded-changes.md).

## Side doors

Some files can change the results without touching a law. lawkeep flags them as integrity issues:

- `conftest.py` outside `laws/`, `sitecustomize.py`, `usercustomize.py` and `.pth` files;
- stray `.pyc` files near the laws;
- skip or xfail markers in laws, hooks in `laws/conftest.py`, weakened Hypothesis settings;
- code under test that imports lawkeep, pytest or Hypothesis, reads lawkeep's or Hypothesis's
  settings, raises skips, defines comparisons that always say "equal", or shadows a standard-library
  or installed module.

Several of these checks compare with git (`HEAD` locally, the pull request's base in CI) to decide
what is new. Serious ones make `check` return 2; others are shown as warnings.

## What lawkeep does not do

It does not stop anyone from editing files. The agent adapters block direct edits to `laws/` where
the agent supports it, but that is a speed bump, not a wall. The promise is that such edits are never
**silent**.
