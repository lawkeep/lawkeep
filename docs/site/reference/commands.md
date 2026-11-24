<!-- Generated from the lawkeep command-line parsers and docs/ARCHITECTURE.md section 7 by scripts/build_llms_docs.py; do not edit. -->

# Commands

Every lawkeep command, with its exact options. This page is generated from lawkeep 0.1.0's own command-line parsers, so it always matches `lawkeep <command> --help`. What the result codes mean is explained in [Result codes](result-codes.md).

Every command also takes `--json` (print exactly one JSON document on stdout, nothing else) and `--root PATH` (project folder; default: search upward from the current folder for `lawkeep.toml`, else `laws/`; env `LAWKEEP_ROOT` is used when set). `lawkeep --version` prints the version. Bad usage exits with 3, never 2.

| Command | What it does |
| --- | --- |
| `init` | set up lawkeep in this project (safe to run again) |
| `draft` | ask your coding agent (in a separate session) to write draft laws for you to approve |
| `approve` | read the drafted laws and proposed law changes, and say yes or no to each |
| `check` | check that your code follows every law (answer: ALL LAWS HOLD or SOME LAWS FAIL) |
| `strength` | test whether your laws are strong enough to catch real mistakes in the code |
| `propose` | ask for a change to a law; changes that weaken a law wait for a person's yes |
| `report` | show every law change, anything waiting for you, and which changed code no law protects |
| `hook` | used by coding agents and git to call lawkeep (you do not need to run it) |
| `mcp` | let coding agents use lawkeep as tools (check, propose, report, list_laws) |

## lawkeep init

set up lawkeep in this project (safe to run again)

```text
lawkeep init [--agent NAME ...] [--no-hooks] [--ci | --no-ci] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `--agent` `NAME` (repeatable) | coding agent(s) to set up: claude-code, codex, cursor, copilot, all, other or none (repeat or comma-separate; default: the agents found in this folder) |
| `--no-hooks` | do not install the git pre-commit hook or the agent hooks (only the instructions and the MCP server) |
| `--ci` | also check the laws on every pull request (adds a GitHub Action workflow) |
| `--no-ci` | do not add the GitHub Action workflow |

Result codes: 0 done · 2 laws changed outside lawkeep, or laws.lock deleted while the history has entries (nothing touched) · 3 problem

## lawkeep draft

ask your coding agent (in a separate session) to write draft laws for you to approve

```text
lawkeep draft [MODULE] [--request REQUEST] [--docs PATH ...] [--dry-run] [--timeout TIMEOUT] [--actor ACTOR] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `MODULE` (positional, optional) | the code to write laws for: a module name (billing.refunds) or a file or folder path |
| `--request` `REQUEST` | the rules you want, in plain English (e.g. "refunds never exceed the payment") |
| `--docs` `PATH` (one or more) | documents that describe the rules (specs, policies, READMEs) |
| `--dry-run` | only show the message lawkeep would send to your agent; start nothing |
| `--timeout` `TIMEOUT` | how many seconds to wait for the agent |
| `--actor` `ACTOR` | who writes the drafts, e.g. "agent:claude-code" |

