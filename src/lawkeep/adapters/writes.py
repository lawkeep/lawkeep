"""What a shell command (or the inline code it runs) would write to, on paper.

Used by the pre-tool-use guard (``guard.py``). Nothing is run: the command is lexed by
``shellwords``, variables and globs are expanded from what the command itself shows (and from
the files that exist), and each simple command is looked up in a table of commands that can
create, change or delete files. The result lists:

- ``targets``: paths the command writes (created, changed, deleted, moved, linked);
- ``recursive``: paths removed or moved as whole folders (``rm -r``, ``mv``), so a folder that
  *contains* the laws counts too;
- ``unsure``: places where a write happens but its target cannot be seen (a path built at run
  time, ``eval`` of computed text, code piped in from another command, a script that cannot be
  read ...), as plain-English reasons;
- ``mentions``: text in the command that looks like a protected path (``laws/...``,
  ``laws.lock``, ``lawkeep.toml``, ``lawkeep.yml``), used to decide whether an unsure write
  plausibly touches the laws;
- ``forced``: decoded code is run (``base64 -d | sh``): hidden on purpose, treated as
  plausible whatever it mentions;
- ``approval``: the command *runs* ``lawkeep approve`` (also through ``uv run``, ``sh -c``,
  ``xargs``, ``python -c "subprocess.run([...])"`` or lawkeep's Python API), and
  ``approve_runs`` says with which arguments, where known. Text that only *mentions*
  ``lawkeep approve`` (a here-document body, an ``echo``/``git commit -m`` message, a string
  in Python code, a file being written) never counts; neither does ``lawkeep approve --help``.

What it sees (writes): output redirections (``>``, ``>>``, ``>|``, ``<>``, ``&>``, ``&>>``,
``>&file``), ``tee``, ``rm``/``unlink``/``rmdir``/``shred``, ``touch``, ``truncate``,
``chmod``/``chown``/``chgrp``/``chattr``/``setfacl``, ``mv``, ``cp``/``install``/``ln``/
``rsync``/``scp`` (destination), ``sed -i``/``perl -i``/``ruby -i``, ``dd of=``, ``patch``
and ``git apply``/``am`` (the files named in the patch), ``git checkout``/``restore``/``rm``/
``mv``/``clean``/``stash push`` paths, ``find -delete``/``-exec``, archive extraction
(``tar``, ``unzip``), compressors, ``curl -o``/``wget -O``, ``sort -o``, editors, and code run
by ``python``/``node``/``ruby``/``perl``/``php``/``deno``/``bun`` (inline ``-c``/``-e``,
here-documents, piped ``echo``/``cat``, or a script file it can read) and by ``sh``/``bash``/
``zsh`` (``-c``, script files, here-documents), ``eval`` of fixed text, ``source``, ``xargs``,
and wrappers (``sudo``, ``env``, ``nohup``, ``time``, ``nice``, ``timeout``, ``uv run`` ...).
It follows ``cd``/``pushd`` between commands, ``VAR=value`` assignments, ``for x in ...``
lists, ``$HOME``/``~``, ``$(pwd)`` and ``$(git rev-parse --show-toplevel)``.

What it cannot see (and does not claim to): commands it does not know (``make``, ``npm run``,
your own scripts in other languages: only their arguments are looked at, never what they do),
values only known at run time (``$(cat list)``, ``read``, most ``$(...)``), whole-tree git
operations (``git checkout <branch>``, ``git checkout .``, ``git stash pop``, ``git reset
--hard``, ``git pull``), files added by archives or patches it cannot read, symlinks created
earlier in the same command, ``find`` filters other than ``-name``/``-path``, and anything
deliberately disguised beyond the forms above. The guard is a speed bump: whatever it misses,
``lawkeep check`` still reports as an unrecorded law change.
"""

from __future__ import annotations

import fnmatch
import glob as globmod
import os
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lawkeep.adapters import shellwords as sw

MAX_DEPTH = 8
MAX_VALUES = 64
MAX_SCRIPT_BYTES = 256 * 1024
PROTECTED_NAMES = ("laws.lock", "lawkeep.toml", "lawkeep.yml")


@dataclass
class ApproveRun:
    """One ``lawkeep approve`` the command runs."""

    #: the words after ``approve`` (``["h-1", "--yes"]``); None when only known at run time
    args: list[str] | None
    #: the folder it runs in, as far as the command shows it
    cwd: str | None = None
    #: ``--root`` given before ``approve`` (``lawkeep --root x approve``)
    root: str | None = None


@dataclass
class Findings:
    targets: list[str] = field(default_factory=list[str])
    recursive: list[str] = field(default_factory=list[str])
    unsure: list[str] = field(default_factory=list[str])
    mentions: list[str] = field(default_factory=list[str])
    forced: bool = False
    approval: bool = False
    approve_runs: list[ApproveRun] = field(default_factory=list["ApproveRun"])
    #: files this command writes with known text (``cat > x.py <<EOF``), by absolute path
    written: dict[str, str] = field(default_factory=dict[str, str])

    def mention(self, text: str) -> None:
        if text not in self.mentions:
            self.mentions.append(text)

    def doubt(self, reason: str) -> None:
        if reason not in self.unsure:
            self.unsure.append(reason)

    def approve(self, run: ApproveRun) -> None:
        self.approval = True
        self.approve_runs.append(run)


@dataclass
class Arg:
    """A word after expansion: its possible values (None: only known at run time)."""

    values: list[str] | None
    text: str  # the literal characters as written (for options and mentions)
    static: bool = True  # written without any expansion

    @staticmethod
    def of(value: str) -> Arg:
        return Arg([value], value)

    @property
    def single(self) -> str | None:
        if self.values is not None and len(self.values) == 1:
            return self.values[0]
        return None

    @property
    def flag(self) -> str | None:
        """The text when this is a literal word starting with ``-`` (an option)."""
        if self.static and self.text.startswith("-") and len(self.text) > 1:
            return self.text
        return None


UNKNOWN = Arg(None, "", static=False)


# ---------------------------------------------------------------------------------------------
# Text helpers


def looks_protected(text: str) -> bool:
    """Does ``text`` look like a path to a protected lawkeep file (``laws/...``, ``laws``,
    ``laws.lock``, ``lawkeep.toml``, ``.github/workflows/lawkeep.yml``)? Words with spaces
    (``"update laws doc"``) are prose, not paths."""
    for piece in (text, text.split("=", 1)[-1]):
        t = piece.strip().strip("'\"")
        if not t or any(ch.isspace() for ch in t):
            continue
        comps = [c for c in t.replace("\\", "/").split("/") if c not in ("", ".")]
        if not comps:
            continue
        if "laws" in comps or comps[-1] in PROTECTED_NAMES:
            return True
        if any(ch in t for ch in "*?[") and any(
            fnmatch.fnmatch(name, comps[-1]) for name in ("laws", *PROTECTED_NAMES)
        ):
            return True  # la*, laws.*, *.lock
    return False


_LITERAL = re.compile(r"""(['"])([^'"\s]{1,300})\1""")


def quoted_mentions(text: str) -> list[str]:
    """Quoted string literals in code that look like protected paths (``"laws/x.py"``,
    ``'laws'``). The word "laws" in prose, comments or docstrings is not a path."""
    return [m.group(2) for m in _LITERAL.finditer(text) if looks_protected(m.group(2))]


_BARE = re.compile(r"[^\s'\"`;|&<>()=]+")


def bare_mentions(text: str) -> list[str]:
    """Path-like tokens in free text (here-document bodies, unparsable commands)."""
    return [t for t in _BARE.findall(text) if looks_protected(t)]


