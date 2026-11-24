"""Build lawkeep's LLM-friendly docs: ``docs/llms.txt``, ``docs/llms-full.txt``, ``docs/index.md``.

The files follow the llms.txt convention (https://llmstxt.org) and are published at the root of
the docs site (https://lawkeep.github.io/lawkeep/) by ``.github/workflows/pages.yml``.

They are generated, never edited by hand, from:

- ``scripts/llms.txt.template`` and ``scripts/llms-full.txt.template`` (the hand-written prose),
  whose ``{{...}}`` directives pull in
- sections of ``README.md``, ``docs/ARCHITECTURE.md`` and ``docs/guide/*.md`` (by heading),
- the live CLI parsers (``lawkeep.cli.build_parser``), so every option is the real one,
- ``lawkeep.exitcodes``, the report dataclasses in ``lawkeep.models``, the ``@law`` signature and
  the ``st`` helpers, the MCP server's instructions and tools (``lawkeep.mcp_server``),
- the agent instructions snippet (``src/lawkeep/adapters/templates/agents_snippet.md``),
- the inputs and outputs of ``action.yml``,
- ``docs/onboarding.html`` (converted to Markdown as ``docs/index.md``).

Usage::

    uv run python scripts/build_llms_docs.py           # write the files
    uv run python scripts/build_llms_docs.py --check   # exit 1 if a committed file is out of date

CI runs ``--check`` in the ``lint`` job.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import inspect
import os
import re
import sys
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The generated files. They are written only through these names, so the write targets are plain
# to see (lawkeep's own pre-tool-use guard reads the scripts agents run and refuses unclear writes).
LLMS_TXT = ROOT / "docs" / "llms.txt"
LLMS_FULL_TXT = ROOT / "docs" / "llms-full.txt"
INDEX_MD = ROOT / "docs" / "index.md"
SITE = "https://lawkeep.github.io/lawkeep"
REPO = "https://github.com/lawkeep/lawkeep"
SCRIPT = "scripts/build_llms_docs.py"
UPDATE_HINT = f"run `uv run python {SCRIPT}` to update them, then commit the result"

# argparse wraps help at the terminal width; keep everything independent of the caller's terminal.
os.environ["COLUMNS"] = "100"
sys.path.insert(0, str(ROOT / "src"))

from lawkeep import __version__, cli, exitcodes, mcp_server, models  # noqa: E402
from lawkeep import _law as law_module  # noqa: E402  # pyright: ignore[reportPrivateUsage]
from lawkeep import strategies as st_module  # noqa: E402
from lawkeep.adapters import base as adapters_base  # noqa: E402


class BuildError(Exception):
    """A source file no longer has the shape the generator expects."""


# ---------------------------------------------------------------------------------------------
# Markdown helpers


def _heading_level(line: str) -> int:
    m = re.match(r"^(#{1,6}) ", line)
    return len(m.group(1)) if m else 0


def _iter_lines_outside_fences(lines: list[str]) -> list[tuple[str, bool]]:
    """Each line with a flag: True when it is outside a fenced code block."""
    out: list[tuple[str, bool]] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        m = re.match(r"^(```+|~~~+)", stripped)
        if fence is None and m:
            fence = m.group(1)
            out.append((line, False))
        elif fence is not None and stripped.startswith(fence):
            fence = None
            out.append((line, False))
        else:
            out.append((line, fence is None))
    return out


def section_body(rel_path: str, heading: str, shift: int, *, own_text_only: bool = False) -> str:
    """The text under ``heading`` (an exact heading line) up to the next heading of the same or a
    higher level (any heading with ``own_text_only``), with the headings inside shifted by
    ``shift`` levels."""
    lines = (ROOT / rel_path).read_text(encoding="utf-8").splitlines()
    marked = _iter_lines_outside_fences(lines)
    start = None
    for i, (line, outside) in enumerate(marked):
        if outside and line.rstrip() == heading:
            start = i
            break
    if start is None:
        raise BuildError(f"heading {heading!r} not found in {rel_path}")
    level = _heading_level(heading)
    body: list[str] = []
    for line, outside in marked[start + 1 :]:
        lvl = _heading_level(line) if outside else 0
        if lvl and (lvl <= level or own_text_only):
            break
        if lvl:
            new = max(1, min(6, lvl + shift))
            line = "#" * new + line[lvl:]
        body.append(line)
    text = "\n".join(body).strip("\n")
    return _relink(text, rel_path)


def _relink(text: str, rel_path: str) -> str:
    """Turn relative Markdown links into absolute GitHub links, so they work anywhere."""
    base = Path(rel_path).parent

    def fix(m: re.Match[str]) -> str:
        label, target = m.group(1), m.group(2)
        if re.match(r"^[a-z]+:|^#", target):
            return m.group(0)
        path, _, anchor = target.partition("#")
        resolved = os.path.normpath(base / path).replace(os.sep, "/")
        kind = (
            "tree" if resolved.endswith("/") or "." not in resolved.rsplit("/", 1)[-1] else "blob"
        )
        url = f"{REPO}/{kind}/main/{resolved}" + (f"#{anchor}" if anchor else "")
        return f"[{label}]({url})"

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", fix, text)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# Commands (live argparse parsers)


def _subparsers() -> dict[str, argparse.ArgumentParser]:
    parser = cli.build_parser()
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]  # argparse has no public accessor
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]  # same
            choices: dict[str, argparse.ArgumentParser] = action.choices  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]  # typeshed leaves it loose
            return {name: choices[name] for name in cli.COMMANDS}
    raise BuildError("lawkeep.cli.build_parser() has no subcommands")


def _actions(p: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        a
        for a in p._actions  # pyright: ignore[reportPrivateUsage]  # argparse has no public accessor
        if not isinstance(a, argparse._HelpAction) and a.help != argparse.SUPPRESS  # pyright: ignore[reportPrivateUsage]  # same
    ]


def _value_text(a: argparse.Action) -> str:
    if a.nargs == 0:
        return ""
    if a.choices is not None:
        return "{" + ",".join(str(c) for c in a.choices) + "}"
    metavar = a.metavar if isinstance(a.metavar, str) else None
    if not a.option_strings:
        return metavar or a.dest.upper()
    return metavar or a.dest.upper()


def _usage_part(a: argparse.Action) -> str:
    value = _value_text(a)
    if not a.option_strings:
        if a.nargs == "*":
            return f"[{value} ...]"
        if a.nargs == "?":
            return f"[{value}]"
        if a.nargs == "+":
            return f"{value} [{value} ...]"
        return value
    flag = a.option_strings[0]
    repeat = " ..." if isinstance(a, argparse._AppendAction) or a.nargs in ("*", "+") else ""  # pyright: ignore[reportPrivateUsage]  # argparse has no public class
    text = f"{flag} {value}{repeat}" if value else flag
    return text if a.required else f"[{text}]"


def _usage(name: str, p: argparse.ArgumentParser) -> str:
    acts = [a for a in _actions(p) if a.dest not in ("json", "root")]
    groups = [
        g._group_actions  # pyright: ignore[reportPrivateUsage]  # argparse has no public accessor
        for g in p._mutually_exclusive_groups  # pyright: ignore[reportPrivateUsage]  # same
    ]
    parts: list[str] = []
    done: set[int] = set()
    for a in acts:
        if id(a) in done:
            continue
        group = next((g for g in groups if a in g), None)
        if group is not None and a.option_strings:
            members = [m for m in group if m in acts]
            done.update(id(m) for m in members)
            inner = [_usage_part(m).strip("[]") for m in members]
            parts.append("[" + " | ".join(inner) + "]")
        else:
            done.add(id(a))
            parts.append(_usage_part(a))
    return " ".join(["lawkeep", name, *parts, "[--json] [--root PATH]"])


def _option_row(a: argparse.Action) -> list[str]:
    value = _value_text(a)
    if a.option_strings:
        name = ", ".join(f"`{o}`" for o in a.option_strings)
        if value:
            name += f" `{value}`"
        if isinstance(a, argparse._AppendAction):  # pyright: ignore[reportPrivateUsage]  # argparse has no public class
            name += " (repeatable)"
        elif a.nargs in ("*", "+"):
            name += " (one or more)"
    else:
        name = f"`{value}` (positional" + (", optional)" if a.nargs in ("?", "*") else ")")
        if a.nargs == "*":
            name = f"`{value} ...` (positional, zero or more)"
    help_text = (a.help or "").replace("%%", "%")
    if "%(" in help_text:
        help_text = help_text % {"default": a.default, "prog": "lawkeep", "choices": a.choices}
    return [name, help_text]


def _result_codes_from_architecture() -> dict[str, str]:
    text = section_body("docs/ARCHITECTURE.md", "## 7. Commands (as built)", 0)
    codes: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\| `([a-z-]+)` \|", line)
        if not m:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        codes[m.group(1)] = cells[-1].replace("\\|", "|")
    return codes


def render_commands(heading_level: int) -> str:
    hashes = "#" * heading_level
    codes = _result_codes_from_architecture()
    out: list[str] = [
        "Every command also takes `--json` (print exactly one JSON document on stdout, nothing "
        "else) and `--root PATH` (project folder; default: search upward from the current folder "
        "for `lawkeep.toml`, else `laws/`; env `LAWKEEP_ROOT` is used when set). `lawkeep "
        "--version` prints the version. Bad usage exits with 3, never 2.",
        "",
        md_table(
            ["Command", "What it does"],
            [[f"`{n}`", p.description or ""] for n, p in _subparsers().items()],
        ),
    ]
    for name, p in _subparsers().items():
        out += ["", f"{hashes} lawkeep {name}", "", p.description or "", ""]
        out += ["```text", _usage(name, p), "```", ""]
        rows = [_option_row(a) for a in _actions(p) if a.dest not in ("json", "root")]
        if rows:
            out.append(md_table(["Option", "Meaning"], rows))
        else:
            out.append("No options besides `--json` and `--root`.")
        if name in codes:
            out += ["", f"Result codes: {codes[name]}"]
        else:
            raise BuildError(f"no row for `{name}` in docs/ARCHITECTURE.md section 7")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# Result codes, models, @law, st, MCP, snippet, action.yml


def render_exit_codes() -> str:
    meaning = {
        exitcodes.ALL_HOLD: "all laws hold (other commands: done)",
        exitcodes.SOME_FAIL: "some laws fail (or a law could not run)",
        exitcodes.WAITING: "waiting for a person's decision (unrecorded law change, side door, "
        "waiting proposal or draft)",
        exitcodes.SETUP_PROBLEM: "setup problem (no project, bad lawkeep.toml, missing tool, "
        "bad usage, crash)",
    }
    rows = [
        [str(code), exitcodes.VERDICTS[code], meaning[code]] for code in sorted(exitcodes.VERDICTS)
    ]
    order = " > ".join(str(c) for c in exitcodes._PRECEDENCE)  # pyright: ignore[reportPrivateUsage]  # the one source of the order
    return (
        md_table(["Code", "Verdict", "Meaning"], rows)
        + f"\n\nWhen several apply, the most important wins: {order} "
        "(`lawkeep.exitcodes.combine`)."
    )


REPORT_MODELS: list[tuple[str, type]] = [
    ("CheckReport (`check`)", models.CheckReport),
    ("LawResult", models.LawResult),
    ("IntegrityIssue", models.IntegrityIssue),
    ("LawChange", models.LawChange),
    ("ExampleRow", models.ExampleRow),
    ("StrengthReport (`strength`)", models.StrengthReport),
    ("StrengthResult", models.StrengthResult),
    ("LawChangeReport (`report`)", models.LawChangeReport),
    ("ProtectionReport", models.ProtectionReport),
    ("ProtectionResult", models.ProtectionResult),
    ("ProposalResult (`propose`)", models.ProposalResult),
    (
        "SimpleReport (`init`, `draft`, `approve`, `hook`, errors, MCP `list_laws`)",
        models.SimpleReport,
    ),
    ("LawInfo (MCP `list_laws` `data.laws`)", models.LawInfo),
    ("HistoryEntry (`laws/history.jsonl` line)", models.HistoryEntry),
]


def render_models() -> str:
    out: list[str] = []
    for title, cls in REPORT_MODELS:
        if not dataclasses.is_dataclass(cls):
            raise BuildError(f"{cls.__name__} is no longer a dataclass")
        names = [f"`{f.name}`" for f in dataclasses.fields(cls)]
        out.append(f"- **{title}**: " + ", ".join(names))
    return "\n".join(out)


def _signature(fn: Callable[..., object], name: str) -> str:
    sig = inspect.signature(fn)
    parts: list[str] = []
    star_done = False
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.KEYWORD_ONLY and not star_done:
            parts.append("*")
            star_done = True
        text = p.name
        if p.annotation is not inspect.Parameter.empty:
            ann = (
                p.annotation
                if isinstance(p.annotation, str)
                else getattr(p.annotation, "__name__", str(p.annotation))
            )
            text += f": {ann.strip(chr(39))}"
        if p.default is not inspect.Parameter.empty:
            text += f" = {p.default!r}"
        parts.append(text)
    ret = sig.return_annotation
    ret_text = "" if ret is inspect.Signature.empty else f" -> {str(ret).strip(chr(39))}"
    return f"{name}({', '.join(parts)}){ret_text}"


def render_law_api() -> str:
    lines = ["```python", _signature(law_module.law, "law")]
    for helper in st_module.__all__[:4]:
        fn = getattr(st_module, helper)
        lines.append(_signature(fn, f"st.{helper}"))
    lines.append("```")
    if st_module.__all__[:4] != ["money", "percentages", "non_empty_text", "ids"]:
        raise BuildError("lawkeep.strategies.__all__ no longer starts with the four helpers")
    return "\n".join(lines)


def render_mcp() -> str:
    tools = mcp_server.LawkeepTools
    out = [
        "Start: `lawkeep mcp [--agent NAME]` (stdio; needs `pip install 'lawkeep[mcp]'`). "
        "`lawkeep init` writes the client config (for example `.mcp.json`).",
        "",
        "Server instructions (sent to the client):",
        "",
        "> " + mcp_server.INSTRUCTIONS,
        "",
        "Tools (each of `check`, `propose`, `report` runs `python -m lawkeep <command> --json` and "
        "returns that JSON document unchanged; there is deliberately no `approve` tool):",
        "",
    ]
    for name, description in mcp_server.TOOL_DESCRIPTIONS.items():
        fn = getattr(tools, name)
        sig = _signature(fn, name).replace("self, ", "").replace("(self)", "()")
        # The server registers propose without `actor` (it uses the server's own actor).
        if name == "propose":
            sig = re.sub(r", actor: [^,)]+ = None", "", sig)
        out += [f"- `{sig}`: {description}"]
    return "\n".join(out)


def render_snippet(shift: int) -> str:
    lines: list[str] = []
    for line, outside in _iter_lines_outside_fences(adapters_base.agents_snippet().splitlines()):
        lvl = _heading_level(line) if outside else 0
        if lvl:
            line = "#" * max(1, min(6, lvl + shift)) + line[lvl:]
        lines.append(line)
    return "\n".join(lines).strip("\n")


def _action_blocks() -> dict[str, dict[str, dict[str, str]]]:
    """``inputs`` and ``outputs`` of action.yml, read with a small parser (no YAML dependency)."""
    blocks: dict[str, dict[str, dict[str, str]]] = {"inputs": {}, "outputs": {}}
    current: dict[str, dict[str, str]] | None = None
    key: str | None = None
    for raw in (ROOT / "action.yml").read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" "):
            name = raw.split(":", 1)[0]
            current = blocks.get(name)
            key = None
            continue
        if current is None:
            continue
        m2 = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", raw)
        m4 = re.match(r"^    ([a-z]+):\s*(.*)$", raw)
        if m2:
            new_key: str = m2.group(1)
            current[new_key] = {}
            key = new_key
        elif m4 and key is not None:
            value = m4.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            current[key][m4.group(1)] = value
        else:
            raise BuildError(f"action.yml: unexpected line in inputs/outputs: {raw!r}")
    if not blocks["inputs"] or not blocks["outputs"]:
        raise BuildError("action.yml: inputs or outputs not found")
    return blocks


def render_action() -> str:
    blocks = _action_blocks()
    inputs = [
        [
            f"`{k}`",
            f"`{v.get('default', '')}`" if v.get("default") else "(empty)",
            v.get("description", ""),
        ]
        for k, v in blocks["inputs"].items()
    ]
    outputs = [[f"`{k}`", v.get("description", "")] for k, v in blocks["outputs"].items()]
    return (
        "Inputs:\n\n"
        + md_table(["Input", "Default", "Meaning"], inputs)
        + "\n\nOutputs:\n\n"
        + md_table(["Output", "Meaning"], outputs)
    )


# ---------------------------------------------------------------------------------------------
# docs/onboarding.html -> Markdown


VOID = {"br", "meta", "img", "hr", "input", "link", "wbr", "source", "col"}
SKIP = {"style", "script", "svg", "button", "nav", "head", "title"}
BLOCK = {
    "p", "div", "section", "header", "footer", "main", "ul", "ol", "li", "table", "tr", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6", "details", "summary", "dl", "dt", "dd", "blockquote",
    "body", "html", "thead", "tbody",
}  # fmt: skip


@dataclasses.dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node | str] = dataclasses.field(default_factory=lambda: [])


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {})
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _find(node: Node, tag: str) -> Node | None:
    for child in node.children:
        if isinstance(child, Node):
            if child.tag == tag:
                return child
            found = _find(child, tag)
            if found is not None:
                return found
    return None


def _text(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(c) for c in node.children)


def _inline(node: Node | str) -> str:
    if isinstance(node, str):
        return re.sub(r"\s+", " ", node)
    if node.tag in SKIP:
        return ""
    if node.tag == "br":
        return " "
    if node.tag == "code":
        code = re.sub(r"\s+", " ", _text(node))
        tick = "``" if "`" in code else "`"
        pad = " " if tick == "``" else ""
        return f"{tick}{pad}{code}{pad}{tick}"
    inner = "".join(_inline(c) for c in node.children)
    if node.tag in ("b", "strong"):
        s = inner.strip()
        return f"**{s}**" if s else ""
    if node.tag in ("em", "i"):
        s = inner.strip()
        return f"*{s}*" if s else ""
    if node.tag == "a":
        href = node.attrs.get("href", "")
        if not href or href.startswith("#"):
            return inner
        return f"[{inner.strip()}]({href})"
    return inner


def _has_block(node: Node) -> bool:
    return any(
        isinstance(c, Node) and (c.tag in BLOCK or _has_block(c)) and c.tag not in SKIP
        for c in node.children
    )


def _blocks(node: Node, depth: int = 0) -> list[str]:
    """Render a node's children as Markdown blocks."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = "".join(buf).strip()
        buf.clear()
        if text:
            out.append(re.sub(r" {2,}", " ", text))

    for child in node.children:
        if isinstance(child, str) or (child.tag not in BLOCK and not _has_block(child)):
            buf.append(_inline(child))
            continue
        flush()
        if child.tag in SKIP:
            if child.tag == "svg":
                out.append("*(Diagram: see the HTML version of this page.)*")
            continue
        out.extend(_block(child, depth))
    flush()
    return out


