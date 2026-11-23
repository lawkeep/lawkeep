# Changelog

All notable changes to lawkeep are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (written as PEP 440
versions). While lawkeep is 0.x, a minor version may change behaviour.

## [Unreleased]

### Added

- `CONTRIBUTING.md` with the project's naming conventions (branches, Conventional Commits, pull
  requests, versions, tags, releases, changelog), a pull request template, `SECURITY.md` and
  Dependabot updates for GitHub Actions and Python dependencies.

### Fixed

- CI: the planted-bug step now captures the gate's expected exit code under `bash -e`.

## [0.1.0] - 2026-11-23

First real release (0.0.1 was a name placeholder). Status: **alpha**, see README → "Known limits".

### Added

- **Laws:** `@law("plain-English sentence", inputs={...})` on pytest + Hypothesis tests.
- **Commands:** `init`, `draft` (a separate session of your own coding agent writes laws),
  `approve` (one waiting list: drafts, proposals, drafting-agent edits, unrecorded edits,
  unconfirmed approvals), `check` (the gate: `ALL LAWS HOLD` / `SOME LAWS FAIL`), `strength`
  (planted bugs, one-sided and vacuous laws), `propose` (stricter changes apply automatically,
  weakening waits for a person), `report` (law changes and "only review what your laws don't
  protect"), `hook`, `mcp`.
- **Law history:** `laws.lock` fingerprints and the append-only `laws/history.jsonl`; laws changed
  outside lawkeep are flagged.
- **Safety:** isolated law runs (`python -I -S -B`, one-way results pipe), side-door checks,
  deterministic verdicts, a cheating test suite.
- **Agents:** adapters for Claude Code, Codex, Cursor and GitHub Copilot on a shared base (CLI,
  MCP server, `AGENTS.md` instructions, git pre-commit hook); rules for long runs without a
  person.
- **CI:** a GitHub Action that runs the gate and posts one report comment (never blocks merges by
  itself); a tag-triggered release workflow with PyPI trusted publishing.
- **Output:** plain-English terminal screens (Rich); `--json` for agents everywhere.
- **Typed:** strict pyright; ships `py.typed`.

Not yet verified: real runs of the Codex, Cursor and Copilot adapters; Windows; the private pilot,
non-technical tester and 30-task evaluation (see `docs/PLAN.md`).

[Unreleased]: https://github.com/lawkeep/lawkeep/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lawkeep/lawkeep/releases/tag/v0.1.0
