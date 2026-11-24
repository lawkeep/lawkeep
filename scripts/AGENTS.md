# scripts

Repository tools that are not part of the installed `lawkeep` package (nothing here ships in
the wheel).

- `build_llms_docs.py`: builds every generated doc file:
  - the LLM-friendly docs (llms.txt convention, https://llmstxt.org) under `docs/`:
    `docs/llms.txt` (index: summary, key facts, result codes, rules for agents, links to the
    Markdown copies of the website pages), `docs/llms-full.txt` (the whole reference in one
    Markdown file, about 17k tokens) and `docs/onboarding.md` (`docs/onboarding.html` converted to
    Markdown with a small stdlib HTML parser);
  - the generated pages of the docs website: `docs/site/reference/commands.md` (every command and
    option from the live parsers, with the result codes from `docs/ARCHITECTURE.md` section 7),
    `docs/site/reference/github-action.md` (inputs and outputs of `action.yml`),
    `docs/site/reference/python-api.md` (`@law` and the `st` helpers: signatures and docstrings)
    and `docs/site/reference/default-lawkeep.toml` (`config.render_default_toml`, included by
    `reference/configuration.md`).
  `.github/workflows/pages.yml` publishes them (see `docs/site/AGENTS.md`).
- `llms.txt.template`, `llms-full.txt.template`: the hand-written prose of the two files. Their
  `{{...}}` directives are filled in by the script:
  - `{{section:FILE|HEADING LINE|SHIFT}}` (add `|own` to stop at the first sub-heading): the text
    under that exact heading in `README.md`, `docs/ARCHITECTURE.md` or a website page
    (`docs/site/**/*.md`), headings shifted by SHIFT levels, relative links made absolute (links to
    website pages point to their Markdown copy on the site, other files to GitHub);
  - `{{commands:LEVEL}}`: every command, usage and option from the live parsers
    (`lawkeep.cli.build_parser`), result codes from `docs/ARCHITECTURE.md` section 7;
  - `{{exit_codes}}` (`lawkeep.exitcodes`), `{{models}}` (field names of the report dataclasses in
    `lawkeep.models`), `{{law_api}}` (signatures of `@law` and the `st` helpers), `{{mcp}}`
    (`mcp_server.INSTRUCTIONS`, `TOOL_DESCRIPTIONS`, tool signatures), `{{snippet:SHIFT}}` (the
    agent instructions, `src/lawkeep/adapters/templates/agents_snippet.md`), `{{action}}`
    (inputs/outputs of `action.yml`, read without a YAML library), `{{default_toml}}`
    (`config.render_default_toml`), `{{version}}`, `{{site}}`, `{{repo}}`.

Run: `uv run python scripts/build_llms_docs.py` (write) or `--check` (exit 1 and a diff when a
committed file is out of date; exit 2 when a source no longer has the expected shape, for
example a quoted heading was renamed). CI runs `--check` in the `lint` job and
`tests/test_docs_llms.py` runs it in the test suite. The output was checked to be identical on
Python 3.10, 3.12 and 3.13 (`COLUMNS` is fixed; options are rendered from the parser's actions,
not from argparse's help text).

Gotchas:

- Never edit the generated files; edit the template or the source and run the script. Changing a
  command option, `action.yml`, the agent snippet, a report model, a docstring of `@law` or an
  `st` helper, the default `lawkeep.toml`, `docs/onboarding.html`, the quoted sections of
  `README.md` / `docs/ARCHITECTURE.md` / `docs/site/` or the version means running the script in
  the same change.
- Renaming a heading that a template quotes stops the build with a clear message: update the
  template.
- The script writes only through the named paths (`LLMS_TXT`, `LLMS_FULL_TXT`, `ONBOARDING_MD`,
  `SITE_COMMANDS_MD`, `SITE_ACTION_MD`, `SITE_API_MD`, `SITE_DEFAULT_TOML`):
  lawkeep's pre-tool-use guard reads scripts that agents run and refuses writes to paths it
  cannot see.
- Checked by ruff and pyright (standard mode) like `tests/`.