def _block(node: Node, depth: int) -> list[str]:
    tag = node.tag
    cls = node.attrs.get("class", "")
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return ["#" * int(tag[1]) + " " + _inline(node).strip()]
    if tag == "pre":
        code = _text(node).strip("\n")
        return ["```text\n" + code + "\n```"]
    if tag in ("ul", "ol"):
        items: list[str] = []
        n = 0
        for li in node.children:
            if not isinstance(li, Node) or li.tag != "li":
                continue
            n += 1
            marker = f"{n}." if tag == "ol" else "-"
            parts = _blocks(li, depth + 1)
            first = parts[0] if parts else ""
            indent = " " * (len(marker) + 1)
            rest = [
                "\n".join(indent + ln if ln else ln for ln in p.splitlines()) for p in parts[1:]
            ]
            items.append("\n".join([f"{marker} {first}", *rest]))
        return ["\n".join(items)] if items else []
    if tag == "table":
        rows: list[list[str]] = []
        header = False
        for tr in _all(node, "tr"):
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ("th", "td")]
            if not rows:
                header = all(c.tag == "th" for c in cells)
            rows.append([_inline(c).strip() for c in cells])
        if not rows:
            return []
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        if header:
            return [md_table(rows[0], rows[1:])]
        return [md_table([""] * width, rows)]
    if tag == "details":
        summary = _find(node, "summary")
        title = _inline(summary).strip() if summary else "Details"
        rest = Node("div", {}, [c for c in node.children if c is not summary])
        return [f"**Under the hood: {title}**", *_blocks(rest, depth)]
    if tag == "dl":
        out: list[str] = []
        term = ""
        for c in node.children:
            if isinstance(c, Node) and c.tag == "dt":
                term = _inline(c).strip()
            elif isinstance(c, Node) and c.tag == "dd":
                out.append(f"- **{term}**: {' '.join(_blocks(c, depth))}")
        return ["\n".join(out)]
    if tag == "div" and "box" in cls.split():
        label_node = next(
            (
                c
                for c in node.children
                if isinstance(c, Node) and "t" in c.attrs.get("class", "").split()
            ),
            None,
        )
        label = _inline(label_node).strip() if label_node else ""
        rest = Node("div", {}, [c for c in node.children if c is not label_node])
        body = _blocks(rest, depth)
        text = "\n\n".join(([f"**{label}**"] if label else []) + body)
        return ["\n".join("> " + ln if ln else ">" for ln in text.splitlines())]
    if tag == "div" and "step" in cls.split():
        parts = [_inline(c).strip() for c in node.children]
        return [": ".join(p for p in parts if p)]
    return _blocks(node, depth)


