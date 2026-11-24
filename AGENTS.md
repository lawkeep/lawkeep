# AGENTS.md

Context for any coding agent or tool working in this repository (Claude Code, Codex, Cursor, Copilot, Gemini and others).

## What this project is

**lawkeep** is an open-source layer for safe AI-assisted coding: coding agents write and maintain *laws* (rules the code must obey), people decide on them, every law change is permissioned, recorded and shown, and one *gate* (`lawkeep check`) says `ALL LAWS HOLD` or `SOME LAWS FAIL`.

**Read [`docs/PLAN.md`](docs/PLAN.md) before doing any work.** It is the design source of truth: principles, core concepts, architecture, v0.1 scope, roadmap, risks, decisions and open questions.

## Current state

- Stage: **v0.1.0 (2026-11-23): first commit on `main`; release to PyPI as `lawkeep` 0.1.0 (Alpha). Releases after this go through `.github/workflows/release.yml` (tag `v*`, PyPI trusted publishing); see `CHANGELOG.md`.** The design decisions from 2026-11-19/20/21 are in `docs/PLAN.md` → "Decisions". The choices made during the build are there too; all were reviewed and approved by the maintainer on 2026-11-23.
- Code: Python package in `src/lawkeep/` (all nine commands: `init`, `draft`, `approve`, `check`, `strength`, `propose`, `report`, `hook`, `mcp`), adapters for Claude Code, Codex, Cursor and Copilot, the GitHub Action (`action.yml`), CI workflows, two made-up example projects (`examples/billing`, `examples/bookings`), the cheating test suite (`tests/tamper/`), a README and guides (`docs/guide/`). The interface contract is in `docs/ARCHITECTURE.md`.
- Tests: `uv run pytest` runs the whole suite: 817 tests in about 9 minutes, all passing on Python 3.12 / Linux (2026-11-23, after "long runs without a person"; 25 of them new in `tests/test_lifecycle_waiting_list.py`).
- Output redesign (2026-11-22, approved 2026-11-23): every command's human output goes through `src/lawkeep/ui.py` (Rich; plain text when not a terminal, in CI or with `NO_COLOR`) and `src/lawkeep/explain.py`, following `docs/OUTPUT-STYLE.md`; `@law(..., inputs={...})` describes inputs; `check`/`strength --details`; `--json` schema unchanged; both examples now have 6 laws (exact-answer companions added with `lawkeep propose`) and `lawkeep strength` reports no weak laws. See `docs/PLAN.md` → Decisions. `uv run ruff check src tests && uv run ruff format --check src tests` is clean.
- Review fixes (2026-11-22, recorded in `docs/PLAN.md` → Decisions, approved 2026-11-23): law-running processes start with `python -I -S -B` (no `.pth`/`sitecustomize` code, so a fresh venv no longer makes `check` wait); results come back through a pipe; code under test is documented as trusted and suspicious source is flagged (`source_side_door`); skips raised while a law runs and `assume()` from outside `laws/` are errors; "same meaning" needs a consistent one-to-one rename and identical generators; generator changes always ask; a widened limit is labelled looser; `approve --accept-unrecorded` / `--yes` without ids no longer decide weakening proposals, and no-terminal approvals record `terminal: false`, never borrow the git user name, and are listed by `check`/`report`; new laws via `propose` must pass the quick strength check; the lawkeep workflow is fingerprinted; `check --law <typo>` is a setup problem and `--law` runs say they are partial; the Action reads the history relative to `working-directory`; MCP configs fall back to `.venv`.
- Type checking (2026-11-23, see `docs/PLAN.md` → Decisions): `uv run pyright` reports 0 errors and 0 warnings, with `src/lawkeep` in **strict** mode and `tests` in standard mode (`[tool.pyright]` in `pyproject.toml`, `pythonVersion = "3.10"`). basedpyright (the maintainer's Neovim checker) reads the same table and also reports 0 errors; `typeCheckingMode` is set explicitly so it does not fall back to its own stricter default. The package ships `py.typed` (checked in the built wheel and sdist). CI runs pyright in the `lint` job with the version from `uv.lock`. Bugs found on the way are covered by `tests/test_typing_fixes_*.py`.
- Direction and guard fixes (2026-11-23, see `docs/PLAN.md` → Decisions, approved 2026-11-23): law-change direction is deterministic (explicit Hypothesis seed from the law id and both versions' source hashes, fixed 100-input budget, `PYTHONHASHSEED=0`) and a moved limit in an assert (`<= b` → `<= b + c`, `<` ↔ `<=`, `==` → `<=` ...) is read statically (`direction.bound_direction`); the formerly flaky `test_bigger_limit_is_labelled_looser` passed 30 of 30 separate runs, and `tests/test_lifecycle_direction_determinism.py` repeats it 30 times in the suite. The pre-tool-use guard judges shell commands by what they write to (`adapters/shellwords.py`, `writes.py`, `pywrites.py`), so reading or naming `laws/` is no longer blocked; table of cases in `tests/test_adapters_guard_writes.py`.
- One law-running core (2026-11-23, option B of the 2026-11-22 decision; the merge's own choices are approved 2026-11-23, see `docs/PLAN.md` → Decisions): `src/lawkeep/lawrun.py` + `_lawrun_child.py` start every law-running process (`python -I -S -B` via `_boot.py`, scrubbed environment, request on stdin, JSON-lines results on the write-once pipe) in mode `check` (`pytest_plugin.run_check`), `strength` (`strength/_worker.run`) or `probe` (`_probe_worker.run`). `isolation.py` and `strength/_run.py` are gone; the gate plugin can no longer be switched on by environment variables; strength now loads only the fixtures of `laws/conftest.py`. `tests/test_lawrun.py` runs every mode in a hostile shell. `check`, `strength` and `report --base HEAD` (JSON and text) on temp copies of both examples, plain and with each patch, gave the same output as before the merge apart from durations; one billing example table drew two different inputs (Hypothesis also takes constants from lawkeep's own source in an editable install).
- Copilot drafting preset (2026-11-23, approved 2026-11-23): `copilot -p {prompt} --no-ask-user --allow-tool 'read, write(laws/drafts/*), write(laws/strategies.py)' --deny-tool 'shell, url'` instead of `--allow-all-tools`; based on GitHub's Copilot CLI docs, never run (Copilot is not installed here).
- Drafting edits become proposals (2026-11-23, implements the maintainer's change to the 2026-11-22 "Drafting" decision): when the agent started by `lawkeep draft` edits an approved law file, an existing generator in `laws/strategies.py`, `lawkeep.toml` or another fingerprinted file, lawkeep puts the approved version back and turns each changed file into a waiting proposal (`src/lawkeep/draft_edits.py`, `propose.park_proposal`, `whole_file`/`from_draft` in the history details), with the direction judged as in `propose`; never applied automatically, even when stricter, and never decided by `approve --yes` without ids. New generators are still added as before (split off from changed ones by `draft_edits.additions_only`). `draft` lists them under "The drafting AI also changed approved laws or settings — waiting for your review" and in `data.waiting_changes` (JSON, additive). Tested with the fake agent only (`tests/test_lifecycle_draft_edits.py`); not tried with a real agent.
- Long runs without a person (2026-11-23, decided in `docs/PLAN.md` → Decisions; the build choices are approved 2026-11-23): **park and keep going**: the AGENTS.md snippet ("When no person is there"; also Cursor's rule and Copilot's instructions), the session-start reminder, the MCP instructions and the draft prompt tell agents that, when a law blocks them and nobody is there, they `lawkeep propose` with a reason, never work around or edit the law, never run `lawkeep approve`, finish the rest, and end with done / waiting (ids) / not done because blocked; with a person there, "stop and ask" is unchanged. `person_present` (`src/lawkeep/presence.py`) is a documented guess (`LAWKEEP_PERSON_PRESENT`, `CI`, a terminal on stdin, two Claude Code variables; other agents read as "no"). **One waiting list**: `src/lawkeep/waiting.py` counts drafts, proposals, drafting-agent edits, unrecorded edits and unconfirmed approvals (additive JSON `waiting_for_person`; one line "N things wait for your decision — run `lawkeep approve`" in `check`, `report`, the PR comment and the session hooks; result codes unchanged); `lawkeep approve` shows them all, offers a safe "approve all recommended new drafts and stricter changes", and lets a person in a terminal confirm or undo approvals made without a terminal (`src/lawkeep/approvals.py`; undo copies in `laws/drafts/proposals/undo/`). `propose` without a person says "Parked as h-… Continue …" (`next_step`). The interactive screens are tested with scripted answers, not typed through by hand; no real agent was run with the new instructions.
- Shown working locally (2026-11-22):
  - In a clean copy of the repository with a freshly created venv (as CI would have): both examples give ALL LAWS HOLD (exit 0), each planted bug fails the gate with a small failing input (exit 1), and the whole cheating suite passes (45 tests, including the new in-process tricks in `tests/tamper/test_tamper_in_process.py`).
  - `strength` flags a deliberately vacuous law; a vacuous law sent through `propose` now waits instead of going in.
  - `report` marks an unprotected `refund_v2()` as NOT protected.
  - A hand-edited law is flagged as an unrecorded law change.
  - `init --agent all` works and is idempotent.
- Known limits (also in README → "Known limits"): the code under test runs in the law runner's process and could still cheat on purpose (flagged, not prevented, e.g. patching Hypothesis); approvals record who *claimed* to approve and cannot be authenticated; "same"/"stricter" are evidence from samples plus code rules, not proof; objects whose comparisons always say yes are only caught when the comparison method visibly returns a constant; several checks compare with a git base, so a local commit hides some flags from a plain local `check` (CI with the PR base still shows them).
- Not done or not verified:
  - Real-agent smoke tests: only Claude Code was run for real (by the verification step). Codex, Cursor and Copilot adapters are checked only against their docs and simulated hook payloads. The new Copilot preset in particular is unverified: whether a tool that is neither allowed nor denied is refused in `-p` mode, and whether `write(laws/drafts/*)` matches every draft path.
  - CI on GitHub (2026-11-23) passes on Python 3.10, 3.12 and 3.13 on Linux (ubuntu-latest); macOS was never tested. No Windows support: hooks and the MCP launcher are POSIX sh, the strength time limit uses SIGALRM, and the results pipe is POSIX-only (a results file is used elsewhere, untested).
  - mutmut is not wrapped; lawkeep uses its own small mutation step (see Decisions; `[strength] mutation_tool` is ignored).
  - The bookings example's generator still uses a lambda (the guard rightly blocks agents from editing example laws); lawkeep's text output now shows such values as what they build, but the JSON keeps Hypothesis's raw text.
  - The examples' history was made by `examples/make_example_history.py`, not by real `draft`/`approve` runs, so it has no strength evidence and no `terminal` field.
  - A failing example that `check` just saved (not yet committed or recorded in `laws.lock`) can still be deleted without a flag; `history.record_change` now refuses to record anything after recorded lines were removed.
  - Needs people: the private pilot on two real modules, the non-technical tester, and the ~30-task evaluation with and without lawkeep (no task set or runner exists yet).
- **lawkeep checks itself (decided 2026-11-22):** this repository uses lawkeep on its own code. `lawkeep init --agent claude-code` set up `lawkeep.toml`, `laws.lock`, `laws/`, `.mcp.json`, `.claude/settings.json` (guard hook + "ask" rule for `lawkeep approve`), `.git/hooks/pre-commit`, `.github/workflows/lawkeep.yml` (uses the local action, `uses: ./`, with `lawkeep-spec: "."`) and the lawkeep section at the end of this file. Three laws about `lawkeep.exitcodes` are approved by the maintainer. Keep these files; change laws only through lawkeep.
- Public repository set up for contributors (2026-11-23, see `docs/PLAN.md` → Decisions): issue forms, Code of Conduct, `CODEOWNERS`, `.editorconfig`, pre-commit hooks, README badges, dependency-review / PR-title / Scorecard / Pages workflows, docs site at https://lawkeep.github.io/lawkeep/, labels, roadmap milestones, issues for the v0.2 roadmap and the known gaps (some marked `good first issue`), Discussions, security features and a ruleset on `main`. Open work is tracked in GitHub issues from now on.
- LLM-friendly docs (2026-11-24, see `docs/PLAN.md` → Decisions): `docs/llms.txt`, `docs/llms-full.txt` and `docs/onboarding.md` (until the docs website: `docs/index.md`) follow the llms.txt convention; `llms.txt` and `llms-full.txt` are served at the docs site root (https://lawkeep.github.io/lawkeep/llms.txt, `/llms-full.txt`), plus Markdown copies of every website page, README, PLAN, ARCHITECTURE. They are **generated** by `scripts/build_llms_docs.py` from the templates in `scripts/`, the live CLI parsers, `action.yml`, the agent snippet, the report models and quoted doc sections; never edit them by hand. CI's `lint` job and `tests/test_docs_llms.py` run `--check` and fail when they are out of date (so changing an option, the snippet, `action.yml`, `docs/onboarding.html` or a quoted heading means rerunning the script). `scripts/` is ruff- and pyright-checked (standard mode). Not done: a `lawkeep` command that prints the reference (idea only).
- Docs website (2026-11-24, see `docs/PLAN.md` → Decisions): https://lawkeep.github.io/lawkeep/ is now the public user documentation, built with **Sphinx + Furo + MyST** from `docs/site/` (`uv sync --group docs`; `uv run sphinx-build -W --keep-going -b html docs/site _build/site`): getting started, concepts, guides, AI tools, writing laws, reference, FAQ/known limits, contributing, changelog. `docs/site/reference/commands.md`, `github-action.md`, `python-api.md` and `default-lawkeep.toml` are generated by `scripts/build_llms_docs.py` (drift-checked); every page is also published as `<page>.md`. The internal onboarding guide is at `/contributing/onboarding.html` (old `/onboarding.html` redirects). `docs/guide/` was folded into the site and removed. CI job `docs site` builds the site on every pull request (not a required check) with a non-blocking link check. The workflow `lawkeep init --ci` writes uses `lawkeep/lawkeep@v0`, which now exists (see "Moving major tag" below).
- CI runs only what a pull request touches (2026-11-24, see `docs/PLAN.md` → Decisions): a first `changes` job in `ci.yml` (plain `git diff` on the merge commit) skips tests / examples / action self-test unless code changed, `docs site` unless docs changed, `lint` unless either changed; `dependency review` runs only for manifests, `action.yml` or workflows. Job-level `if:` only (never workflow-level `paths:` with required checks); fails open; pushes to `main` run everything. Tables in `.github/workflows/AGENTS.md` and `CONTRIBUTING.md` → "What CI runs".
- Moving major tag (2026-11-24, see `docs/PLAN.md` → Decisions): `v0` is an annotated tag on the newest final 0.x release (created by hand on the `v0.1.0` commit; from then on moved by the `move major tag` job in `release.yml`, final `X.Y.Z` releases only, never backwards). `release.yml` starts only for full version tags (such as `v0.2.0`). Docs tell users `@v0` (gets 0.x fixes) or `@v0.1.0` (exact); `lawkeep init --ci` and the templates keep `@v0`.
- Next steps: add the PyPI trusted publisher, then try each agent by hand (issues exist for Codex, Cursor and Copilot).
- The online copy of the plan (Claude Doc) has not yet been updated with the 2026-11-20/21/22 decisions.
- Name reserved: GitHub org `lawkeep`, PyPI `lawkeep` 0.0.1 and npm `lawkeep` 0.0.1 (placeholders).
- Licence: Apache-2.0.

## Developer commands

```bash
uv sync --all-extras                                                 # install lawkeep + dev tools
uv run pytest -q                                                     # whole suite, about 6-7 minutes
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts  # lint and format
uv run pyright                                                       # type check: must report 0 errors
uv run python scripts/build_llms_docs.py                             # rebuild the LLM docs (--check in CI)
uv run lawkeep check                                                 # lawkeep's own laws: ALL LAWS HOLD
```

Type-checking conventions: `src/lawkeep` is strict (annotate everything, no unknown types; read JSON
from disk through `models.as_dict` / `models.as_list`; casts or Protocols at untyped third-party
boundaries). Silence an error only with `# pyright: ignore[rule]  # reason`; `# type: ignore` is
switched off (`enableTypeIgnoreComments = false`). For basedpyright in an editor:
`basedpyright --pythonpath .venv/bin/python` should match `uv run pyright`.

## Rules for agents

1. **Follow the plan.** If a change departs from `docs/PLAN.md`, stop and ask the maintainer, or update the plan in the same change and say so.
2. **Open questions stay open.** Items under "Open questions" and "Proposals under discussion" in the plan need a human decision. Ask; don't settle them silently.
3. **Honest wording.** Never call something "proven" or "foolproof" unless it reached level L4. The promise is: every law is checked, the AI never changes a law silently, weakening a law needs a person's yes, and weak laws get flagged. Never claim the AI *cannot* get around lawkeep.
4. **Fit the team, don't police it.** Don't design features that force a team process (mandatory reviews, branch protection and the like). Record and show; make stricter enforcement an optional extra, off by default.
5. **Wrap, don't rebuild.** Use Hypothesis, CrossHair, existing mutation testers and Dafny instead of re-implementing them.
6. **No private code.** Examples and tests use made-up projects only.
7. **Every folder has an `AGENTS.md`.** Each project folder (source, commands, adapters, tests, examples, docs, CI) contains a short `AGENTS.md`: what the folder is for, its key files, how it connects to other folders, conventions and gotchas, and how to test it. When you add a folder, add its `AGENTS.md`; when you change a folder's code, update its `AGENTS.md` in the same change. Exceptions (no `AGENTS.md` there):
   - any `laws/` folder and everything below it (e.g. `examples/*/laws/`): lawkeep fingerprints every file there, so an extra file is an unrecorded law change. Describe `laws/` in the parent folder's `AGENTS.md`;
   - inside the made-up fixture projects `tests/fixtures/<area>/<project>/` (tests copy them, and an `AGENTS.md` changes what `lawkeep init` finds). Describe them in `tests/fixtures/<area>/AGENTS.md`;
   - the repository's own lawkeep setup (`laws/`, `.claude/`): lawkeep checks itself (see "Current state");
   - `.github/ISSUE_TEMPLATE/`: GitHub would offer any `.md` file there as an issue template. Describe it in `.github/AGENTS.md`;
   - generated folders (`.venv`, `__pycache__`, `.hypothesis`, caches).
8. **Follow the naming conventions in [`CONTRIBUTING.md`](CONTRIBUTING.md).** Branches `<type>/<short-description>` off `main` (never commit to `main` directly), Conventional Commits for commits and PR titles, squash-merge, SemVer/PEP 440 versions, annotated `v<version>` tags, Keep a Changelog entries under `Unreleased` in the same change.
9. **Keep this file and the plan current.** When a decision is made or the state changes, update `docs/PLAN.md` (including "Decisions") and the "Current state" section above.

## Local machine setup

If `LOCAL-SETUP.md` exists in the repository root, read it: it holds machine-specific notes (accounts, remotes) and is not committed.

<!-- lawkeep:begin -->
## lawkeep: laws this code must obey

This project uses [lawkeep](https://github.com/lawkeep/lawkeep). Laws are rules the code must
obey for every input. Each law is one plain-English sentence plus an executable check, kept in
`laws/` and fingerprinted in `laws.lock`. People decide on laws; coding agents write code that
obeys them. Every law change is recorded and shown to the person.

1. **Before you finish any task, run `lawkeep check`** (or the `check` tool of the `lawkeep`
   MCP server; add `--json` for machine-readable output). It prints `ALL LAWS HOLD` or
   `SOME LAWS FAIL`. Result codes: 0 all laws hold, 1 some fail, 2 waiting for a person's
   decision, 3 setup problem.
2. **When a law fails, fix the code, not the law.** Every failure comes with the simplest
   failing example, for example `refund(charge=40, amount=50) returned 50, but a refund must
   never exceed the charge`. Read it, fix the code, and run `lawkeep check` again.
3. **Never change `laws/`, `laws.lock` or `lawkeep.toml` directly**: not with edit tools, not
   with shell commands. Do not add `conftest.py`, `sitecustomize.py`, `.pth` files, skip or xfail
   markers, or special cases for the failing input to get around a law; lawkeep flags all of
   these. To change a law, write the new version to a file under `laws/drafts/` and run
   `lawkeep propose <LAW_ID> --file laws/drafts/<file>.py --reason "<why>"`. Stricter changes
   may apply right away; anything that weakens a law waits for the person's yes.
4. **If a law conflicts with your task, stop and ask the person** (when they are there). Say
   which law, show the example that fails and what you would change. Stopping to ask is a
   successful outcome, not a failure. Nobody there? See "When no person is there" below.
5. **Run `lawkeep approve` only when the person asks you to**, after showing them the law's
   sentence and examples. Your coding agent will ask them to confirm the command; never
   approve a law change on your own.
6. **At the end of the session, show the person `lawkeep report`**: the law changes made in
   this session, anything changed outside lawkeep, and how many things wait for their
   decision in `lawkeep approve`.

### When no person is there (long runs on your own)

A person is there when they are chatting with you in this session. If you are unsure, read
`person_present` in `lawkeep check --json` (lawkeep's guess; it is `false` in CI, in
`claude -p` style runs and when `LAWKEEP_PERSON_PRESENT=0`). When nobody is there and a law
blocks you:

1. **Park it:** write the change you need to `laws/drafts/` and run `lawkeep propose
   <LAW_ID> --file laws/drafts/<file>.py --reason "<why>"`. Looser or unclear changes wait for
   the person; note the id it prints (`h-...`).
2. **Never work around the law:** do not edit `laws/`, `laws.lock` or `lawkeep.toml`, do not
   special-case the failing input, and never run `lawkeep approve`.
3. **Keep going** with every part of the task that does not depend on the blocked law.
   Leave the parts that do depend on it undone.
4. **End with a summary in three lists:** done; waiting for the person (each `h-...` id or
   draft, with one line on why); not done because a law blocked it. The person decides
   everything at once with `lawkeep approve`.
<!-- lawkeep:end -->
