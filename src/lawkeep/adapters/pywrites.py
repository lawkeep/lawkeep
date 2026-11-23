"""What a piece of Python code would write to, read from its syntax tree (nothing runs).

Used by ``writes.py`` for ``python -c "..."``, Python here-documents and Python scripts that
a shell command runs. It finds calls that create, change or delete files and works out their
path arguments when the code shows them:

- ``open(p, "w"/"a"/"x"/"+...")``, ``io.open``, ``codecs.open``, ``os.open`` with write flags,
  ``Path(p).open("w")``;
- ``Path`` methods ``write_text``, ``write_bytes``, ``unlink``, ``rmdir``, ``touch``,
  ``chmod``, ``rename``, ``replace``, ``symlink_to``, ``hardlink_to``;
- ``os.remove``/``unlink``/``rmdir``/``removedirs``/``truncate``/``chmod``/``chown``/
  ``utime``/``rename``/``replace``/``renames``/``link``/``symlink``;
- ``shutil.copy``/``copy2``/``copyfile``/``copytree``/``copymode``/``copystat`` (destination),
  ``shutil.move`` (both), ``shutil.rmtree``; ``fileinput.input(..., inplace=True)``;
- commands it starts (``subprocess.run``/``call``/``check_call``/``check_output``/``Popen``,
  ``os.system``, ``os.popen``): returned as shell text for ``writes.py`` to analyse;
- ``exec``/``eval``/``compile`` of a fixed string: analysed as Python too;
- lawkeep's own entry points: ``lawkeep.cli.main([...])`` with a fixed list is returned as the
  shell command ``lawkeep ...``; a call to ``record_change`` (lawkeep's history API), a
  ``main(...)`` whose arguments are only known at run time, or a command list such as
  ``["lawkeep", "approve", some_id]`` with run-time values sets ``approval_unknown``. Strings
  that merely *mention* ``lawkeep approve`` (``print("run lawkeep approve")``) never count.

Path values it can follow: string literals, f-strings of literals, ``+`` and ``/`` joins,
``Path(...)``/``os.path.join(...)``/``str(...)``, ``.resolve()``/``.absolute()``/
``.expanduser()``/``.parent``, ``__file__``, ``sys.argv[N]`` (from the command line), and names
assigned one of those anywhere in the code (every assignment counts, so a name may have
several values). Anything else (a path computed in a loop, read from a file, ``glob``
results ...) makes that write *unsure*. A write call whose path is unsure only matters when
the code (or its command line) also names a protected path in a string literal; reads
(``open(p)``, ``read_text()``) never matter.
"""

from __future__ import annotations

import ast
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from lawkeep.adapters.writes import looks_protected

MAX_VALUES = 32

_OPEN_FUNCS = {"open", "io.open", "codecs.open", "builtins.open", "aiofiles.open"}
_PATH_CTORS = {"Path", "PurePath", "PosixPath", "WindowsPath", "pathlib.Path", "pathlib.PurePath",
               "str", "os.fspath", "os.path.join", "os.path.abspath", "os.path.realpath",
               "os.path.normpath", "os.path.expanduser", "os.path.dirname"}  # fmt: skip
_PATH_METHODS_FIRST = {"write_text", "write_bytes", "unlink", "rmdir", "touch", "chmod",
                       "lchmod", "symlink_to", "hardlink_to"}  # fmt: skip
_PATH_METHODS_BOTH = {"rename", "replace"}
_OS_FIRST = {"os.remove", "os.unlink", "os.rmdir", "os.removedirs", "os.truncate", "os.chmod",
             "os.chown", "os.lchown", "os.utime", "os.mkfifo", "os.mknod", "os.lchmod",
             "shutil.rmtree", "shutil.chown"}  # fmt: skip
_OS_BOTH = {"os.rename", "os.replace", "os.renames", "shutil.move"}
_OS_SECOND = {"os.link", "os.symlink", "shutil.copy", "shutil.copy2", "shutil.copyfile",
              "shutil.copytree", "shutil.copymode", "shutil.copystat"}  # fmt: skip
_RUNNERS = {"subprocess.run", "subprocess.call", "subprocess.check_call",
            "subprocess.check_output", "subprocess.Popen", "subprocess.getoutput",
            "subprocess.getstatusoutput", "os.system", "os.popen"}  # fmt: skip
