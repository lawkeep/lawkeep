"""What a coding agent's ``lawkeep approve`` would decide, in a few plain lines for the person.

Used by the guard (``guard.py``) when it answers "ask" for ``lawkeep approve``: the agent's
permission prompt then shows the person *what* they are about to approve, not only that an
approval is coming. For example::

    lawkeep: your coding agent wants to record YOUR approval of 1 law change:
    • Loosen “A refund never includes a fee” → “A refund may include a fee of at most $1” (looser)
    Say yes only if you asked for this. Not sure? Say no — nothing is lost; you can approve
    later yourself with `lawkeep approve`.

It reads the command's arguments (``writes.ApproveRun``) with ``lawkeep approve``'s own parser,
lists what waits with ``approve.collect`` and picks what this run decides with
``approve.select``: the same selection the real command makes. Nothing is written and no
project code runs (drafts are read from their syntax tree, the history and ``laws.lock`` as
files, unrecorded edits compared with git). When anything cannot be worked out (arguments
only known at run time, an unknown id, a broken project), the text says so plainly: "lawkeep
could not tell which law change this is — say no unless you are sure". Never raises.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

from lawkeep.adapters.writes import ApproveRun

if TYPE_CHECKING:
    from lawkeep.commands.approve import Item

#: At most this many item lines; the rest become "…and N more".
MAX_LINES = 5
#: Sentences longer than this are shortened with "…".
MAX_SENTENCE = 90

UNKNOWN = "lawkeep could not tell which law change this is — say no unless you are sure."


def _short(text: str | None) -> str:
    s = " ".join((text or "").split())
    return s if len(s) <= MAX_SENTENCE else s[: MAX_SENTENCE - 1].rstrip() + "…"


def _q(text: str | None) -> str:
    return f"“{_short(text)}”"


class _Parser(argparse.ArgumentParser):
    """Raises instead of printing usage and exiting (a hook must print only its answer)."""

    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _parse(words: list[str]) -> argparse.Namespace | None:
    """``lawkeep approve``'s own arguments (None when they do not parse)."""
    from lawkeep.commands import approve

    parser = _Parser(add_help=False, exit_on_error=False)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=None)
    approve.add_arguments(parser)
    try:
        args, extra = parser.parse_known_args(words)
    except (argparse.ArgumentError, SystemExit, ValueError):
        return None
    if extra:
        return None
    return args


def _strength_word(details: dict[str, Any]) -> str:
    s: object = details.get("strength")
    if not isinstance(s, dict) or not s:
        return ""
    d = cast("dict[str, Any]", s)
    if d.get("flags") or not (d.get("quick_check_caught") or d.get("planted_bugs_caught")):
        return " (weak: lawkeep's quick check says it lets mistakes through)"
    return " (strong)"


def item_line(item: Item, yes: bool) -> list[str]:
    """One plain line per thing this item decides (an unrecorded item: one per file)."""
    from lawkeep.commands.approve import from_draft

    kind: str = item.kind
    if kind == "draft":
        laws = list(item.laws)
        first = next((i.sentence for i in laws if i.sentence), None)
        what = _q(first) if first else f"in {item.ref}"
        more = f" (+{len(laws) - 1} more in the same file)" if len(laws) > 1 else ""
        return [f"Add new law {what}{more}" if yes else f"REJECT the new draft law {what}{more}"]
    if kind == "unrecorded":
        files: list[str] = list(item.paths)
        if yes:
            return [f"Accept a hand edit to {p} (made outside lawkeep)" for p in files]
        return [f"Leave the hand edit to {p} flagged (nothing is accepted)" for p in files]
    if kind == "unconfirmed" and item.group is not None:
        entries = list(item.group.entries)
        sentences = [e.sentence_after or e.sentence_before for e in entries]
        what = "; ".join(_q(s) for s in sentences if s) or ", ".join(item.group.law_ids)
        verb = "Confirm" if yes else "UNDO"
        return [f"{verb} an approval made without a terminal: {what}"]
    e = item.entry
    if e is None:
        return [f"Decide {item.ref}"]
    before, after = e.sentence_before, e.sentence_after
    where = e.law_id or e.details.get("target_file") or "a law file"
    law = _q(after or before) if (after or before) else str(where)
    if from_draft(e):
        target = e.details.get("target_file") or where
        if not yes:
            return [f"REJECT the drafting AI's change to {target}"]
        line = f"Accept the drafting AI's change to {target}"
    elif e.action == "add_law":
        line = f"Add new law {law}{_strength_word(e.details)}"
    elif e.action == "remove_law":
        line = f"Delete the law {_q(before) if before else law}"
    elif e.action == "skip_law":
        line = f"Switch off the law {_q(before) if before else law}"
    else:
        change = f"{_q(before)} → {_q(after)}" if before and after and before != after else law
        if e.direction == "looser":
            line = f"Loosen {change} (looser: protects less)"
        elif e.direction == "stricter":
            line = f"Tighten {change} (stricter)"
        elif e.direction == "same":
            line = f"Update {change} (same meaning)"
        else:
            line = f"Change {change} (lawkeep cannot tell whether this protects less)"
    return [line if yes else f"REJECT: {line}"]