_WRITEY_CODE = re.compile(
    r"open\s*\(|\.write|write_text|write_bytes|writeFile|appendFile|createWriteStream|unlink|"
    r"\bremove|rename|replace|truncate|rmtree|rmSync|rmdir|copy|move|symlink|chmod|"
    r"File\.(write|open|delete)|file_put_contents|fopen|FileUtils|Deno\.write|Bun\.write"
)

#: Code in other languages (or Python that does not parse) that *calls* something with
#: lawkeep approve: ``["lawkeep", "approve"]`` as a command list, ``system("lawkeep approve")``
#: / ``execSync(`lawkeep approve`)`` with the command as the call's first text, or lawkeep's
#: Python API ``record_change(``. Prose that merely mentions ``lawkeep approve`` does not match.
_CODE_APPROVAL = re.compile(
    r"""['"]lawkeep['"]\s*,\s*['"]approve['"]"""
    r"""|\b(?:system|exec\w*|spawn\w*|popen|Popen|run|call|check_call|check_output)\s*\(\s*"""
    r"""['"`](?:[^'"`]*/)?lawkeep\s+(?:--?\w[\w-]*\s+)*approve\b"""
    r"""|\brecord_change\s*\("""
)


def code_approval(code: str) -> bool:
    """Code in another language (or Python that does not parse) that runs ``lawkeep approve``
    or records a decision through lawkeep's Python API. A careful text check: Python that
    parses is read from its syntax tree instead (``pywrites``)."""
    return bool(_CODE_APPROVAL.search(code))


def patch_targets(text: str) -> list[str]:
    """Files named in a unified/git diff (``--- a/x``, ``+++ b/x``, ``diff --git``, renames)
    and in Codex ``*** Update File:`` patches, as written (prefixes not stripped)."""
    out: list[str] = []
    for line in text.splitlines():
        m = (
            re.match(r"(?:\+\+\+|---)\s+(\S+)", line)
            or re.match(r"(?:rename|copy) (?:from|to) (.+?)\s*$", line)
            or re.match(r"\*\*\*\s+(?:Add|Update|Delete) File:\s*(.+?)\s*$", line)
            or re.match(r"\*\*\*\s+Move to:\s*(.+?)\s*$", line)
        )
        if m:
            out.append(m.group(1))
        g = re.match(r"diff --git (\S+) (\S+)", line)
        if g:
            out.extend([g.group(1), g.group(2)])
    return [p for p in out if p != "/dev/null"]


def _strip_components(path: str, n: int) -> str:
    parts = path.split("/")
    return "/".join(parts[n:]) if len(parts) > n else parts[-1]


def _read_text(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_SCRIPT_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _git_toplevel(start: Path) -> Path | None:
    for folder in (start, *start.parents):
        if (folder / ".git").exists():
            return folder
    return None


# ---------------------------------------------------------------------------------------------
# Option parsing


@dataclass
class Parsed:
    operands: list[Arg]
    opts: dict[str, list[Arg]]  # "-x" / "--long" -> values (empty list for a plain flag)

    def has(self, *names: str) -> bool:
        return any(n in self.opts for n in names)

    def value(self, *names: str) -> Arg | None:
        for n in names:
            vals = self.opts.get(n)
            if vals:
                return vals[-1]
        return None


def parse_opts(
    args: list[Arg], short_values: str = "", long_values: tuple[str, ...] = ()
) -> Parsed:
    """Split arguments into operands and options. ``short_values``: one-letter options that
    take a value (``-s 0`` or ``-s0``); ``long_values``: long options that take one
    (``--size 0`` or ``--size=0``). ``--`` ends the options."""
    operands: list[Arg] = []
    opts: dict[str, list[Arg]] = {}
    i = 0
    ended = False
    while i < len(args):
        a = args[i]
        f = None if ended else a.flag
        if f == "--":
            ended = True
        elif f is not None and f.startswith("--"):
            key, eq, val = f.partition("=")
            if eq:
                opts.setdefault(key, []).append(Arg.of(val))
            elif key in long_values and i + 1 < len(args):
                i += 1
                opts.setdefault(key, []).append(args[i])
            else:
                opts.setdefault(key, [])
        elif f is not None:
            for j, ch in enumerate(f[1:], start=1):
                if ch in short_values:
                    rest = f[j + 1 :]
                    if rest:
                        opts.setdefault("-" + ch, []).append(Arg.of(rest))
                    elif i + 1 < len(args):
                        i += 1
                        opts.setdefault("-" + ch, []).append(args[i])
                    break
                opts.setdefault("-" + ch, [])
        else:
            operands.append(a)
        i += 1
    return Parsed(operands, opts)


# ---------------------------------------------------------------------------------------------
# The analyser


_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=")
_KEYWORDS = frozenset(
    {"then", "do", "else", "elif", "if", "while", "until", "!", "{", "}", "done", "fi", "esac"}
)
_DECODERS = frozenset(
    {
        "base64",
        "base32",
        "basenc",
        "xxd",
        "uudecode",
        "openssl",
        "gunzip",
        "zcat",
        "bzcat",
        "xzcat",
        "unxz",
        "rev",
        "zstdcat",
    }  # fmt: skip
)
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "mksh", "ash", "fish"})
_OTHER_INTERPRETERS = frozenset(
    {"node", "nodejs", "deno", "bun", "ruby", "php", "lua", "Rscript", "osascript", "tclsh"}
)
_EDITORS = frozenset(
    {
        "vi",
        "vim",
        "nvim",
        "view",
        "nano",
        "pico",
        "emacs",
        "emacsclient",
        "ed",
        "ex",
        "micro",
        "joe",
        "kak",
        "hx",
        "code",
        "subl",
        "gedit",
        "kate",
        "mcedit",
    }  # fmt: skip
)
_COMPRESSORS = {
    "gzip": ".gz", "gunzip": ".gz", "bzip2": ".bz2", "bunzip2": ".bz2", "xz": ".xz",
    "unxz": ".xz", "zstd": ".zst", "unzstd": ".zst", "lz4": ".lz4", "compress": ".Z",
    "uncompress": ".Z",
}  # fmt: skip


