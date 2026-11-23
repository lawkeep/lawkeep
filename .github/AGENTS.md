# .github

GitHub settings for the lawkeep repository itself: `workflows/` (CI, release, the nightly deep
search and copy-me templates for users; see `workflows/AGENTS.md`), `pull_request_template.md`
(PR checklist; PR titles follow Conventional Commits) and `dependabot.yml` (weekly update PRs for
GitHub Actions and `uv.lock`, titled `ci(deps): ...` / `build(deps): ...`, labelled `ci` / `build`;
Gotcha: an Actions update also edits the protected `workflows/lawkeep.yml`, which makes the
`laws` check fail until a person records that change through lawkeep). Naming conventions:
`CONTRIBUTING.md` in the repository root.

Also here: `ISSUE_TEMPLATE/` (issue forms `bug_report.yml` and `feature_request.yml`, which add the
labels `bug`/`feature` + `needs triage`, and `config.yml`: blank issues off, links to Discussions
and to private security advisories) and `CODEOWNERS` (`* @abhishek19273`: GitHub asks the
maintainer to review every PR in this repository; nothing to do with lawkeep's users).
`ISSUE_TEMPLATE/` has no `AGENTS.md` on purpose: GitHub would offer any `.md` file there as an
issue template. Labels named in the forms must exist in the repository (GitHub ignores unknown
ones); the label set is described in `docs/PLAN.md` → Decisions (2026-11-23, repository setup).

- Nothing here runs locally. CI, the lawkeep workflow and the v0.1.0 release ran on GitHub on 2026-11-23.
- The workflows use the composite action in the repository root (`action.yml`, `uses: ./`).
- lawkeep checks itself (decided 2026-11-22): `workflows/lawkeep.yml` was installed by
  `lawkeep init` for this repository, is fingerprinted in the root `laws.lock` and uses the local
  action (`uses: ./`, `lawkeep-spec: "."`). Agents cannot edit it (the guard blocks it); a person
  changes it and records the change through lawkeep.
- Gotcha: the Copilot adapter writes `copilot-instructions.md` and `hooks/` into `.github/`, and
  their presence makes `init` detect Copilot. Do not add those here: this repository's lawkeep
  setup is for Claude Code only.

Test: there is no local test for this folder; `ci.yml` is exercised only on GitHub.
