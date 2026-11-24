# Workflows

| File | Runs in this repository? | What it does |
| --- | --- | --- |
| `ci.yml` | yes, on pushes to `main` (every job) and pull requests (only the jobs whose files the change touches; see `AGENTS.md` here) | Tests (Python 3.10, 3.12, 3.13, including the cheating test suite), ruff, pyright (type check), the generated-docs drift check, the docs website build (job `docs site`, with a non-blocking link check), both example projects through `lawkeep check`, each planted bug failing the gate, and a self-test of `action.yml` on `examples/billing`. |
| `lawkeep.yml` | yes, on pull requests, pushes to `main` and nightly | lawkeep checking its own laws (the root `laws/`), with the action and package from this checkout. Installed by `lawkeep init`; protected by `laws.lock`. |
| `nightly.yml` | yes, nightly | `lawkeep check --profile deep` on both examples; uploads the report and any newly saved failing examples. |
| `dependency-review.yml` | yes, on pull requests that change a dependency manifest, `action.yml` or a workflow (skipped otherwise) | Fails if a change adds a dependency with a known high-severity vulnerability. |
| `pr-title.yml` | yes, on pull requests | Checks the PR title follows Conventional Commits (see `CONTRIBUTING.md`). |
| `scorecard.yml` | yes, weekly and on pushes to `main` | OpenSSF Scorecard supply-chain checks; publishes the README badge. |
| `pages.yml` | yes, on pushes to `main` that change `docs/`, README, CHANGELOG, CONTRIBUTING, the agent snippet, the version or the docs dependencies | Builds the docs website (Sphinx + Furo + MyST from `docs/site/`) and publishes it to https://lawkeep.github.io/lawkeep/, with `llms.txt` / `llms-full.txt` at the root and the onboarding guide at `/contributing/onboarding.html`. |
| `templates/lawkeep.yml` | no (GitHub only runs files directly in this folder) | Copy into your project: checks laws on every pull request and posts one comment. |
| `templates/lawkeep-nightly.yml` | no | Copy into your project: nightly deep search. |

The templates use `lawkeep/lawkeep@v0`: a moving tag that `release.yml` moves to every final
0.x release, so it picks up fixes. To change only when you say so, pin an exact release
(`@v0.1.0`) or a commit SHA.
