# Contributing to lawkeep

Thanks for helping. This page lists the conventions every change follows, so the history,
releases and the PyPI package stay predictable. New to the codebase? Start with
the [onboarding guide](https://lawkeep.github.io/lawkeep/contributing/onboarding.html) (source:
[`docs/onboarding.html`](docs/onboarding.html)) and [`AGENTS.md`](AGENTS.md).

- **Find something to work on:** issues labelled
  [`good first issue`](https://github.com/lawkeep/lawkeep/labels/good%20first%20issue) are small
  and come with steps; [`help wanted`](https://github.com/lawkeep/lawkeep/labels/help%20wanted)
  ones need someone with the right setup (for example a coding agent we could not run). Say in the
  issue that you are taking it. Milestones follow the roadmap in [`docs/PLAN.md`](docs/PLAN.md).
- **Questions and ideas:** [Discussions](https://github.com/lawkeep/lawkeep/discussions). Bugs and
  concrete features: the issue forms. Security problems: [`SECURITY.md`](SECURITY.md), never a
  public issue.
- **Docs website:** the user documentation is at
  [lawkeep.github.io/lawkeep](https://lawkeep.github.io/lawkeep/) (source: `docs/site/`, Sphinx +
  Furo + MyST; build it with `uv sync --group docs && uv run sphinx-build -W --keep-going -b html
  docs/site _build/site`). The onboarding guide for contributors is at
  [/contributing/onboarding.html](https://lawkeep.github.io/lawkeep/contributing/onboarding.html).
- Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Workflow in one picture

```
main  ──●────────●──────────●───────────●──  (always releasable; every commit passed CI)
         \      /            \         /  ↑
          feat/waiting-list   fix/ci-exit-code   tag v0.2.0 → release.yml → PyPI
```

1. Branch off `main` with a [branch name](#branch-names) like `feat/waiting-list`.
2. Commit with [Conventional Commits](#commit-messages).
3. Open a pull request; its title follows the same format. CI must pass.
4. **Squash-merge** into `main` (the PR title becomes the commit message). Delete the branch.
5. Releases are cut from `main` by pushing a [version tag](#versions-tags-and-releases).

## Branch names

`<type>/<short-description>` in lowercase kebab-case, using the commit types below.

| Example | For |
| --- | --- |
| `feat/waiting-list` | a new feature |
| `fix/ci-exit-code` | a bug fix |
| `docs/onboarding-guide` | documentation only |
| `refactor/one-law-runner` | code change without behaviour change |
| `test/tamper-pyc` | tests only |
| `ci/release-workflow` | CI/CD |
| `build/pyright-strict` | packaging, dependencies, tooling |
| `chore/update-lockfile` | maintenance |

- `main` is the only long-lived branch. Never commit to it directly except the very first commit.
- If an old version ever needs a fix, use a maintenance branch `release/<major>.<minor>.x`
  (e.g. `release/0.1.x`).
- Optional issue number: `fix/123-ci-exit-code`.

## Commit messages

[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<optional scope>): <summary>

<optional body: why, not how>

<optional footers, e.g. BREAKING CHANGE: ..., Refs: #123>
```

- **Types:** `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Scopes** (optional): a command or area, e.g. `check`, `approve`, `draft`, `propose`,
  `report`, `strength`, `guard`, `adapters`, `mcp`, `action`, `release`, `examples`.
- **Summary:** imperative mood ("add", not "added"), lowercase start, no full stop, at most
  72 characters.
- **Breaking changes:** `feat(check)!: ...` and a `BREAKING CHANGE:` footer. While lawkeep is 0.x,
  a breaking change raises the minor version.
- Examples: `feat(approve): show one waiting list`, `fix(ci): capture the gate's expected exit
  code`, `docs: add naming conventions`.

## Pull requests

- **Title:** same format as a commit message (it becomes the squash commit).
- Fill in the template: what changed, why, how it was tested, and the checklist (tests, ruff,
  pyright, `lawkeep check`, CHANGELOG, folder `AGENTS.md` files).
- One topic per PR. Keep the `Unreleased` section of `CHANGELOG.md` up to date in the same PR.

## Versions, tags and releases

| Thing | Convention | Example |
| --- | --- | --- |
| Version | [Semantic Versioning](https://semver.org/) written as [PEP 440](https://peps.python.org/pep-0440/) | `0.2.0`, `0.2.0a1`, `0.2.0rc1`, `1.0.0` |
| Where it lives | `__version__` in `src/lawkeep/__init__.py` (single source) | `__version__ = "0.2.0"` |
| Git tag | annotated, `v` + version, on a `main` commit | `git tag -a v0.2.0 -m "lawkeep 0.2.0"` |
| GitHub release | created by `release.yml`, title `lawkeep v<version>`, notes from `CHANGELOG.md` | `lawkeep v0.2.0` |
| PyPI | distribution, import and command are all `lawkeep` | `pip install lawkeep` |
| Changelog | [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/): `## [Unreleased]`, then `## [x.y.z] - YYYY-MM-DD` with `Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security` | `## [0.2.0] - 2027-01-15` |

**While lawkeep is 0.x:** minor (`0.2.0`) for new features or breaking changes, patch (`0.1.1`)
for fixes only. Pre-releases (`a`, `b`, `rc`) need `pip install --pre`.

**To release** (from an up-to-date `main`):

1. Open `chore/release-0.2.0`: bump `__version__`, move `Unreleased` in `CHANGELOG.md` to
   `## [0.2.0] - <date>`, update the compare links, and run `uv run python
   scripts/build_llms_docs.py` (the LLM docs name the version). Merge it.
2. `git tag -a v0.2.0 -m "lawkeep 0.2.0" && git push origin v0.2.0`.
3. `release.yml` runs every check, verifies the tag equals `__version__`, builds, publishes to
   PyPI with trusted publishing (environment `pypi`, no token), and creates the GitHub release.

Never reuse or move a published tag: PyPI never accepts the same version twice. A bad release is
fixed by a new patch version (and, if needed, yanking the bad one on PyPI).

## Other names

| Thing | Convention |
| --- | --- |
| Workflow files | lowercase kebab-case by purpose: `ci.yml`, `release.yml`, `nightly.yml`, `lawkeep.yml` |
| Workflow job names | short lowercase phrases: `lint`, `tests (Python 3.12)`, `publish to PyPI` |
| GitHub environments | named after the target: `pypi` (and `testpypi` if ever used) |
| Python modules | lowercase snake_case; private helpers start with `_` (`_boot.py`) |
| CLI commands and options | lowercase single words or kebab-case options (`--accept-unrecorded`) |
| Law ids | `<file stem>.<function name>`, e.g. `refunds.refund_is_capped` |

## Before you open a PR

```bash
uv sync --all-extras
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run pyright                 # must report 0 errors
uv run python scripts/build_llms_docs.py --check   # generated docs up to date (drop --check to rebuild)
uv run pytest -q               # about 9 minutes
uv run lawkeep check           # lawkeep's own laws: ALL LAWS HOLD
```

### pre-commit hooks (optional, recommended)

```bash
uv run pre-commit install         # once per clone
uv run pre-commit run --all-files # run every hook by hand
```

`pre-commit` is in the dev group for Python 3.11 and newer (the repository's default is 3.12;
on 3.10 one of its dependencies has an unfixed advisory).

`.pre-commit-config.yaml` runs whitespace and end-of-file fixes, YAML/TOML checks, a large-file
check, a merge-conflict check, ruff (lint and format, on `src/` and `tests/`) and lawkeep's own
pre-commit check (`uv run lawkeep hook pre-commit`). `pre-commit install` replaces
`.git/hooks/pre-commit`, which is where `lawkeep init` put that check, so the last hook keeps it
running: it shows law changes made outside lawkeep and only stops the commit if you set
`git config lawkeep.precommit block`. The hooks never touch `laws/`, `laws.lock` or
`examples/*/laws/` (lawkeep fingerprints them) or the planted-bug `*.patch` files.
`.editorconfig` sets the same basics for your editor (UTF-8, LF, 4 spaces for Python, 2 for
YAML/JSON/TOML).

Laws in this repository are changed only through lawkeep (`lawkeep propose` / `lawkeep approve`);
see `AGENTS.md`.