_WRITE_FLAGS = {"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"}


@dataclass
class PyFindings:
    targets: list[str] = field(default_factory=list[str])
    unsure: list[str] = field(default_factory=list[str])
    shell: list[str | None] = field(default_factory=list["str | None"])  # None: built at run time
    mentions: list[str] = field(default_factory=list[str])
    #: runs ``lawkeep approve`` (or records a decision) with arguments only known at run time
    approval_unknown: bool = False


_LAWKEEP_MAINS = {"lawkeep.cli.main", "lawkeep.__main__.main", "lawkeep.main"}


class _Analyser:
    def __init__(self, tree: ast.AST, argv: list[str | None], script: str | None) -> None:
        self.tree = tree
        self.argv = argv
        self.script = script
        self.aliases: dict[str, str] = {}  # local name -> dotted name ("P" -> "pathlib.Path")
        self.names: dict[str, list[str] | None] = {}
        self.pathish: set[str] = set()  # names assigned a Path(...) value
        self.out = PyFindings()

    # -- names -----------------------------------------------------------------------------
    def collect(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = (
                        a.name if a.asname else a.name.split(".")[0]
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        assigns: dict[str, list[ast.expr]] = {}
        unknown: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        assigns.setdefault(t.id, []).append(node.value)
                    else:
                        unknown.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is not None:
                    assigns.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                unknown.add(node.target.id)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                target, it = node.target, node.iter
                if isinstance(target, ast.Name) and isinstance(it, (ast.List, ast.Tuple)):
                    assigns.setdefault(target.id, []).extend(it.elts)
                else:
                    unknown.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        unknown.update(
                            n.id for n in ast.walk(item.optional_vars) if isinstance(n, ast.Name)
                        )
            elif isinstance(node, ast.arg):
                unknown.add(node.arg)
            elif isinstance(node, ast.NamedExpr):
                assigns.setdefault(node.target.id, []).append(node.value)
        for name in unknown:
            self.names[name] = None
        for _ in range(3):  # a few rounds, so names built from other names resolve
            for name, values in assigns.items():
                if name in unknown:
                    continue
                merged: list[str] | None = []
                for v in values:
                    if self._is_path(v):
                        self.pathish.add(name)
                    vals = self.value(v)
                    if vals is None or merged is None:
                        merged = None
                    else:
                        merged.extend(x for x in vals if x not in merged)
                self.names[name] = merged[:MAX_VALUES] if merged is not None else None

    def dotted(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self.dotted(node.value)
            return f"{base}.{node.attr}" if base else ""
        return ""

    def _is_path(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call):
            name = self.dotted(node.func)
            if name.rsplit(".", 1)[-1] in ("Path", "PurePath", "PosixPath", "WindowsPath"):
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "resolve",
                "absolute",
                "expanduser",
                "joinpath",
                "with_name",
                "with_suffix",
            ):
                return self._is_path(node.func.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return True
        if isinstance(node, ast.Name):
            return node.id in self.pathish
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            return True
        return False

    # -- values ----------------------------------------------------------------------------
    def value(self, node: ast.AST) -> list[str] | None:  # noqa: C901 - one evaluator
        """Possible string values of an expression, or None when only known at run time."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return [node.value]
            if isinstance(node.value, bytes):
                return [node.value.decode("utf-8", "replace")]
            return None
        if isinstance(node, ast.JoinedStr):
            out = [""]
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    pieces: list[str] | None = [part.value]
                elif isinstance(part, ast.FormattedValue):
                    pieces = self.value(part.value)
                else:
                    pieces = None
                if pieces is None:
                    return None
                out = [a + b for a in out for b in pieces][:MAX_VALUES]
            return out
        if isinstance(node, ast.Name):
            if node.id == "__file__" and self.script:
                return [self.script]
            return self.names.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            left, right = self.value(node.left), self.value(node.right)
            if left is None or right is None:
                return None
            sep = "/" if isinstance(node.op, ast.Div) else ""
            return [_join(a, b) if sep else a + b for a in left for b in right][:MAX_VALUES]
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            inner = self.value(node.value)
            return None if inner is None else [os.path.dirname(v.rstrip("/")) or "." for v in inner]
        if isinstance(node, ast.Subscript):
            if self.dotted(node.value) == "sys.argv" and isinstance(node.slice, ast.Constant):
                idx = node.slice.value
                if isinstance(idx, int) and 0 <= idx < len(self.argv):
                    v = self.argv[idx]
                    return None if v is None else [v]
            return None
        if isinstance(node, ast.Call):
            name = self.dotted(node.func)
            short = name.rsplit(".", 1)[-1]
            if name in _PATH_CTORS or short in ("Path", "PurePath", "PosixPath"):
                if not node.args:
                    return ["."] if short in ("Path", "PurePath", "PosixPath") else None
                parts = [self.value(a) for a in node.args]
                if any(p is None for p in parts):
                    return None
                out = [""]
                for p in parts:
                    assert p is not None
                    out = [_join(a, b) if a else b for a in out for b in p][:MAX_VALUES]
                if name == "os.path.dirname":
                    return [os.path.dirname(v) for v in out]
                if name == "os.path.expanduser":
                    return [os.path.expanduser(v) for v in out]
                return out
            if name in ("os.getcwd", "pathlib.Path.cwd") or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "cwd"
            ):
                return ["."]
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr in ("resolve", "absolute", "expanduser", "strip", "rstrip"):
                    return self.value(node.func.value)
                if attr == "joinpath":
                    base = self.value(node.func.value)
                    parts = [self.value(a) for a in node.args]
                    if base is None or any(p is None for p in parts):
                        return None
                    out = base
                    for p in parts:
                        assert p is not None
                        out = [_join(a, b) for a in out for b in p][:MAX_VALUES]
                    return out
        return None

    # -- calls -----------------------------------------------------------------------------
    def target(self, node: ast.AST | None, what: str) -> None:
        if node is None:
            return
        vals = self.value(node)
        if vals is None:
            self.out.unsure.append(f"Python code {what} a path only known when it runs")
            return
        self.out.targets.extend(vals)

    def mode_writes(self, mode: ast.AST | None) -> bool | None:
        if mode is None:
            return False
        vals = self.value(mode)
        if vals is None:
            return None
        return any(any(ch in v for ch in "wax+") for v in vals)

    def visit_calls(self) -> None:  # noqa: C901 - one table
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = self.dotted(func)
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            args = node.args
            if name in _OPEN_FUNCS or (name == "open" and isinstance(func, ast.Name)):
                mode = args[1] if len(args) > 1 else kw.get("mode")
                writes = self.mode_writes(mode)
                if writes is None:
                    self.out.unsure.append(
                        "Python code opens a file in a mode only known when it runs"
                    )
                elif writes:
                    self.target(args[0] if args else kw.get("file"), "writes to")
                continue
            if name == "os.open":
                flags = args[1] if len(args) > 1 else kw.get("flags")
                text = ast.unparse(flags) if flags is not None else ""
                if any(f in text for f in _WRITE_FLAGS):
                    self.target(args[0] if args else None, "writes to")
                continue
            if name in _OS_FIRST:
                self.target(args[0] if args else kw.get("path"), "changes")
                continue
            if name in _OS_BOTH:
                for a in args[:2]:
                    self.target(a, "moves")
                continue
            if name in _OS_SECOND:
                dst = args[1] if len(args) > 1 else kw.get("dst")
                self.target(dst, "copies or links to")
                continue
            if name in ("fileinput.input", "fileinput.FileInput"):
                inplace = kw.get("inplace")
                if inplace is not None and not (
                    isinstance(inplace, ast.Constant) and not inplace.value
                ):
                    files = args[0] if args else kw.get("files")
                    if isinstance(files, (ast.List, ast.Tuple)):
                        for e in files.elts:
                            self.target(e, "rewrites")
                    else:
                        self.target(files, "rewrites")
                continue
            if name in _RUNNERS:
                cmd = args[0] if args else kw.get("args")
                self.runner(cmd)
                continue
            if name.rsplit(".", 1)[-1] == "record_change":
                self.out.approval_unknown = True  # lawkeep's history API: a recorded decision
                continue
            if name in _LAWKEEP_MAINS:
                argv = args[0] if args else kw.get("argv")
                if isinstance(argv, (ast.List, ast.Tuple)):
                    vals = [self.value(e) for e in argv.elts]
                    if all(v is not None and len(v) == 1 for v in vals):
                        self.out.shell.append(shlex.join(["lawkeep", *(v[0] for v in vals if v)]))
                        continue
                if argv is not None and self._mentions_approve(argv):
                    self.out.approval_unknown = True
                continue
            if (
                name.startswith("os.exec")
                or name.startswith("os.spawn")
                or name.startswith("os.posix_spawn")
            ):
                rest = args[1:] if name.startswith(("os.exec", "os.posix_spawn")) else args[2:]
                vals = [self.value(a) for a in rest]
                if any(v is None or len(v) != 1 for v in vals):
                    self.out.shell.append(None)
                else:
                    self.out.shell.append(shlex.join(v[0] for v in vals if v))
                continue
            if name in ("exec", "eval", "compile") and isinstance(func, ast.Name):
                src = self.value(args[0]) if args else None
                if src is None:
                    self.out.unsure.append("Python code runs code built at run time (exec/eval)")
                else:
                    for s in src:
                        inner = analyse(s, self.argv, None, self.script)
                        if inner is None:
                            continue
                        self.out.targets.extend(inner.targets)
                        self.out.unsure.extend(inner.unsure)
                        self.out.shell.extend(inner.shell)
                continue
            if isinstance(func, ast.Attribute):
                attr = func.attr
                receiver = func.value
                if attr == "open" and self._is_path(receiver):
                    mode = args[0] if args else kw.get("mode")
                    writes = self.mode_writes(mode)
                    if writes is None:
                        self.out.unsure.append(
                            "Python code opens a file in a mode only known when it runs"
                        )
                    elif writes:
                        self.target(receiver, "writes to")
                elif attr in _PATH_METHODS_FIRST and not self.dotted(receiver).startswith(
                    ("os", "shutil")
                ):
                    self.target(receiver, "changes")
                elif attr in _PATH_METHODS_BOTH and self._is_path(receiver):
                    self.target(receiver, "moves")
                    self.target(args[0] if args else None, "moves")

    def _mentions_approve(self, node: ast.AST) -> bool:
        """An element of a list built in the code is exactly ``"approve"``."""
        return any(isinstance(n, ast.Constant) and n.value == "approve" for n in ast.walk(node))

    def runner(self, cmd: ast.AST | None) -> None:
        if cmd is None:
            return
        if isinstance(cmd, (ast.List, ast.Tuple)):
            vals = [self.value(e) for e in cmd.elts]
            if any(v is None or len(v) != 1 for v in vals):
                words = [v[0] if v and len(v) == 1 else None for v in vals]
                if _runs_lawkeep_approve(words):
                    self.out.approval_unknown = True
                self.out.shell.append(None)
            else:
                self.out.shell.append(shlex.join(v[0] for v in vals if v))
            return
        vals = self.value(cmd)
        if vals is None:
            self.out.shell.append(None)
        else:
            self.out.shell.extend(vals)


def _runs_lawkeep_approve(words: list[str | None]) -> bool:
    """A command list (some words only known at run time) that starts lawkeep and then names
    ``approve``: ``["lawkeep", "approve", x]``, ``[sys.executable, "-m", "lawkeep", ...]``."""
    for i, w in enumerate(words):
        if w is not None and os.path.basename(w) == "lawkeep":
            return "approve" in words[i + 1 :]
    return False


def _join(a: str, b: str) -> str:
    if os.path.isabs(b) or not a:
        return b
    return a.rstrip("/") + "/" + b


def analyse(
    code: str, argv: list[str | None], cwd: Path | None, script: str | None = None
) -> PyFindings | None:
    """Writes of Python ``code`` (None when it does not parse as Python).

    ``argv`` is ``sys.argv`` as far as the command line shows it (None for run-time values);
    ``script`` is the script's path (for ``__file__``). Relative paths stay relative: the
    caller resolves them against the folder the command runs in (``cwd`` is unused here and
    kept for symmetry with the shell analyser).
    """
    del cwd
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    a = _Analyser(tree, argv, script)
    a.collect()
    a.visit_calls()
    a.out.mentions = _string_mentions(tree)
    return a.out


def _string_mentions(tree: ast.AST) -> list[str]:
    """String constants in the code that are, as a whole, a protected-looking path
    (``"laws/refunds.py"``, ``'laws.lock'``). Prose, docstrings and longer text that merely
    contain the word are not paths."""
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if len(text) <= 300 and looks_protected(text) and text not in out:
                out.append(text)
    return out
