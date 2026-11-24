"""The LLM docs (docs/llms.txt, docs/llms-full.txt, docs/index.md) are generated and up to date.

They are built by scripts/build_llms_docs.py from the CLI parsers, action.yml, the agent
instructions template, the report models and the docs. When this test fails, run
`uv run python scripts/build_llms_docs.py` and commit the result.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "build_llms_docs.py"
DOCS = REPO / "docs"


def test_generated_llm_docs_are_up_to_date() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_llms_txt_follows_the_convention() -> None:
    text = (DOCS / "llms.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "# lawkeep"  # H1 with the project name, first
    first_block = next(line for line in lines[1:] if line.strip())
    assert first_block.startswith("> ")  # then the blockquote summary
    sections = [line for line in lines if line.startswith("## ")]
    assert sections[0] == "## Docs" and sections[-1] == "## Optional"
    assert not [line for line in lines if line.startswith("### ")]  # only H1 and H2 headings
    links = re.findall(r"^- \[[^\]]+\]\((https://lawkeep\.github\.io/lawkeep/[^)]+)\)", text, re.M)
    assert links and all(link.endswith((".md", ".txt")) for link in links)


def test_full_reference_lists_every_command_and_option() -> None:
    from lawkeep import cli

    text = (DOCS / "llms-full.txt").read_text(encoding="utf-8")
    for name in cli.COMMANDS:
        assert f"### lawkeep {name}\n" in text
    for option in ("--accept-unrecorded", "--deep-check", "--no-protection", "--dry-run"):
        assert f"`{option}`" in text
    assert "When no person is there" in text  # the agent instructions are included
    assert "`fail-on-broken-laws`" in text  # the action inputs are included
    assert "<div" not in text and "<table" not in text  # plain Markdown, no HTML
