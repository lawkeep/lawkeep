# .github/workflows

CI for the lawkeep repository itself (see `README.md` here for the table).

- `ci.yml`: tests on Python 3.10 / 3.12 / 3.13, ruff (on `src`, `tests`, `scripts`), pyright and
  the generated-docs drift check `scripts/build_llms_docs.py --check` (the `lint` job; pyright's
  version comes from `uv.lock` through `uv sync --locked`), the docs website build (job
  `docs site`: `uv sync --locked --group docs`, `sphinx-build -W --keep-going`, then a
  `linkcheck` step with `continue-on-error`; not a required check unless added to the ruleset),
  both examples through
  `lawkeep check`, each planted bug failing the gate, and a self-test of `action.yml`.
- `lawkeep.yml`: lawkeep checking its own repository (the root `laws/`, three laws about
  `lawkeep.exitcodes`). Installed by `lawkeep init`, fingerprinted in the root `laws.lock`, so it
  is protected: agents cannot edit it, and a hand edit shows up as an unrecorded law change.
- `nightly.yml`: deep search on the examples.
- `dependency-review.yml` (job `dependency review`): on pull requests, fails when a change adds a
  dependency with a known high-severity vulnerability.
- `pr-title.yml` (job `pr title`): PR titles must be Conventional Commits with the types from
  `CONTRIBUTING.md` and a summary that starts lowercase and has no full stop. Change the type list
  here and in `CONTRIBUTING.md` together.
- `scorecard.yml`: OpenSSF Scorecard weekly and on pushes to `main`; results go to the Security
  tab and the public badge. With `publish_results: true` the job may only use the actions
  Scorecard allows and the workflow may not set top-level `env`/`defaults`.
- `pages.yml`: builds the docs website with Sphinx from `docs/site/` (warnings are errors; every
  page also written as `<page>.md` by `docs/site/conf.py`) at the site root, adds
  `docs/llms.txt` and `docs/llms-full.txt` at the root, the internal onboarding guide at
  `contributing/onboarding.html` (links injected after the sidebar's `<div class="brand">` line;
  the build stops if that line changes) and `contributing/onboarding.md`, a redirect from the old
  `/onboarding.html`, and Markdown copies of PLAN, ARCHITECTURE, OUTPUT-STYLE, README, CHANGELOG and
  CONTRIBUTING, and deploys it to https://lawkeep.github.io/lawkeep/ on pushes to `main` that touch
  `docs/`, those root files, the agent snippet, `pyproject.toml`/`uv.lock` or the workflow.
  Pages must be set to "GitHub Actions" in the repository settings.
- The required status checks on `main` (ruleset) use the job names as GitHub shows them: renaming
  a job in `ci.yml`, `pr-title.yml` or `dependency-review.yml` means updating the ruleset too.
- `templates/`: workflows for users to copy (GitHub does not run files in sub-folders; see
  `templates/AGENTS.md`). `lawkeep init --ci` installs its own copy from
  `src/lawkeep/adapters/templates/lawkeep-workflow.yml`.
- `README.md`: the table of what runs where.

All three workflows use the local action (`uses: ./`, `lawkeep-spec: ${{ github.workspace }}`) and
may only pass inputs that the root `action.yml` defines. `ci.yml` repeats the local commands:
change it when the test or lint commands change.

These run only on GitHub; there is no local test for them (`uv run pre-commit run check-yaml
--all-files` checks their syntax).

## release.yml

Publishes lawkeep to PyPI when a `v*` tag is pushed: lint, pyright, full tests, tag must equal `lawkeep.__version__`, `uv build`, `twine check`, then upload with PyPI trusted publishing (environment `pypi`, no token) and a GitHub release. One-time PyPI setup: project lawkeep → Publishing → GitHub publisher (owner `lawkeep`, repo `lawkeep`, workflow `release.yml`, environment `pypi`). To release: bump `__version__`, add a `CHANGELOG.md` entry, commit, tag `v<version>`, push the tag.