def _resolve(run: ApproveRun, cwd: Path) -> tuple[list[str], list[str], str]:
    """(item lines, notes, mode) for one run; mode is "yes", "no" or "show" (only lists what
    waits). Raises on anything unexpected (the caller then says it could not tell)."""
    from lawkeep import paths
    from lawkeep.commands import approve

    if run.args is None:
        return [], [UNKNOWN], "yes"
    args = _parse(run.args)
    if args is None:
        return [], [UNKNOWN], "yes"
    here = Path(run.cwd) if run.cwd else cwd
    root_arg = args.root or run.root
    start = (here / root_arg) if root_arg else here
    root = paths.find_root(start)
    if root is None:
        return [], [f"lawkeep could not find the project here. {UNKNOWN}"], "yes"
    ids: list[str] = list(args.ids or [])
    yes, no = bool(args.yes), bool(args.no)
    listing = not ids and not (yes or no) and not args.accept_unrecorded
    items = approve.collect(
        root, bool(args.accept_unrecorded) or listing, unconfirmed=listing or bool(ids)
    )
    if listing:
        if not items:
            return [], ["It only shows what waits for a decision; right now nothing does."], "show"
        lines = [ln for it in items for ln in item_line(it, True)]
        note = (
            "Without --yes or --no it decides nothing unless you answer its questions "
            "yourself in a terminal."
        )
        return lines, [note], "show"
    selected, held_back, unmatched = approve.select(
        items, root, ids, yes=yes, accept_unrecorded=bool(args.accept_unrecorded)
    )
    lines = [ln for it in selected for ln in item_line(it, not no)]
    notes: list[str] = []
    for t in unmatched:
        notes.append(f"Nothing waiting is called “{_short(t)}”.")
    if unmatched and not selected:
        notes.append(UNKNOWN)
    if held_back:
        n = len(held_back)
        notes.append(
            f"{n} riskier {'change' if n == 1 else 'changes'} (weakening a law, or by the "
            "drafting AI) stay waiting: --yes without ids never decides them."
        )
    if not selected and not unmatched and not held_back:
        notes.append("Nothing is waiting for a decision right now, so it would change nothing.")
    return lines, notes, "no" if no else "yes"


def describe(runs: list[ApproveRun], cwd: Path) -> str:
    """The confirmation text for the person: what these ``lawkeep approve`` runs decide."""
    lines: list[str] = []
    notes: list[str] = []
    modes: set[str] = set()
    for run in runs or [ApproveRun(None)]:
        try:
            more, more_notes, mode = _resolve(run, cwd)
        except Exception:  # noqa: BLE001 - the prompt must always appear
            more, more_notes, mode = [], [UNKNOWN], "yes"
        lines += more
        notes += [n for n in more_notes if n not in notes]
        if more:
            modes.add(mode)
    says_yes, says_no = "yes" in modes, "no" in modes
    n = len(lines)
    things = "law change" if n == 1 else "law changes"
    if n and modes == {"show"}:
        head = (
            f"lawkeep: your coding agent wants to run `lawkeep approve`, which lists {n} "
            f"{'thing' if n == 1 else 'things'} waiting for YOUR decision:"
        )
    elif not n:
        head = (
            "lawkeep: your coding agent wants to run `lawkeep approve`, which records YOUR "
            "decision on law changes."
        )
    elif says_yes and says_no:
        head = f"lawkeep: your coding agent wants to record YOUR decision on {n} {things}:"
    elif says_no:
        head = f"lawkeep: your coding agent wants to record YOUR rejection of {n} {things}:"
    else:
        head = f"lawkeep: your coding agent wants to record YOUR approval of {n} {things}:"
    shown = [f"• {ln}" for ln in lines[:MAX_LINES]]
    if n > MAX_LINES:
        shown.append(f"…and {n - MAX_LINES} more")
    tail = (
        "Say yes only if you asked for this. Not sure? Say no — nothing is lost; you can "
        "decide later yourself with `lawkeep approve`."
    )
    return "\n".join([head, *shown, *notes, tail])
