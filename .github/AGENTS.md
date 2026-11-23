# .github

GitHub settings for the lawkeep repository itself: `workflows/` (CI, release, the nightly deep
search and copy-me templates for users; see `workflows/AGENTS.md`), `pull_request_template.md`
(PR checklist; PR titles follow Conventional Commits) and `dependabot.yml` (weekly update PRs for
GitHub Actions and `uv.lock`, titled `ci(deps): ...` / `build(deps): ...`). Naming conventions:
`CONTRIBUTING.md` in the repository root.

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