def _all(node: Node, tag: str) -> list[Node]:
    found: list[Node] = []
    for c in node.children:
        if isinstance(c, Node):
            if c.tag == tag:
                found.append(c)
            elif c.tag != "table":
                found.extend(_all(c, tag))
    return found


def render_onboarding_markdown() -> str:
    builder = _TreeBuilder()
    builder.feed((ROOT / "docs/onboarding.html").read_text(encoding="utf-8"))
    main = _find(builder.root, "main")
    if main is None:
        raise BuildError("docs/onboarding.html has no <main> element")
    blocks = _blocks(main)
    header = (
        f"<!-- Generated from docs/onboarding.html by {SCRIPT}; do not edit. -->\n\n"
        f"> Markdown version of the lawkeep onboarding guide ({SITE}/). For a compact "
        f"reference written for LLMs and coding agents, read [llms-full.txt]({SITE}/llms-full.txt); "
        f"the index of LLM-ready pages is [llms.txt]({SITE}/llms.txt)."
    )
    return header + "\n\n" + "\n\n".join(blocks).strip() + "\n"


# ---------------------------------------------------------------------------------------------
# Templates


def _directive(spec: str) -> str:
    name, _, arg = spec.partition(":")
    if name == "version":
        return __version__
    if name == "site":
        return SITE
    if name == "repo":
        return REPO
    if name == "section":
        # {{section:FILE|HEADING LINE|SHIFT}} or {{section:FILE|HEADING LINE|SHIFT|own}}
        fields = arg.split("|")
        if len(fields) not in (3, 4) or (len(fields) == 4 and fields[3] != "own"):
            raise BuildError(f"section directive needs FILE|HEADING|SHIFT[|own]: {spec!r}")
        return section_body(fields[0], fields[1], int(fields[2]), own_text_only=len(fields) == 4)
    if name == "commands":
        return render_commands(int(arg or "3"))
    if name == "exit_codes":
        return render_exit_codes()
    if name == "models":
        return render_models()
    if name == "law_api":
        return render_law_api()
    if name == "mcp":
        return render_mcp()
    if name == "snippet":
        return render_snippet(int(arg or "0"))
    if name == "action":
        return render_action()
    if name == "default_toml":
        from lawkeep import config

        return config.render_default_toml(agent_name="claude-code").rstrip("\n")
    raise BuildError(f"unknown template directive {{{{{spec}}}}}")