Result codes: 2 drafts (or the agent's edits to approved files, now waiting proposals) waiting for a person · 1 a draft fails on today's code or is weak · 3 agent not set up, failed, or wrote nothing (and changed no approved file)

## lawkeep approve

read the drafted laws and proposed law changes, and say yes or no to each

```text
lawkeep approve [ID ...] [--yes | --no] [--by BY] [--channel CHANNEL] [--accept-unrecorded] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `ID ...` (positional, zero or more) | what to decide: a law id, a decision id (h-...) or a draft file (default: everything waiting) |
| `--yes` | say yes without being asked |
| `--no`, `--reject` | say no without being asked |
| `--by`, `--approver` `BY` | the name of the person who decided (default: your git user name) |
| `--channel` `CHANNEL` | where the decision was made, e.g. "agent permission prompt" (recorded) |
| `--accept-unrecorded` | also decide about law files someone changed directly, without lawkeep |

Result codes: 0 decided · 2 still waiting (no terminal / `--json` and no `--yes`/`--no`) · 1 a decision could not be applied · 3

## lawkeep check

check that your code follows every law (answer: ALL LAWS HOLD or SOME LAWS FAIL)

```text
lawkeep check [--profile NAME] [--deep-check] [--law LAW_ID ...] [--base REF] [--no-save] [--details] [--timeout SECONDS] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `--profile` `NAME` | which settings to use: 'pr' (the default: the same inputs every run, so the same code always gets the same answer) or 'deep' (many more random inputs, for nightly runs) |
| `--deep-check` | experimental: let CrossHair pick inputs by reading the code (needs lawkeep[deep]); it may not try every path through the code |
| `--law` `LAW_ID` (repeatable) | check only this law, by its id (repeat for several) |
| `--base` `REF` | git branch or commit to compare with when looking for files that could get around the laws (default: HEAD) |
| `--no-save` | do not save newly found failing inputs (normally kept in laws/failing_examples.jsonl and tried again on every check) |
| `--details`, `-v` | also show law ids, inputs tried, timings and every note |
| `--timeout` `SECONDS` | stop the laws after this many seconds (default: no limit) |

Result codes: 0 · 1 · 2 (integrity errors / pending decisions) · 3

## lawkeep strength

test whether your laws are strong enough to catch real mistakes in the code

```text
lawkeep strength [--full] [--law LAW_ID ...] [--drafts] [--details] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `--full` | plant every small bug lawkeep can make in every function a law runs (slower; for nightly runs or before approving important laws) |
| `--law` `LAW_ID` (repeatable) | measure only this law (repeatable), e.g. --law refunds.refund_is_capped |
| `--drafts` | also measure the drafts in laws/drafts/ (they are not approved yet) |
| `--details`, `-v` | also show law ids, every planted bug a law missed and test-data notes |

Result codes: 0 no law flagged · 1 some law flagged (or fails today) · 3

## lawkeep propose

ask for a change to a law; changes that weaken a law wait for a person's yes

```text
lawkeep propose [LAW_ID] [--file PATH] [--reason REASON] [--delete] [--actor ACTOR] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `LAW_ID` (positional, optional) | the law to change (e.g. refunds.refund_is_capped) |
| `--file` `PATH` | the complete new version of the law's file |
| `--reason` `REASON` | why the law should change (shown to people) |
| `--delete` | propose deleting the law (always needs a yes) |
| `--actor` `ACTOR` | who proposes it, e.g. "agent:claude-code" (default: agent from lawkeep.toml) |

Result codes: 0 applied · 2 waiting for a person · 1 rejected (new version broken) · 3

## lawkeep report

show every law change, anything waiting for you, and which changed code no law protects

```text
lawkeep report [--since TIMESTAMP | --session | --all] [--base REF] [--no-protection] [--format {text,markdown}] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `--since` `TIMESTAMP` | show law changes at or after this time (ISO 8601, e.g. 2026-11-21T10:00:00Z) |
| `--session` | show law changes since the current agent session started (the default when a session start was recorded) |
| `--all` | show every recorded law change |
| `--base` `REF` | compare code changes with this branch, tag or commit (default: the merge-base with main or master, plus uncommitted changes) |
| `--no-protection` | skip the check of which changed code your laws protect (it plants small bugs in a copy of the code, which takes a while) |
| `--format` `{text,markdown}` | text for the terminal, markdown for a pull-request comment (not used with --json) |

Result codes: 0 · 2 if integrity errors or pending decisions · 3

## lawkeep hook

used by coding agents and git to call lawkeep (you do not need to run it)

```text
lawkeep hook [EVENT] [--agent {claude-code,codex,cursor,copilot,other,git}] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `EVENT` (positional, optional) | pre-tool-use, session-start, session-end or pre-commit (or an agent name, then the event defaults to pre-tool-use) |
| `--agent` `{claude-code,codex,cursor,copilot,other,git}` | which agent calls the hook (decides the output format; default claude-code style) |

Result codes: agent hooks always 0 (the decision is in the agent's own JSON; exit 2 would mean "block" to agents but "waiting" to lawkeep) · pre-commit 0, or 1 only with `git config lawkeep.precommit block` / `LAWKEEP_PRECOMMIT=block`

## lawkeep mcp

let coding agents use lawkeep as tools (check, propose, report, list_laws)

```text
lawkeep mcp [--agent NAME] [--json] [--root PATH]
```

| Option | Meaning |
| --- | --- |
| `--agent` `NAME` | the agent using the server, recorded as the actor of proposals (claude-code, codex, cursor, copilot; default: other) |

Result codes: 0 when the client disconnects · 3 if `mcp` is not installed
