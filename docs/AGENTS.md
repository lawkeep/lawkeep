# docs

- `PLAN.md`: the design source of truth (principles, concepts, scope, roadmap, Decisions, open
  questions). Read it before any work. Decisions made during the build are marked
  "(pending maintainer review)" until the maintainer decides.
- `ARCHITECTURE.md`: the code contract (data formats, module signatures, commands, call graph).
  Update it in the same change as any signature or format change.
- `OUTPUT-STYLE.md`: how every command talks to people (lead with the verdict, explain every
  number, glossary of the words to use, layout, plain vs colour mode). Follow it for any message,
  error or `--help` text; the code is `src/lawkeep/ui.py` and `src/lawkeep/explain.py`.
- `guide/`: user guides (non-technical, developer, recipes).
- `llms.txt`, `llms-full.txt`, `index.md`: **generated** LLM-friendly docs (llms.txt convention):
  the index, the whole reference in one Markdown file, and `onboarding.html` as Markdown. Built by
  `scripts/build_llms_docs.py` (see `scripts/AGENTS.md`); never edit them by hand. Published at
  the site root by `.github/workflows/pages.yml`, together with Markdown copies of `guide/*.md`,
  `PLAN.md`, `ARCHITECTURE.md`, `OUTPUT-STYLE.md`, README, CHANGELOG and CONTRIBUTING.
- `onboarding.html`: one self-contained HTML onboarding guide for new contributors (interns to
  seniors): concepts, every command, architecture with a diagram, repository tour, data formats,
  safety model, how to develop. Plain layer first, "Under the hood" boxes for detail. No external
  resources; light/dark via CSS variables. Written 2026-11-22 against the uncommitted v0.1 code
  (its last section lists what was not verified); section 3b "Long runs without a person"
  added 2026-11-23. Update it when commands, formats or modules change.

Conventions: plain English, concrete examples, honest wording (never "proven" below L4; the promise
is "the AI never changes your laws silently; weakening needs your yes").

Check: `tests/test_docs_llms.py` (and CI's `lint` job) fail when the generated LLM docs are out
of date: after changing `onboarding.html`, `ARCHITECTURE.md` sections 3, 4 or 7, or the quoted
sections of the guides or README, run `uv run python scripts/build_llms_docs.py`. Renaming a
heading the templates quote stops the build until the template is updated. `onboarding.html`'s
`<head>` links to `index.md` (rel alternate) and `llms.txt` (rel describedby). Otherwise no tests
read these files. After changing a command, a flag or a data format, compare
`ARCHITECTURE.md` and `guide/` with `uv run lawkeep <cmd> --help` and the code.