def render_template(rel_path: str) -> str:
    text = (ROOT / rel_path).read_text(encoding="utf-8")
    rendered = re.sub(r"\{\{([a-z_]+(?::[^}]*)?)\}\}", lambda m: _directive(m.group(1)), text)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.rstrip("\n") + "\n"


def build() -> dict[Path, str]:
    """Every generated file and its expected content."""
    return {
        LLMS_TXT: render_template("scripts/llms.txt.template"),
        LLMS_FULL_TXT: render_template("scripts/llms-full.txt.template"),
        INDEX_MD: render_onboarding_markdown(),
    }


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--check", action="store_true", help="only check that the committed files are up to date"
    )
    args = parser.parse_args(argv)
    try:
        files = build()
    except BuildError as exc:
        print(f"build_llms_docs: {exc}", file=sys.stderr)
        return 2
    stale: list[Path] = []
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path)
        if args.check:
            diff = difflib.unified_diff(
                (current or "").splitlines(),
                content.splitlines(),
                f"{_rel(path)} (committed)",
                f"{_rel(path)} (expected)",
                lineterm="",
                n=1,
            )
            print("\n".join(list(diff)[:40]), file=sys.stderr)
    if args.check:
        if stale:
            names = ", ".join(_rel(p) for p in stale)
            print(
                f"\nOut of date: {names}. These files are generated: {UPDATE_HINT}.",
                file=sys.stderr,
            )
            return 1
        print("LLM docs are up to date: " + ", ".join(_rel(p) for p in files))
        return 0
    # One plain write per file (see the note at LLMS_TXT).
    if LLMS_TXT in stale:
        LLMS_TXT.write_text(files[LLMS_TXT], encoding="utf-8")
    if LLMS_FULL_TXT in stale:
        LLMS_FULL_TXT.write_text(files[LLMS_FULL_TXT], encoding="utf-8")
    if INDEX_MD in stale:
        INDEX_MD.write_text(files[INDEX_MD], encoding="utf-8")
    for path, content in files.items():
        state = "wrote" if path in stale else "unchanged"
        print(f"{state} {_rel(path)} ({len(content):,} characters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
