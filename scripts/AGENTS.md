# scripts

Repository tools that are not part of the installed `lawkeep` package (nothing here ships in
the wheel).

- `build_llms_docs.py`: builds the LLM-friendly docs (llms.txt convention, https://llmstxt.org)
  and writes them under `docs/`: `docs/llms.txt` (index: summary, key facts, result codes, rules
  for agents, links), `docs/llms-full.txt` (the whole reference in one Markdown file, about 17k
  tokens) and `docs/index.md` (`docs/onboarding.html` converted to Markdown with a small
  stdlib HTML parser). `.github/workflows/pages.yml` copies them to the site root.
- `llms.txt.template`, `llms-full.txt.template`: the hand-written prose of the two files. Their
  `{{...}}` directives are filled in by the script:
  - `{{section:FILE|HEADING LINE|SHIFT}}` (add `|own` to stop at the first sub-heading): the text
    under that exact heading in `README.md`, `docs/ARCHITECTURE.md` or `docs/guide/*.md`, headings
    shifted by SHIFT levels, relative links made absolute;
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
  command option, `action.yml`, the agent snippet, a report model, `docs/onboarding.html`, the
  quoted sections of `README.md` / `docs/ARCHITECTURE.md` / `docs/guide/` or the version means
  running the script in the same change.
- Renaming a heading that a template quotes stops the build with a clear message: update the
  template.
- The script writes only through the three named paths (`LLMS_TXT`, `LLMS_FULL_TXT`, `INDEX_MD`):
  lawkeep's pre-tool-use guard reads scripts that agents run and refuses writes to paths it
  cannot see.
- Checked by ruff and pyright (standard mode) like `tests/`.
