# Contributing to lawkeep

Thanks for helping. This page lists the conventions every change follows, so the history,
releases and the PyPI package stay predictable. New to the codebase? Start with
[`docs/onboarding.html`](docs/onboarding.html) and [`AGENTS.md`](AGENTS.md).

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
   `## [0.2.0] - <date>`, update the compare links. Merge it.
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
uv run ruff check src tests && uv run ruff format --check src tests
uv run pyright                 # must report 0 errors
uv run pytest -q               # about 9 minutes
uv run lawkeep check           # lawkeep's own laws: ALL LAWS HOLD
```

Laws in this repository are changed only through lawkeep (`lawkeep propose` / `lawkeep approve`);
see `AGENTS.md`.