class Shell:
    """Walks a parsed shell script, tracking the current folder and simple variables."""

    def __init__(
        self,
        findings: Findings,
        cwd: Path | None,
        env: dict[str, list[str] | None] | None = None,
        depth: int = 0,
    ) -> None:
        self.f = findings
        self.cwd = cwd
        self.env: dict[str, list[str] | None] = dict(env or {})
        self.depth = depth
        self.dirstack: list[Path | None] = []

    def child(self, cwd: Path | None | str = "same") -> Shell:
        """A subshell / new process: changes of folder and variables do not come back."""
        here = self.cwd if isinstance(cwd, str) else cwd
        return Shell(self.f, here, self.env, self.depth + 1)

    # -- entry points ----------------------------------------------------------------------
    def run_text(self, script: str, what: str = "shell code") -> None:
        if self.depth > MAX_DEPTH:
            self.f.doubt(f"{what} nested too deeply to follow")
            for m in bare_mentions(script):
                self.f.mention(m)
            return
        try:
            commands = sw.parse(script)
        except sw.Incomplete:
            self.f.doubt(f"{what} that lawkeep cannot read (unbalanced quotes or brackets)")
            for m in bare_mentions(script):
                self.f.mention(m)
            return
        self.run(commands)

    def run(self, commands: list[sw.Command]) -> None:
        for cmd in commands:
            self.command(cmd)

    # -- expansion -------------------------------------------------------------------------
    def var(self, name: str) -> list[str] | None:
        if name in self.env:
            return self.env[name]
        if name == "PWD":
            return [str(self.cwd)] if self.cwd else None
        if name in os.environ and name not in ("OLDPWD",):
            return [os.environ[name]]
        return None

    def known_sub(self, script: list[sw.Command]) -> list[str] | None:
        """The output of a few harmless substitutions: ``$(pwd)``, ``$(git rev-parse
        --show-toplevel)``. Anything else is only known at run time."""
        if len(script) != 1 or script[0].redirects:
            return None
        words = [w.static_text() if w.is_static() else None for w in script[0].words]
        if words == ["pwd"] and self.cwd:
            return [str(self.cwd)]
        if words == ["git", "rev-parse", "--show-toplevel"] and self.cwd:
            top = _git_toplevel(self.cwd)
            return [str(top)] if top else None
        return None

    def expand(self, word: sw.Word) -> list[str] | None:
        results = [""]
        globbing = False
        for part in word.parts:
            pieces: list[str] | None
            if part.kind == "lit":
                pieces = [part.text] if part.quoted else _braces(part.text)
                if not part.quoted and any(ch in part.text for ch in "*?["):
                    globbing = True
            elif part.kind == "var":
                pieces = self.var(part.text)
            elif part.kind == "sub" and part.script is not None:
                pieces = self.known_sub(part.script)
            else:
                pieces = None
            if pieces is None:
                return None
            results = [r + p for r in results for p in pieces][:MAX_VALUES]
        first = word.parts[0] if word.parts else None
        if first is not None and first.kind == "lit" and not first.quoted:
            results = [os.path.expanduser(r) if r.startswith("~") else r for r in results]
        if globbing:
            expanded: list[str] = []
            for r in results:
                matches: list[str] = []
                try:
                    if os.path.isabs(r) or self.cwd is not None:
                        matches = sorted(
                            globmod.glob(r, root_dir=None if os.path.isabs(r) else self.cwd)
                        )
                except (OSError, ValueError):
                    matches = []
                expanded.extend(matches[:MAX_VALUES] or [r])  # no match: the word stays as is
            results = expanded[: MAX_VALUES * 4]
        return results

    def arg(self, word: sw.Word) -> Arg:
        return Arg(self.expand(word), word.static_text(), word.is_static())

    # -- recording -------------------------------------------------------------------------
    def resolve(self, value: str) -> str | None:
        if os.path.isabs(value):
            return os.path.normpath(value)
        if self.cwd is None:
            return None
        return os.path.normpath(str(self.cwd / value))

    def read(self, path: str) -> str | None:
        """A file's text: what this command itself wrote there (``cat > x.py <<EOF``), else
        the file on disk (small regular files only)."""
        if path in self.f.written:
            return self.f.written[path]
        return _read_text(Path(path))

    def write(self, arg: Arg, what: str = "a file", *, recursive: bool = False) -> None:
        if arg.values is None:
            self.f.doubt(f"writes to {what} whose name is only known when the command runs")
            return
        for v in arg.values:
            if not v:
                continue
            path = self.resolve(v)
            if path is None:
                if looks_protected(v):
                    self.f.mention(v)
                self.f.doubt(f"writes to {v!r} after changing to a folder only known at run time")
                continue
            self.f.targets.append(path)
            if recursive:
                self.f.recursive.append(path)

    def write_into(self, folder: Arg, names: list[str]) -> None:
        """``cp a b dir/``: the files land inside the folder."""
        if folder.values is None:
            self.write(folder)
            return
        for d in folder.values:
            base = self.resolve(d)
            if base is not None and os.path.isdir(base) and names:
                for n in names:
                    self.f.targets.append(os.path.join(base, os.path.basename(n.rstrip("/"))))
            else:
                self.write(Arg.of(d))

    # -- one simple command ----------------------------------------------------------------
    def command(self, cmd: sw.Command) -> None:
        for w in [*cmd.words, *(r.target for r in cmd.redirects if r.target is not None)]:
            for sub in w.subs():
                self.child().run(sub)  # $(...) runs in a subshell: its writes count too
            text = w.static_text()
            if looks_protected(text):
                self.f.mention(text)
        for r in cmd.redirects:
            if not r.writes() or r.target is None:
                continue
            t = r.target.static_text()
            if r.op == ">&" and r.target.is_static() and (t.isdigit() or t == "-"):
                continue  # 2>&1: a file descriptor, not a file
            self.write(self.arg(r.target), "a file (output redirection)")
        args = [self.arg(w) for w in cmd.words]
        self.remember_written(args, cmd)
        self.dispatch(args, cmd)

    def remember_written(self, args: list[Arg], cmd: sw.Command) -> None:
        """``cat > run.py <<EOF ... EOF`` / ``echo ... > run.sh``: keep what was written, so a
        later ``python run.py`` / ``sh run.sh`` in the same command is read from it."""
        head = os.path.basename(args[0].single or "") if args else ""
        body: str | None = None
        if head == "cat" and len(args) == 1:
            body = next((r.body for r in cmd.redirects if r.op in ("<<", "<<-")), None)
        elif head in ("echo", "printf") and all(a.single is not None for a in args[1:]):
            body = " ".join(a.single or "" for a in args[1:] if a.flag is None) + "\n"
        if body is None:
            return
        for r in cmd.redirects:
            if r.op in (">", ">|", ">>") and r.target is not None:
                vals = self.expand(r.target)
                path = self.resolve(vals[0]) if vals and len(vals) == 1 else None
                if path:
                    prev = self.f.written.get(path, "") if r.op == ">>" else ""
                    self.f.written[path] = prev + body

    def dispatch(self, args: list[Arg], cmd: sw.Command) -> None:  # noqa: C901 - one table
        # keywords and `for NAME in ...`
        while args and args[0].static and args[0].text in _KEYWORDS:
            args = args[1:]
        if not args:
            return
        if args[0].static and args[0].text in ("for", "select"):
            if len(args) >= 2:
                name = args[1].text
                if len(args) >= 3 and args[2].text == "in":
                    values: list[str] | None = []
                    for a in args[3:]:
                        if a.values is None or values is None:
                            values = None
                        else:
                            values.extend(a.values)
                    self.env[name] = values
                else:
                    self.env[name] = None
            return
        # assignments
        i = 0
        while i < len(args) and _ASSIGN.match(args[i].text):  # x=$(mktemp) counts too
            i += 1
        if i == len(args):
            for a in args:
                self.assign(a)
            return
        args = self.strip_wrappers(args[i:])
        if not args:
            return
        head = args[0]
        if head.single is None:
            self.f.doubt("runs a command whose name is only known when it runs")
            return
        name = os.path.basename(head.single)
        rest = args[1:]
        handler = self.HANDLERS.get(name)
        if handler is not None:
            handler(self, name, rest, cmd)
        elif re.match(r"^(python|pypy)[0-9.]*$|^py$", name):
            self.python(name, rest, cmd)
        elif name in _SHELLS:
            self.shell(name, rest, cmd)
        elif name in _OTHER_INTERPRETERS:
            self.other_code(name, rest, cmd)
        elif name in _EDITORS:
            for a in rest:
                if not (a.static and a.text.startswith(("+", "-"))):
                    self.write(a)

    def assign(self, a: Arg) -> None:
        name, _, _ = a.text.partition("=")
        name = name.rstrip("+").split("[", 1)[0]
        if a.values is None:
            self.env[name] = None
            return
        vals = [v.partition("=")[2] for v in a.values]
        self.env[name] = vals

    def strip_wrappers(self, args: list[Arg]) -> list[Arg]:  # noqa: C901 - a list of wrappers
        while args:
            head = args[0].single
            name = os.path.basename(head) if head else ""
            rest = args[1:]
            if name in ("sudo", "doas"):
                args = _after_options(rest, "ugpCUrTtDhR")
            elif name == "env":
                j = 0
                while j < len(rest):
                    a = rest[j]
                    if a.flag in ("-u", "--unset", "-C", "--chdir", "-S", "--split-string"):
                        if a.flag in ("-C", "--chdir") and j + 1 < len(rest):
                            new = rest[j + 1].single
                            self.cwd = Path(self.resolve(new) or "") if new else None
                        if a.flag in ("-S", "--split-string") and j + 1 < len(rest):
                            split = rest[j + 1].single
                            if split is None:
                                return [UNKNOWN]
                            return [Arg.of(w) for w in shlex.split(split)] + rest[j + 2 :]
                        j += 2
                    elif a.flag is not None or (a.static and _ASSIGN.match(a.text)):
                        j += 1
                    else:
                        break
                args = rest[j:]
            elif name in (
                "nohup",
                "command",
                "builtin",
                "exec",
                "chronic",
                "unbuffer",
                "caffeinate",
                "noglob",
            ):
                args = _after_options(rest, "")
            elif name == "time":
                parsed_o = None
                j = 0
                while j < len(rest) and rest[j].flag is not None:
                    if rest[j].flag in ("-o", "--output") and j + 1 < len(rest):
                        parsed_o = rest[j + 1]
                        j += 1
                    elif rest[j].flag in ("-f", "--format"):
                        j += 1
                    j += 1
                if parsed_o is not None:
                    self.write(parsed_o)
                args = rest[j:]
            elif name in ("nice", "ionice", "chrt", "taskset"):
                args = _after_options(rest, "ncp")
                if name in ("chrt", "taskset") and args:
                    args = args[1:]  # the priority / CPU mask
            elif name == "timeout":
                args = _after_options(rest, "sk")
                args = args[1:]  # the duration
            elif name == "stdbuf":
                args = _after_options(rest, "ioe")
            elif name == "flock":
                parsed = parse_opts(rest, "wEc", ("--timeout", "--conflict-exit-code", "--command"))
                code = parsed.value("-c", "--command")
                if code is not None:
                    self.code_string(code, "shell code run by flock")
                    return []
                args = parsed.operands[1:]
            elif name in ("uv", "poetry", "pdm", "hatch", "rye", "pipenv", "pixi"):
                if not rest or rest[0].text not in ("run", "exec"):
                    return args  # uv sync, poetry add ...: not a wrapper
                sub = rest[1:]
                j = 0
                value_opts = {
                    "--with", "--with-editable", "--with-requirements", "--python", "-p",
                    "--project", "--directory", "--package", "--extra", "--group", "--env-file",
                    "--index", "--index-url", "--extra-index-url", "--find-links", "-f",
                    "--config-file", "--cache-dir", "--only-group", "--no-group", "-e", "--env",
                }  # fmt: skip
                while j < len(sub) and sub[j].flag is not None:
                    flag = sub[j].flag or ""
                    if flag == "--":
                        j += 1
                        break
                    if flag in value_opts and "=" not in flag:
                        if flag == "--directory" and j + 1 < len(sub):
                            d = sub[j + 1].single
                            self.cwd = Path(self.resolve(d) or "") if d else None
                        j += 2
                    else:
                        j += 1
                args = sub[j:]
            elif name in ("uvx", "pipx", "npx", "bunx", "pnpx"):
                sub = rest[1:] if name == "pipx" and rest and rest[0].text == "run" else rest
                args = _after_options(sub, "")
            else:
                return args
        return args

    # -- handlers --------------------------------------------------------------------------
    def h_cd(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        if name == "popd":
            self.cwd = self.dirstack.pop() if self.dirstack else None
            return
        ops = [a for a in args if a.flag is None or a.text == "-"]
        if name == "pushd":
            self.dirstack.append(self.cwd)
        if not ops:
            home = os.environ.get("HOME")
            self.cwd = Path(home) if home and name == "cd" else self.cwd
            return
        target = ops[-1].single
        if target is None or target == "-":
            self.cwd = None
            return
        new = self.resolve(target)
        self.cwd = Path(new) if new else None

    def h_read(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        for a in parse_opts(args, "adpnNtu").operands:
            self.env[a.text] = None

    def h_declare(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        for a in args:
            if a.static and _ASSIGN.match(a.text):
                self.assign(a)
            elif a.flag is None and a.static:
                self.env.setdefault(a.text, None)

    def h_unset(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        for a in args:
            if a.flag is None:
                self.env[a.text] = None

    def h_operands(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        values = {"shred": "nsu", "touch": "rdtA", "truncate": "sr", "tee": "", "mkfifo": "m"}
        parsed = parse_opts(args, values.get(name, ""), ("--size", "--reference", "--date"))
        recursive = name == "rm" and parsed.has("-r", "-R", "--recursive")
        for a in parsed.operands:
            self.write(a, recursive=recursive)

    def h_perms(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "mMxX" if name == "setfacl" else "", ("--reference", "--from"))
        ops = parsed.operands
        if name == "chmod":
            # chmod -w f: the mode was read as an option; chmod 644 f / u+x f: first operand
            if (
                ops
                and not parsed.has("--reference")
                and re.match(r"^[0-7]+$|^[ugoa]*[-+=]", ops[0].text)
            ):
                ops = ops[1:]
            elif not parsed.has("--reference") and not any(
                k for k in parsed.opts if re.match(r"^-[rwxXst]$", k)
            ):
                ops = ops[1:]
        elif name in ("chown", "chgrp") and not parsed.has("--reference"):
            ops = ops[1:]
        elif name == "chattr":
            ops = [a for a in ops if not a.text.startswith(("+", "="))]
        for a in ops:
            self.write(a, recursive=False)

    def h_mv(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "tS", ("--target-directory", "--suffix"))
        for a in parsed.operands:
            self.write(a, recursive=True)  # the source disappears, the destination changes
        target = parsed.value("-t", "--target-directory")
        if target is not None:
            self.write(target)

    def h_copy(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        values = {
            "cp": "tS",
            "ln": "tS",
            "link": "",
            "install": "mogSt",
            "rsync": "efTB",
            "scp": "PiocFlSJ",
        }
        parsed = parse_opts(
            args,
            values.get(name, ""),
            (
                "--target-directory",
                "--suffix",
                "--mode",
                "--owner",
                "--group",
                "--rsh",
                "--filter",
                "--exclude",
                "--include",
                "--temp-dir",
                "--files-from",
                "--chmod",
            ),  # fmt: skip
        )
        ops = parsed.operands
        if name == "install" and parsed.has("-d", "--directory"):
            for a in ops:
                self.write(a)
            return
        if name == "scp" or name == "rsync":
            ops = [a for a in ops if not (a.single and re.match(r"^[^/]*:", a.single))]
        target = parsed.value("-t", "--target-directory")
        sources = ops if target is not None else ops[:-1]
        if target is None:
            if len(ops) < 2 and name not in ("ln",):
                return
            if not ops:
                return
            target = ops[-1]
        names = [v for a in sources for v in (a.values or [])]
        if parsed.has("-T", "--no-target-directory"):
            self.write(target)
        else:
            self.write_into(target, names)
        if name == "rsync" and parsed.has("--remove-source-files"):
            for a in sources:
                self.write(a)

    def h_sed(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        inplace = False
        has_script = False
        operands: list[Arg] = []
        i = 0
        while i < len(args):
            a = args[i]
            f = a.flag
            if f == "--":
                operands.extend(args[i + 1 :])
                break
            if f is not None and f.startswith("--"):
                key = f.partition("=")[0]
                if key == "--in-place":
                    inplace = True
                elif key in ("--expression", "--file"):
                    has_script = True
                    if "=" not in f:
                        i += 1
                elif key == "--line-length" and "=" not in f:
                    i += 1
            elif f is not None:
                body = f[1:]
                for j, ch in enumerate(body):
                    if ch == "i":
                        inplace = True
                        if (
                            j == len(body) - 1
                            and i + 1 < len(args)
                            and args[i + 1].static
                            and args[i + 1].text == ""
                        ):
                            i += 1  # BSD sed -i '' (empty backup suffix)
                        break  # the rest of the bundle is the backup suffix
                    if ch in "ef":
                        has_script = True
                        if j == len(body) - 1:
                            i += 1
                        break
                    if ch == "l":
                        if j == len(body) - 1:
                            i += 1
                        break
            else:
                operands.append(a)
            i += 1
        if not has_script and operands:
            operands = operands[1:]
        if inplace:
            for a in operands:
                self.write(a)

    def h_perl_ruby(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        inplace = False
        codes: list[Arg] = []
        operands: list[Arg] = []
        i = 0
        while i < len(args):
            a = args[i]
            f = a.flag
            if f == "--":
                operands.extend(args[i + 1 :])
                break
            if f is not None and not f.startswith("--"):
                body = f[1:]
                for j, ch in enumerate(body):
                    if ch == "i":
                        inplace = True
                        break  # rest: backup extension
                    if ch in "eE":
                        rest = body[j + 1 :]
                        if rest:
                            codes.append(Arg.of(rest))
                        elif i + 1 < len(args):
                            i += 1
                            codes.append(args[i])
                        break
                    if ch in "MmIxCdlr0":
                        if ch in "MIr" and j == len(body) - 1:
                            i += 1
                        break
            elif f is None:
                operands.append(a)
            i += 1
        for code in codes:
            self.code_arg(code, name, operands)
        if not codes and operands:
            script, operands = operands[0], operands[1:]
            self.script_file(script, name, operands)
        if inplace:
            for a in operands:
                self.write(a)

    def h_dd(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        for a in args:
            if a.text.startswith("of="):
                vals = None if a.values is None else [v[3:] for v in a.values]
                self.write(Arg(vals, a.text[3:]))

    def h_git(self, name: str, args: list[Arg], cmd: sw.Command) -> None:  # noqa: C901
        saved = self.cwd
        i = 0
        while i < len(args) and args[i].flag is not None:
            f = args[i].flag or ""
            if f == "-C" and i + 1 < len(args):
                d = args[i + 1].single
                self.cwd = Path(self.resolve(d) or "") if d else None
                i += 2
            elif f in (
                "-c",
                "--git-dir",
                "--work-tree",
                "--namespace",
                "--exec-path",
            ) and i + 1 < len(args):
                if f == "--work-tree":
                    d = args[i + 1].single
                    self.cwd = Path(self.resolve(d) or "") if d else None
                i += 2
            else:
                if f.startswith("--work-tree="):
                    d = f.partition("=")[2]
                    self.cwd = Path(self.resolve(d) or "")
                i += 1
        try:
            if i >= len(args):
                return
            sub = args[i].text
            rest = args[i + 1 :]
            if sub in ("rm", "mv"):
                parsed = parse_opts(rest)
                for a in parsed.operands:
                    self.write(a, recursive=sub == "mv" or parsed.has("-r"))
            elif sub == "checkout":
                if any(a.static and a.text == "--" for a in rest):
                    idx = next(k for k, a in enumerate(rest) if a.static and a.text == "--")
                    paths = rest[idx + 1 :]
                else:
                    parsed = parse_opts(rest, "bB", ("--orphan", "--conflict"))
                    if parsed.has("-b", "-B", "--orphan"):
                        return
                    paths = parsed.operands  # a branch name is judged as a path too: harmless
                for a in paths:
                    self.write(a)
            elif sub == "restore":
                parsed = parse_opts(rest, "s", ("--source",))
                if parsed.has("-S", "--staged") and not parsed.has("-W", "--worktree"):
                    return  # only the index changes
                for a in parsed.operands:
                    self.write(a)
            elif sub == "clean":
                parsed = parse_opts(rest, "e", ("--exclude",))
                if parsed.has("-n", "--dry-run"):
                    return
                for a in parsed.operands:
                    self.write(a, recursive=True)
            elif sub == "stash":
                if rest and rest[0].text in ("push", "save") or (rest and rest[0].flag):
                    parsed = parse_opts(
                        rest[1:] if rest[0].text in ("push", "save") else rest, "m", ("--message",)
                    )
                    for a in parsed.operands:
                        self.write(a)
            elif sub in ("apply", "am"):
                parsed = parse_opts(
                    rest, "pC", ("--directory", "--exclude", "--include", "--whitespace")
                )
                if sub == "apply" and (
                    parsed.has("--check", "--stat", "--numstat", "--summary", "--cached")
                    and not parsed.has("--apply", "--index")
                ):
                    return
                strip = _int_or(parsed.value("-p"), 1)
                prefix = (parsed.value("--directory") or Arg.of("")).single or ""
                self.from_patch(parsed.operands, cmd, [strip], prefix)
        finally:
            self.cwd = saved

    def h_patch(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(
            args,
            "pidoDrBVzFgY",
            (
                "--strip",
                "--input",
                "--directory",
                "--output",
                "--reject-file",
                "--prefix",
                "--suffix",
                "--fuzz",
                "--backup-if-mismatch",
                "--quoting-style",
            ),  # fmt: skip
        )
        if parsed.has("--dry-run"):
            return
        out = parsed.value("-o", "--output")
        if out is not None:
            self.write(out)
            return
        saved = self.cwd
        d = parsed.value("-d", "--directory")
        if d is not None:
            dv = d.single
            self.cwd = Path(self.resolve(dv) or "") if dv else None
        try:
            ops = parsed.operands
            if ops:
                self.write(ops[0])  # patch FILE [PATCHFILE]: FILE changes
                return
            p = parsed.value("-p", "--strip")
            strips = [_int_or(p, 0)] if p is not None else [0, 1, 99]
            source = parsed.value("-i", "--input")
            self.from_patch([source] if source is not None else [], cmd, strips, "")
        finally:
            self.cwd = saved

    def from_patch(self, files: list[Arg], cmd: sw.Command, strips: list[int], prefix: str) -> None:
        texts: list[str] = []
        for a in files:
            if a.values is None:
                self.f.doubt("applies a patch file whose name is only known at run time")
                continue
            for v in a.values:
                path = self.resolve(v)
                text = self.read(path) if path and v != "-" else None
                if text is None and v != "-":
                    self.f.doubt(f"applies a patch lawkeep cannot read ({v})")
                elif text is not None:
                    texts.append(text)
        if not files or any(a.single == "-" for a in files):
            text, decoded, fed = self.stdin_text(cmd)
            if text is not None:
                texts.append(text)
            elif fed:
                self.f.forced = self.f.forced or decoded
                self.f.doubt("applies a patch piped in from another command")
        for text in texts:
            for raw in patch_targets(text):
                for n in strips:
                    path = _strip_components(raw, n) if n < 99 else os.path.basename(raw)
                    self.write(Arg.of(os.path.join(prefix, path) if prefix else path))

    def h_find(self, name: str, args: list[Arg], cmd: sw.Command) -> None:  # noqa: C901
        starts: list[Arg] = []
        i = 0
        while i < len(args) and args[i].flag is None and args[i].text not in ("(", "!"):
            starts.append(args[i])
            i += 1
        while i < len(args) and args[i].flag in ("-H", "-L", "-P"):
            i += 1
        expr = args[i:]
        if not starts:
            starts = [Arg.of(".")]
        names: list[str] = []
        excluded = False
        writes = False
        k = 0
        negate = False
        while k < len(expr):
            t = expr[k].text
            if t in ("-name", "-iname", "-regex", "-iregex") and k + 1 < len(expr):
                if not negate:
                    names.append(expr[k + 1].text)
                k += 2
                negate = False
                continue
            if t in ("-path", "-ipath", "-wholename") and k + 1 < len(expr):
                pat = expr[k + 1].text
                if negate and "laws" in pat:
                    excluded = True
                k += 2
                negate = False
                continue
            if t == "-prune" and k >= 2 and "laws" in expr[k - 1].text:
                excluded = True
            negate = t in ("!", "-not")
            if t in ("-fprint", "-fprint0", "-fprintf", "-fls") and k + 1 < len(expr):
                self.write(expr[k + 1])
                k += 2
                continue
            if t == "-delete":
                writes = True
                for s in starts:
                    self.write(s, recursive=False)
            elif t in ("-exec", "-execdir", "-ok", "-okdir"):
                j = k + 1
                sub: list[Arg] = []
                while j < len(expr) and expr[j].text not in (";", "+"):
                    a = expr[j]
                    if a.static and "{}" in a.text:
                        vals = (
                            [a.text.replace("{}", v) for s in starts for v in (s.values or [])]
                            if all(s.values is not None for s in starts)
                            else None
                        )
                        sub.append(Arg(vals, a.text))
                    else:
                        sub.append(a)
                    j += 1
                before = len(self.f.targets) + len(self.f.unsure)
                self.child().dispatch(sub, sw.Command())
                if len(self.f.targets) + len(self.f.unsure) > before:
                    writes = True
                k = j + 1
                continue
            k += 1
        if writes and not excluded:
            self.find_over_laws(starts, names)

    def find_over_laws(self, starts: list[Arg], names: list[str]) -> None:
        """``find . -exec sed -i ...``: a write over a folder that contains ``laws/`` reaches
        the law files unless a ``-name`` filter rules all of them out."""
        for s in starts:
            for v in s.values or []:
                base = self.resolve(v)
                if base is None:
                    continue
                laws = _laws_below(Path(base))
                if laws is None:
                    continue
                files = [
                    p for p in laws.rglob("*")
                    if p.is_file() and "drafts" not in p.relative_to(laws).parts[:1]
                    and not any(part in ("__pycache__", ".hypothesis", ".pytest_cache") for part in p.parts)
                ]  # fmt: skip
                if not names or any(fnmatch.fnmatch(p.name, pat) for p in files for pat in names):
                    self.f.forced = True
                    self.f.mention(str(laws))
                    self.f.doubt("changes files found by `find` in a folder that contains laws/")
                    return

    def h_tar(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        modes: set[str] = set()
        archive: Arg | None = None
        dest: Arg | None = None
        members: list[Arg] = []
        rest = list(args)
        if (
            rest
            and rest[0].static
            and rest[0].flag is None
            and re.match(r"^[A-Za-z]+$", rest[0].text)
        ):
            letters = rest.pop(0).text  # old style: tar czf out.tgz ...
            for ch in letters:
                if ch in "cxtrudA":
                    modes.add(ch)
                if ch == "f" and rest:
                    archive = rest.pop(0)
                if ch == "C" and rest:
                    dest = rest.pop(0)
        parsed = parse_opts(
            rest,
            "fCbTXIHKgLVN",
            ("--file", "--directory", "--exclude", "--files-from", "--use-compress-program"),
        )
        for ch in "cxtrudA":
            if parsed.has("-" + ch):
                modes.add(ch)
        long_modes = {"--create": "c", "--extract": "x", "--get": "x", "--list": "t", "--append": "r",
                      "--update": "u", "--delete": "u", "--catenate": "A", "--concatenate": "A"}  # fmt: skip
        for k, v in long_modes.items():
            if parsed.has(k):
                modes.add(v)
        archive = parsed.value("-f", "--file") or archive
        dest = parsed.value("-C", "--directory") or dest
        members = parsed.operands
        if modes & set("cruA") and archive is not None:
            self.write(archive)
        if "x" in modes:
            self.extract_into(dest, members, "tar")

    def h_unzip(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "dxP", ())
        if parsed.has("-l", "-t", "-v", "-p", "-Z", "-z"):
            return
        ops = parsed.operands
        self.extract_into(parsed.value("-d"), ops[1:], "unzip")

    def extract_into(self, dest: Arg | None, members: list[Arg], tool: str) -> None:
        folder = dest if dest is not None else Arg.of(".")
        if folder.values is None:
            self.f.doubt(f"{tool} extracts into a folder only known at run time")
            return
        for d in folder.values:
            base = self.resolve(d)
            if base is None:
                self.f.doubt(f"{tool} extracts after changing to a folder only known at run time")
                continue
            if members:
                for m in members:
                    for v in m.values or []:
                        self.f.targets.append(os.path.normpath(os.path.join(base, v)))
                continue
            self.f.targets.append(base)  # inside laws/: that alone is enough
            if _laws_below(Path(base)) is not None:
                self.f.doubt(f"{tool} extracts an archive into a folder that contains laws/; "
                             "lawkeep cannot see which files it holds")  # fmt: skip

    def h_compress(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "S", ("--suffix",))
        if parsed.has("-c", "--stdout", "--to-stdout", "-l", "--list", "-t", "--test"):
            return
        suffix = _COMPRESSORS.get(name, "")
        for a in parsed.operands:
            self.write(a)
            if a.values is not None and suffix:
                derived = [
                    v[: -len(suffix)] if v.endswith(suffix) else v + suffix for v in a.values
                ]
                self.write(Arg(derived, a.text))

    def h_zip(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "bntxi", ())
        if parsed.operands:
            self.write(parsed.operands[0])

    def h_download(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        if name == "curl":
            parsed = parse_opts(
                args,
                "oduHXAeEKTwxyrmUbcCzQt",
                (
                    "--output",
                    "--output-dir",
                    "--data",
                    "--header",
                    "--request",
                    "--user-agent",
                    "--referer",
                    "--cert",
                    "--config",
                    "--upload-file",
                    "--write-out",
                    "--proxy",
                    "--range",
                    "--max-time",
                    "--user",
                    "--cookie",
                    "--cookie-jar",
                    "--form",
                ),  # fmt: skip
            )
            for o in parsed.opts.get("-o", []) + parsed.opts.get("--output", []):
                self.write(o)
            jar = parsed.value("-c", "--cookie-jar")
            if jar is not None:
                self.write(jar)
            if parsed.has("-O", "--remote-name", "--remote-name-all"):
                self.write(parsed.value("--output-dir") or Arg.of("."))
        else:
            parsed = parse_opts(
                args, "OPoaeiUtTwlQAR", ("--output-document", "--directory-prefix", "--output-file")
            )
            out = parsed.value("-O", "--output-document")
            if out is not None and out.single != "-":
                self.write(out)
            else:
                self.write(parsed.value("-P", "--directory-prefix") or Arg.of("."))

    def h_sort(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(
            args, "otkSTt", ("--output", "--key", "--buffer-size", "--temporary-directory")
        )
        out = parsed.value("-o", "--output")
        if out is not None:
            self.write(out)

    def h_awk(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        parsed = parse_opts(args, "fvFiE", ("--file", "--assign", "--field-separator", "--include"))
        inplace = any(
            v.single == "inplace"
            for v in parsed.opts.get("-i", []) + parsed.opts.get("--include", [])
        )
        ops = parsed.operands
        if not parsed.has("-f", "--file", "-E") and ops:
            ops = ops[1:]  # the program
        if inplace:
            for a in ops:
                if not (a.single and "=" in a.single):  # var=value operands are not files
                    self.write(a)

    def h_lawkeep(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        # lawkeep itself is the right way to change laws; only `approve` needs the person
        root: str | None = None
        i = 0
        while i < len(args):
            a = args[i]
            f = a.flag
            if f in ("--help", "-h", "--version"):
                return  # prints text, changes nothing
            if f == "--root":
                root = args[i + 1].single if i + 1 < len(args) else None
                i += 2  # its value is a folder, not the subcommand
                continue
            if f is not None and f.startswith("--root="):
                root = f.partition("=")[2]
            elif f is None:
                break
            i += 1
        if i >= len(args) or args[i].text != "approve":
            return
        tail = args[i + 1 :]
        if any(a.flag in ("--help", "-h") for a in tail):
            return  # `lawkeep approve --help` only prints the help text
        words = [a.single for a in tail]
        known = None if any(w is None for w in words) else [w for w in words if w is not None]
        self.f.approve(ApproveRun(known, str(self.cwd) if self.cwd else None, root))

    def h_eval(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        if any(a.values is None or len(a.values) != 1 for a in args):
            self.f.doubt("runs text built at run time with `eval`")
            for a in args:
                if looks_protected(a.text):
                    self.f.mention(a.text)
            return
        self.run_text(" ".join(a.values[0] for a in args if a.values), "`eval` text")

    def h_source(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        if not args:
            return
        script = args[0]
        if script.single is None:
            self.f.doubt("runs a script whose name is only known at run time")
            return
        path = self.resolve(script.single)
        text = self.read(path) if path else None
        if text is not None:
            self.depth += 1
            try:
                self.run_text(text, f"the script {script.single}")
            finally:
                self.depth -= 1

    def h_xargs(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        j = 0
        replace: str | None = None
        with_value = {"-I", "-i", "-n", "-P", "-d", "-E", "-e", "-L", "-l", "-s", "-a"}
        while j < len(args) and args[j].flag is not None:
            f = args[j].flag or ""
            if f in with_value and j + 1 < len(args):
                if f == "-I":
                    replace = args[j + 1].text
                j += 2
                continue
            if f.startswith("-I") and len(f) > 2:
                replace = f[2:]
            elif f == "-i" or f.startswith("--replace"):
                replace = f.partition("=")[2] or "{}"
            j += 1
        sub = args[j:]
        if not sub:
            return
        if replace:
            new = [UNKNOWN if a.static and replace in a.text else a for a in sub]
        else:
            new = [*sub, UNKNOWN]  # the arguments come from the input
        self.child().dispatch(new, sw.Command())

    def h_watch(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        ops = _after_options(args, "nd")
        if ops:
            vals = [a.single for a in ops]
            if any(v is None for v in vals):
                self.f.doubt("`watch` runs text built at run time")
                return
            self.run_text(" ".join(v for v in vals if v is not None), "`watch` command")

    HANDLERS: dict[str, Callable[[Shell, str, list[Arg], sw.Command], None]] = {}

    # -- code ------------------------------------------------------------------------------
    def stdin_text(self, cmd: sw.Command) -> tuple[str | None, bool, bool]:
        """(text fed to the command's standard input, it came from a decoder, there is input).
        Here-documents, here-strings, ``< file`` and ``echo``/``printf``/``cat`` pipes."""
        for r in reversed(cmd.redirects):
            if r.op in ("<<", "<<-"):
                return r.body or "", False, True
            if r.op == "<<<" and r.target is not None:
                vals = self.expand(r.target)
                return (" ".join(vals) if vals is not None else None), False, True
            if r.op == "<" and r.target is not None:
                vals = self.expand(r.target)
                path = self.resolve(vals[0]) if vals and len(vals) == 1 else None
                return (self.read(path) if path else None), False, True
        prev = cmd.piped_from
        if prev is None:
            return None, False, False
        words = [self.arg(w) for w in prev.words]
        words = self.strip_wrappers(words)
        head = os.path.basename(words[0].single or "") if words else ""
        decoded = head in _DECODERS or (
            head in ("gzip", "bzip2", "xz", "zstd") and any(a.flag and "d" in a.flag for a in words)
        )
        if head in ("echo", "printf") and all(a.values is not None for a in words[1:]):
            body = [
                v for a in words[1:] if a.flag is None or head == "printf" for v in (a.values or [])
            ]
            return " ".join(body), False, True
        if head == "cat" and not words[1:]:
            return self.stdin_text(prev)  # cat <<EOF | sh: the here-document is the input
        if head == "cat" and words[1:] and all(a.single is not None for a in words[1:]):
            texts: list[str] = []
            for a in words[1:]:
                path = self.resolve(a.single or "")
                text = self.read(path) if path else None
                if text is None:
                    return None, False, True
                texts.append(text)
            return "".join(texts), False, True
        return None, decoded, True

    def code_string(self, code: Arg, what: str) -> None:
        if code.single is None:
            self.f.doubt(f"runs {what} built at run time")
            return
        self.child().run_text(code.single, what)

    def python(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        i = 0
        while i < len(args):
            a = args[i]
            f = a.flag
            if f is None:
                if a.static and a.text == "-":
                    self.python_stdin(cmd, args[i + 1 :])
                    return
                self.script_file(a, "python", args[i + 1 :])
                return
            if f == "-c" or (f.startswith("-c") and not f.startswith("--")):
                code = (
                    Arg.of(f[2:])
                    if len(f) > 2
                    else (args[i + 1] if i + 1 < len(args) else Arg.of(""))
                )
                self.code_arg(code, "python", args[i + 2 :] if len(f) == 2 else args[i + 1 :])
                return
            if f == "-m" or (f.startswith("-m") and not f.startswith("--")):
                module = f[2:] if len(f) > 2 else (args[i + 1].text if i + 1 < len(args) else "")
                if module == "lawkeep":
                    self.h_lawkeep("lawkeep", args[i + 2 :] if len(f) == 2 else args[i + 1 :], cmd)
                return
            if f in ("-W", "-X", "--check-hash-based-pycs"):
                i += 2
                continue
            i += 1
        self.python_stdin(cmd, [])

    def python_stdin(self, cmd: sw.Command, script_args: list[Arg]) -> None:
        text, decoded, fed = self.stdin_text(cmd)
        if text is not None:
            self.code_text(text, "python", script_args)
        elif fed:
            self.f.forced = self.f.forced or decoded
            self.f.doubt("runs Python code piped in from another command")

    def shell(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        i = 0
        code_next = False
        while i < len(args):
            a = args[i]
            f = a.flag
            if f is not None and not f.startswith("--") and "c" in f[1:]:
                code_next = True
            elif f in ("-o", "+o", "-O", "+O"):
                i += 1
            elif f is None or f == "-":
                if code_next:
                    self.code_string(a, f"{name} -c code")
                    return
                if f == "-":
                    break
                self.script_file(a, name, args[i + 1 :])
                return
            i += 1
        text, decoded, fed = self.stdin_text(cmd)
        if text is not None:
            self.child().run_text(text, f"{name} code from standard input")
        elif fed:
            self.f.forced = self.f.forced or decoded
            self.f.doubt(f"runs {name} code piped in from another command")

    def other_code(self, name: str, args: list[Arg], cmd: sw.Command) -> None:
        code_flags = {"-e", "--eval", "-p", "--print", "-r", "-E"}
        i = 0
        while i < len(args):
            a = args[i]
            if a.flag in code_flags and i + 1 < len(args):
                self.code_arg(args[i + 1], name, args[i + 2 :])
                return
            if a.flag is None:
                if name == "deno" and a.text in ("eval",) and i + 1 < len(args):
                    self.code_arg(args[i + 1], name, args[i + 2 :])
                    return
                if name in ("deno", "bun") and a.text in ("run", "x", "test", "task"):
                    i += 1
                    continue
                self.script_file(a, name, args[i + 1 :])
                return
            i += 1
        text, decoded, fed = self.stdin_text(cmd)
        if text is not None:
            self.code_text(text, name, [])
        elif fed:
            self.f.forced = self.f.forced or decoded
            self.f.doubt(f"runs {name} code piped in from another command")

    def code_arg(self, code: Arg, lang: str, script_args: list[Arg]) -> None:
        if code.single is None:
            self.f.doubt(f"runs {lang} code built at run time")
            for m in quoted_mentions(code.text) + (
                [code.text] if looks_protected(code.text) else []
            ):
                self.f.mention(m)
            return
        self.code_text(code.single, lang, script_args, inline=True)

    def script_file(self, script: Arg, lang: str, script_args: list[Arg]) -> None:
        if script.single is None:
            self.f.doubt(f"runs a {lang} script whose name is only known at run time")
            return
        path = self.resolve(script.single)
        text = self.read(path) if path else None
        if text is None:
            # cannot read it: it may write its arguments
            if any(looks_protected(a.text) for a in script_args):
                self.f.doubt(
                    f"runs {script.single}, which lawkeep cannot read, on a protected path"
                )
            return
        if lang in _SHELLS:
            self.depth += 1
            try:
                self.child().run_text(text, f"the script {script.single}")
            finally:
                self.depth -= 1
            return
        self.code_text(text, lang, script_args, script=script.single)

    def code_text(
        self,
        code: str,
        lang: str,
        script_args: list[Arg],
        *,
        inline: bool = False,
        script: str | None = None,
    ) -> None:
        argv: list[str | None] = [script or "-c"] + [a.single for a in script_args]
        for a in script_args:
            if looks_protected(a.text):
                self.f.mention(a.text)
        if lang.startswith(("python", "pypy")) or lang == "py":
            from lawkeep.adapters import pywrites

            found = pywrites.analyse(code, argv, self.cwd, script)
            if found is not None:
                if found.approval_unknown:
                    self.f.approve(ApproveRun(None, str(self.cwd) if self.cwd else None))
                for m in found.mentions:
                    self.f.mention(m)
                for t in found.targets:
                    self.write(Arg.of(t))
                for reason in found.unsure:
                    self.f.doubt(reason)
                for shell_cmd in found.shell:
                    if shell_cmd is None:
                        self.f.doubt("starts a command built at run time from Python")
                    else:
                        self.child().run_text(shell_cmd, "a command started from Python")
                return
        # other languages (or Python that does not parse): a careful text check for a call that
        # runs `lawkeep approve`, and a quoted protected path in code that writes files counts
        # as a write to it
        if code_approval(code):
            self.f.approve(ApproveRun(None, str(self.cwd) if self.cwd else None))
        mentions = quoted_mentions(code)
        for m in mentions:
            self.f.mention(m)
        if mentions and _WRITEY_CODE.search(code):
            for m in mentions:
                self.write(Arg.of(m))


Shell.HANDLERS = {
    "cd": Shell.h_cd, "pushd": Shell.h_cd, "popd": Shell.h_cd,
    "read": Shell.h_read, "export": Shell.h_declare, "declare": Shell.h_declare,
    "local": Shell.h_declare, "typeset": Shell.h_declare, "readonly": Shell.h_declare,
    "unset": Shell.h_unset,
    "rm": Shell.h_operands, "unlink": Shell.h_operands, "rmdir": Shell.h_operands,
    "shred": Shell.h_operands, "touch": Shell.h_operands, "truncate": Shell.h_operands,
    "tee": Shell.h_operands, "mkfifo": Shell.h_operands,
    "chmod": Shell.h_perms, "chown": Shell.h_perms, "chgrp": Shell.h_perms,
    "chattr": Shell.h_perms, "setfacl": Shell.h_perms,
    "mv": Shell.h_mv,
    "cp": Shell.h_copy, "install": Shell.h_copy, "ln": Shell.h_copy, "link": Shell.h_copy,
    "rsync": Shell.h_copy, "scp": Shell.h_copy,
    "sed": Shell.h_sed, "gsed": Shell.h_sed,
    "perl": Shell.h_perl_ruby, "ruby": Shell.h_perl_ruby,
    "dd": Shell.h_dd,
    "git": Shell.h_git,
    "patch": Shell.h_patch,
    "find": Shell.h_find,
    "tar": Shell.h_tar, "gtar": Shell.h_tar, "bsdtar": Shell.h_tar,
    "unzip": Shell.h_unzip,
    "zip": Shell.h_zip,
    "curl": Shell.h_download, "wget": Shell.h_download,
    "sort": Shell.h_sort,
    "awk": Shell.h_awk, "gawk": Shell.h_awk,
    "lawkeep": Shell.h_lawkeep,
    "eval": Shell.h_eval,
    "source": Shell.h_source, ".": Shell.h_source,
    "xargs": Shell.h_xargs,
    "watch": Shell.h_watch,
    **{name: Shell.h_compress for name in _COMPRESSORS},
}  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Small helpers


def _braces(text: str) -> list[str]:
    """One level of ``{a,b}`` brace expansion (``laws/{a,b}.py``)."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", text)
    if not m:
        return [text]
    out: list[str] = []
    for choice in m.group(1).split(","):
        out.extend(_braces(text[: m.start()] + choice + text[m.end() :]))
    return out[:MAX_VALUES]


def _after_options(args: list[Arg], short_values: str) -> list[Arg]:
    """The arguments after leading options (``sudo -u bob cmd`` -> ``cmd ...``)."""
    j = 0
    while j < len(args) and args[j].flag is not None:
        f = args[j].flag or ""
        if f == "--":
            return args[j + 1 :]
        if not f.startswith("--") and f[-1] in short_values and len(f) == 2:
            j += 2
        else:
            j += 1
    return args[j:]


def _int_or(arg: Arg | None, default: int) -> int:
    if arg is None or arg.single is None:
        return default
    try:
        return int(arg.single)
    except ValueError:
        return default


def _laws_below(folder: Path) -> Path | None:
    """``folder/laws`` (or the laws folder of the project ``folder`` is inside of, when
    ``folder`` is the project itself or an ancestor of it) if ``folder`` contains the laws."""
    try:
        candidate = folder / "laws"
        if candidate.is_dir() and (
            (folder / "lawkeep.toml").is_file() or (folder / "laws.lock").is_file()
        ):
            return candidate
    except OSError:
        return None
    return None


def analyse(command: str, cwd: str | os.PathLike[str] | None) -> Findings:
    """What ``command`` (shell text) would write to, starting in ``cwd``."""
    findings = Findings()
    Shell(findings, Path(cwd) if cwd else None).run_text(command, "the command")
    return findings
