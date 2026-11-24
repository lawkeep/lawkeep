# docs/site

lawkeep's public documentation website, https://lawkeep.github.io/lawkeep/ : Sphinx with the Furo
theme and MyST Markdown (decided 2026-11-24, see `docs/PLAN.md` → Decisions). Audience: developers
and non-technical people who use a coding agent. Plain language per `docs/OUTPUT-STYLE.md`; honest
wording (never "proven" below L4; say what is untested).

- `conf.py`: Sphinx settings, plus a `build-finished` hook that writes every page next to its HTML
  as plain Markdown (`concepts/laws.md`), with `{include}`/`{literalinclude}` expanded, toctrees
  removed and `:::{note}`-style admonitions turned into blockquotes. `llms.txt` links to those copies.
- `index.md` (home, holds the toctrees that make the sidebar), `getting-started.md`, `faq.md`
  (FAQ and known limits), `changelog.md` (includes the root `CHANGELOG.md`).
- `concepts/`, `guides/`, `agents/`, `writing-laws/`, `reference/`, `contributing/`: one page per
  topic. `agents/index.md` includes `src/lawkeep/adapters/templates/agents_snippet.md`.
- **Generated, never edit by hand** (by `scripts/build_llms_docs.py`, drift-checked in CI):
  `reference/commands.md` (live argparse parsers), `reference/github-action.md` (`action.yml`),
  `reference/python-api.md` (`@law` and `st` signatures and docstrings),
  `reference/default-lawkeep.toml` (included by `reference/configuration.md`).
- Quoted in `docs/llms-full.txt`: `writing-laws/index.md` `## Writing a law`,
  `writing-laws/weak-laws.md` `## Traps`, `guides/long-runs.md` `## What the agent does`,
  `## How an agent knows whether a person is there`, `## One waiting list`. Keep those sections
  plain Markdown (no MyST directives); after editing them run
  `uv run python scripts/build_llms_docs.py`. Renaming them means updating
  `scripts/llms-full.txt.template`.

Conventions: link between pages with relative `.md` links (MyST resolves them and `-W` fails on a
broken one, anchors included: `myst_heading_anchors = 3`); link to the onboarding guide with its full
URL (it is not a Sphinx page); use colon fences (`:::{note}`) for admonitions; no sphinx-design
(the Markdown copies stay readable). Facts must match the code: commands and options come from the
generated `reference/commands.md`; compare other claims with `lawkeep <cmd> --help`,
`docs/ARCHITECTURE.md` and the adapters' docstrings.

The `docs` dependency group carries the marker `python_full_version >= '3.11.5'` (soupsieve, pulled in by
furo, has no fixed release for 3.10; dependency review fails otherwise). Build the site on 3.12.

Build and check:

```bash
uv sync --group docs
uv run sphinx-build -W --keep-going -b html docs/site _build/site   # warnings are errors
uv run python scripts/build_llms_docs.py --check                    # generated pages up to date
```

CI: the `docs` job (`docs site`) in `.github/workflows/ci.yml` builds the site on every pull request
that touches `docs/` or a file the site or the generated pages are made from (plus a
non-blocking link check); `.github/workflows/pages.yml` publishes it from `main`.
