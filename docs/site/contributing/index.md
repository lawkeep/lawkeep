# Contributing

lawkeep is open source (Apache-2.0) and contributions are welcome: code, docs, trying an agent we could
not run, or reporting what confused you.

- **How we work:** [CONTRIBUTING.md](https://github.com/lawkeep/lawkeep/blob/main/CONTRIBUTING.md):
  branch names, Conventional Commits, pull requests, versions and releases, and the checks to run before
  you open a pull request.
- **Something to work on:** issues labelled
  [good first issue](https://github.com/lawkeep/lawkeep/labels/good%20first%20issue) are small and come
  with steps; [help wanted](https://github.com/lawkeep/lawkeep/labels/help%20wanted) ones need someone
  with the right setup (for example Codex, Cursor or Copilot).
- **Questions and ideas:** [Discussions](https://github.com/lawkeep/lawkeep/discussions). Bugs and
  feature requests: [Issues](https://github.com/lawkeep/lawkeep/issues).
- **Security problems:** follow [SECURITY.md](https://github.com/lawkeep/lawkeep/blob/main/SECURITY.md);
  never open a public issue.
- **Code of Conduct:**
  [CODE_OF_CONDUCT.md](https://github.com/lawkeep/lawkeep/blob/main/CODE_OF_CONDUCT.md).

## Working on lawkeep's code

The **[onboarding guide for contributors](https://lawkeep.github.io/lawkeep/contributing/onboarding.html)** explains how lawkeep works inside: every
command, the architecture, a tour of the repository, the data formats and the safety model. It is
written for people who will change lawkeep's code; you do not need it to use lawkeep. (Also as
[Markdown](https://lawkeep.github.io/lawkeep/contributing/onboarding.md).)

Other internal documents, in the repository:

- [docs/PLAN.md](https://github.com/lawkeep/lawkeep/blob/main/docs/PLAN.md): the design source of truth
  (principles, roadmap, decisions, open questions);
- [docs/ARCHITECTURE.md](https://github.com/lawkeep/lawkeep/blob/main/docs/ARCHITECTURE.md): the code
  contract (data formats, module signatures, commands);
- [docs/OUTPUT-STYLE.md](https://github.com/lawkeep/lawkeep/blob/main/docs/OUTPUT-STYLE.md): how every
  command talks to people;
- [AGENTS.md](https://github.com/lawkeep/lawkeep/blob/main/AGENTS.md): instructions for coding agents
  working on lawkeep itself.

```bash
uv sync --all-extras
uv run pytest -q
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run pyright
uv run lawkeep check          # lawkeep checks its own laws
```

## This website

The site is built with Sphinx, the Furo theme and MyST Markdown from `docs/site/` in the repository.
Four reference files are generated from lawkeep's code by `scripts/build_llms_docs.py`. To build it
locally:

```bash
uv sync --group docs
uv run sphinx-build -W --keep-going -b html docs/site _build/site
```
