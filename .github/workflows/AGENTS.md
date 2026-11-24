# .github/workflows

CI for the lawkeep repository itself (see `README.md` here for the table).

- `ci.yml`: tests on Python 3.10 / 3.12 / 3.13, ruff (on `src`, `tests`, `scripts`), pyright and
  the generated-docs drift check `scripts/build_llms_docs.py --check` (the `lint` job; pyright's
  version comes from `uv.lock` through `uv sync --locked`), the docs website build (job
  `docs site`: `uv sync --locked --group docs`, `sphinx-build -W --keep-going`, then a
  `linkcheck` step with `continue-on-error`; a required check on `main`),
  both examples through
  `lawkeep check`, each planted bug failing the gate, and a self-test of `action.yml`.

  **Only what the change touches runs on pull requests.** The first job, `changes`, lists the
  files with `git diff --name-only HEAD^1 HEAD` on GitHub's merge commit (so exactly what merging
  would change; no third-party action, no API call) and sets two outputs:

  | Output | True when the PR changes |
  | --- | --- |
  | `code` | `src/`, `tests/`, `examples/`, `laws/`, `scripts/`, `.github/workflows/`, `lawkeep.toml`, `laws.lock`, `pyproject.toml`, `uv.lock`, `action.yml`, `.pre-commit-config.yaml` |
  | `docs` | `docs/`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, plus what the docs build and `scripts/build_llms_docs.py` read: `src/`, `scripts/`, `action.yml`, `pyproject.toml`, `uv.lock`, `.github/workflows/` |

  | Job | Runs when |
  | --- | --- |
  | `lint` (ruff, pyright, generated-docs drift check) | `code` or `docs` |
  | `tests (Python 3.10/3.12/3.13)`, `example projects through the gate`, `lawkeep action on examples/billing` | `code` |
  | `docs site` | `docs` |

  Pushes to `main` and `workflow_dispatch` runs always run every job. Gotchas: jobs are skipped
  with a **job-level `if:`** (a skipped job reports "Skipped", which satisfies a required status
  check); never add workflow-level `paths:`/`paths-ignore:` to a workflow with required checks, or
  the checks wait forever. Never skip a **matrix** job with `if:` either: GitHub then reports one
  check named `tests (Python ${{ matrix.python-version }})` and the per-version required checks
  never report; that is why the tests are three jobs (`test-py310`, `test-py312`, `test-py313`)
  sharing their steps through a YAML anchor (`&test-steps`). Each `if:` is
  `!cancelled() && needs.changes.outputs.<kind> != 'false'`,
  so if the `changes` job fails the jobs run instead of being skipped (fail open). When a new kind
  of file starts to matter to a job (a new folder, a file the docs build reads), add it to the
  pattern in the `changes` job and to the table above and in `CONTRIBUTING.md` → "What CI runs".
- `lawkeep.yml`: lawkeep checking its own repository (the root `laws/`, three laws about
  `lawkeep.exitcodes`). Installed by `lawkeep init`, fingerprinted in the root `laws.lock`, so it
  is protected: agents cannot edit it, and a hand edit shows up as an unrecorded law change.
- `nightly.yml`: deep search on the examples.
- `dependency-review.yml` (job `dependency review`): on pull requests, fails when a change adds a
  dependency with a known high-severity vulnerability. A first job `dependency changes` skips the
  review (job-level `if:`, so the required check reports Skipped) unless the PR touches a manifest
  (`pyproject.toml`, `uv.lock`, `requirements*.txt`, `setup.py`, `setup.cfg`, anywhere), an
  `action.yml` or a workflow.
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
  `docs/`, those root files, the agent snippet, `src/lawkeep/__init__.py` (the version on the
  site), `pyproject.toml`/`uv.lock` or the workflow (workflow-level `paths:` is fine here: it runs
  only on pushes and has no required check).
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

Publishes lawkeep to PyPI when a full version tag is pushed (trigger `v*.*.*`, so never the moving `v0`): lint, pyright, full tests, tag must equal `lawkeep.__version__`, `uv build`, `twine check`, then upload with PyPI trusted publishing (environment `pypi`, no token) and a GitHub release. Last, job `move major tag` (`contents: write`) force-moves the annotated tag `v<major>` ("lawkeep v0 (moving major tag; currently v0.x.y)") to the released commit, only for a final `X.Y.Z` release that is the newest of its major version; it does nothing when the tag is already there (idempotent). Users' `uses: lawkeep/lawkeep@v0` resolves through that tag. One-time PyPI setup: project lawkeep → Publishing → GitHub publisher (owner `lawkeep`, repo `lawkeep`, workflow `release.yml`, environment `pypi`). To release: bump `__version__`, add a `CHANGELOG.md` entry, commit, tag `v<version>`, push the tag.
