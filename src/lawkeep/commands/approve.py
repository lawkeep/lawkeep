"""`lawkeep approve`: review drafted laws as sentences and examples, and approve or reject them.

Owner: workstream D (law lifecycle).

    lawkeep approve                         # list everything waiting (drafts, proposals)
    lawkeep approve LAW_ID|HISTORY_ID|FILE  # just those
        [--yes | --no]                      # decide without being asked
        [--by NAME]                         # who decided (default: git user.name)
        [--channel "agent permission prompt"]  # where the yes came from (recorded)
        [--accept-unrecorded]               # also decide about laws changed outside lawkeep

In a terminal without --yes/--no, each item is shown (sentence, example table, strength) and
the person is asked y/N. With --json, or with no terminal, nothing is decided: the waiting
items are listed with their example tables and the result is 2 (waiting for a person). An
agent that got the person's yes in its own permission prompt runs
``lawkeep approve ID --yes --channel "agent permission prompt" --by "<their name>"``.

Guard rails (an agent could run this command itself, so a yes must be specific):

- ``--accept-unrecorded`` with no ids decides ONLY the law files changed outside lawkeep;
- ``--yes`` with no ids never decides a weakening proposal (looser, unclear, delete, skip) or
  a change the drafting agent made to an approved file (``draft_edits``): those are approved
  one at a time by id;
- with no terminal, ``--yes`` needs ``--channel`` or ``--by`` (where the yes came from / who
  gave it); the person is then recorded as given (``person:unnamed`` when only a channel is
  given, never the git user name), and the entry records ``terminal: false``. ``lawkeep
  check`` and ``lawkeep report`` show approvals recorded without a terminal: lawkeep records
  who claimed to approve, it cannot confirm that a person did.

On yes: a draft moves from laws/drafts/ into laws/ (parked generators in
laws/drafts/strategies.py are installed with it), a parked proposal is applied (for the
drafting agent's edits: the whole file it wrote, byte for byte), and each is
recorded with ``history.record_change`` (laws.lock refreshed; ``approved_by`` is the person).
On no: the draft or proposal is removed and the rejection is recorded.

Result: 0 decided · 2 still waiting · 3 a problem (nothing matched, a conflict).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from rich.console import RenderableType

from lawkeep import approvals, config, discovery, exitcodes, history, lock, output, paths, ui
from lawkeep.commands.draft import (
    draft_files,
    probe_text,
    quick_check_text,
    read_sidecar,
    write_sidecar,
)
from lawkeep.commands.propose import apply_proposal, read_meta, reject_proposal
from lawkeep.errors import LawkeepError
from lawkeep.examples_table import DRAFT_STRATEGIES, LawProbe, probe_law, render_rows
from lawkeep.models import ExampleRow, HistoryEntry, LawInfo, SimpleReport

HELP = "read the drafted laws and proposed law changes, and say yes or no to each"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "ids",
        nargs="*",
        metavar="ID",
        help="what to decide: a law id, a decision id (h-...) or a draft file (default: "
        "everything waiting)",
    )
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--yes", action="store_true", help="say yes without being asked")
    decision.add_argument(
        "--no", "--reject", dest="no", action="store_true", help="say no without being asked"
    )
    parser.add_argument(
        "--by",
        "--approver",
        dest="by",
        default=None,
        help="the name of the person who decided (default: your git user name)",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help='where the decision was made, e.g. "agent permission prompt" (recorded)',
    )
    parser.add_argument(
        "--accept-unrecorded",
        action="store_true",
        help="also decide about law files someone changed directly, without lawkeep",
    )


# ---------------------------------------------------------------------------------------------
# What can be waiting


@dataclass
class Item:
    kind: str  # "draft" | "proposal" | "waiting" | "unrecorded" | "unconfirmed"
    ref: str  # what to type to select it
    title: str
    laws: list[LawInfo] = field(default_factory=list["LawInfo"])  # drafts
    file: Path | None = None  # drafts
    entry: HistoryEntry | None = None  # proposals / other waiting entries
    paths: list[str] = field(default_factory=list[str])  # unrecorded
    probes: dict[str, LawProbe] = field(default_factory=dict[str, "LawProbe"])
    quick: dict[str, str | None] = field(default_factory=dict[str, str | None])
    strength: dict[str, Any] = field(
        default_factory=dict[str, Any]
    )  # law id -> StrengthResult | None
    strength_missing: str | None = None  # why the strength check could not run
    review: dict[str, Any] | None = None  # unrecorded: laws touched, obvious weakening
    group: approvals.UnconfirmedGroup | None = None  # unconfirmed approvals
    batch_safe: bool = False  # may go in "approve all recommended" (set by _mark_batch_safe)

    @property
    def category(self) -> str:
        """The kind in the one waiting list (``waiting.KINDS``)."""
        if self.kind in ("draft", "unrecorded", "unconfirmed"):
            return self.kind
        if self.entry is not None and from_draft(self.entry):
            return "draft_edit"
        return "proposal"

    def matches(self, token: str, root: Path) -> bool:
        if token == self.ref:
            return True
        if self.group is not None:
            return token in self.group.ids
        if self.kind == "draft" and self.file is not None:
            if token in {info.law_id for info in self.laws}:
                return True
            t = Path(token)
            cand = t if t.is_absolute() else (Path.cwd() / t)
            if (
                cand.resolve() == self.file.resolve()
                or (root / token).resolve() == self.file.resolve()
            ):
                return True
            return token == self.file.name
        if self.entry is not None:
            return token in (self.entry.id, self.entry.law_id)
        if self.kind == "unrecorded":
            return token in self.paths or token == "unrecorded"
        return False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": self.kind,
            "ref": self.ref,
            "title": self.title,
            "group": self.category,
            "batch_safe": self.batch_safe,
        }
        if self.group is not None:
            d["approval"] = self.group.to_dict()
        if self.kind == "draft":
            d["file"] = self.ref
            d["laws"] = [
                {
                    "law_id": info.law_id,
                    "sentence": info.sentence,
                    "probe": self.probes[info.law_id].to_dict()
                    if info.law_id in self.probes
                    else None,
                    "quick_check": self.quick.get(info.law_id),
                }
                for info in self.laws
            ]
        if self.entry is not None:
            d["history_id"] = self.entry.id
            d["law_id"] = self.entry.law_id
            d["direction"] = self.entry.direction
            d["sentence_before"] = self.entry.sentence_before
            d["sentence_after"] = self.entry.sentence_after
            d["reason"] = self.entry.reason
            d["actor"] = self.entry.actor
            d["evidence"] = self.entry.details.get("evidence")
            d["examples"] = self.entry.details.get("examples", [])
            d["action"] = self.entry.action
            d["target_file"] = self.entry.details.get("target_file")
            if self.entry.details.get("from_draft"):
                d["from_draft"] = True
                d["change_kind"] = self.entry.details.get("kind")
                d["changes"] = self.entry.details.get("changes", [])
                d["laws"] = self.entry.details.get("laws", [])
        if self.paths:
            d["paths"] = self.paths
        if self.review is not None:
            d["review"] = self.review
        return d


def collect(root: Path, accept_unrecorded: bool, *, unconfirmed: bool = False) -> list[Item]:
    """What waits, in the order of the one waiting list (``waiting.KINDS``).

    ``accept_unrecorded``: include law files changed outside lawkeep; ``unconfirmed``: include
    approvals recorded without a terminal (to confirm or undo).
    """
    items: list[Item] = []
    if accept_unrecorded:
        changed = list(lock.diff_against_lock(root).paths())
        # laws.lock rewritten by hand: files match the lock, but the history does not explain it
        try:
            unexplained = history.unexplained_lock_paths(lock.read_lock(root), history.read(root))
        except LawkeepError:
            unexplained = []
        changed += [p for p in unexplained if p not in changed]
        if changed:
            items.append(
                Item(
                    "unrecorded",
                    "unrecorded",
                    "law files changed outside lawkeep",
                    paths=changed,
                    review=unrecorded_review(root, changed),
                )
            )
    for f in draft_files(root):
        found = discovery.laws_in_file(f, root)
        rel = paths.rel(root, f)
        items.append(Item("draft", rel, f"draft {rel}", laws=found.laws, file=f))
    entries = history.read(root)
    for e in history.pending(entries):
        kind = "proposal" if e.details.get("proposal_path") else "waiting"
        what = e.law_id or e.details.get("target_file") or "a law file"
        items.append(Item(kind, e.id, f"proposed change to {what}", entry=e))
    if unconfirmed:
        also: list[str] = []
        try:
            from lawkeep import integrity, waiting

            issues = integrity.unconfirmed_approval_issues(root)
            also = waiting.unconfirmed_ids_from(issues)
        except Exception:  # noqa: BLE001 - explicit terminal: false entries are still found
            also = []
        for g in approvals.unconfirmed_groups(entries, also):
            what = ", ".join(g.law_ids) or g.entries[0].action
            items.append(
                Item("unconfirmed", g.id, f"approval of {what} made without a terminal", group=g)
            )
    order = {"draft": 1, "proposal": 2, "draft_edit": 3, "unrecorded": 0, "unconfirmed": 4}
    items.sort(key=lambda it: order.get(it.category, 9))
    return items


def _grade_drafts(root: Path, cfg: config.Config, items: list[Item]) -> list[str]:
    notes: list[str] = []
    ids: list[str] = []
    for it in items:
        if it.kind != "draft" or it.file is None:
            continue
        for info in it.laws:
            it.probes[info.law_id] = probe_law(root, cfg, it.file, info.law_id)
            ids.append(info.law_id)
    if not ids or not cfg.strength.quick_check:
        for it in items:
            it.strength_missing = "the strength check is switched off in lawkeep.toml"
        return notes
    try:
        from lawkeep import strength

        results = strength.run_quick_check(root, cfg, law_ids=ids, include_drafts=True)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"The quick strength check could not run ({type(exc).__name__}: {exc}).")
        for it in items:
            it.strength_missing = "the strength check could not run"
        return notes
    for it in items:
        if it.kind != "draft" or it.file is None:
            continue
        for info in it.laws:
            found = strength.result_for(results, info.law_id, paths.rel(root, it.file))
            it.quick[info.law_id] = quick_check_text(found)
            it.strength[info.law_id] = found
    return notes


def _example_rows(e: HistoryEntry) -> list[ExampleRow]:
    """The example table stored with a proposal (rows that are not objects are skipped)."""
    raw: object = e.details.get("examples", [])
    if not isinstance(raw, list):
        return []
    return [
        ExampleRow.from_dict(cast("dict[str, Any]", r))
        for r in cast("list[object]", raw)
        if isinstance(r, dict)
    ]


def present(item: Item) -> list[str]:
    lines: list[str] = []
    if item.kind == "draft":
        lines.append(f"DRAFT {item.ref}")
        if not item.laws:
            lines.append("  (no @law in this file)")
        for info in item.laws:
            lines.append(f'  law {info.law_id}: "{info.sentence or ""}"')
            p = item.probes.get(info.law_id)
            if p is not None:
                lines += [f"    {t}" for t in probe_text(p)]
            if item.quick.get(info.law_id):
                lines.append(f"    {item.quick[info.law_id]}")
            if p is not None and p.rows:
                lines.append(render_rows(p.rows))
    elif item.kind in ("proposal", "waiting") and item.entry is not None:
        e = item.entry
        what = e.law_id or e.details.get("target_file")
        lines.append(f"PROPOSAL {e.id} for {what} by {e.actor}")
        lines.append(f"  {(e.direction or 'unclear').upper()}: needs your yes")
        if from_draft(e):
            lines.append(
                f"  the drafting agent changed {e.details.get('target_file')} during "
                "`lawkeep draft`; the approved version is still in place"
            )
            lines += [f"  {c}" for c in _changes(e)]
        lines.append(
            f'  before: "{e.sentence_before}"' if e.sentence_before else "  before: (no law)"
        )
        if e.action == "remove_law":
            lines.append("  after:  (law deleted)")
        elif e.sentence_after and e.sentence_after == e.sentence_before:
            lines.append("  after:  same sentence; what the law checks changes")
        else:
            lines.append(f'  after:  "{e.sentence_after}"' if e.sentence_after else "  after:  -")
        lines.append(f"  why:    {e.reason or '(no reason given)'}")
        if e.details.get("explanation"):
            lines.append(f"  what would change: {e.details['explanation']}")
        rows = _example_rows(e)
        if rows:
            lines.append(render_rows(rows))
    elif item.kind == "unrecorded":
        lines.append("UNRECORDED law change: these files differ from laws.lock")
        lines += [f"  {p}" for p in item.paths]
        review = item.review or {}
        if review.get("laws"):
            lines.append(f"  laws in these files: {', '.join(review['laws'])}")
        if review.get("weakening"):
            lines.append("  LOOKS LOOSER: " + "; ".join(review["weakening"]))
        elif review.get("compared_with"):
            lines.append(
                f"  compared with {review['compared_with']}: no obvious weakening found "
                "(lawkeep did not compare what the laws check; read the change)"
            )
        lines.append("  Yes = accept them as they are now (recorded with your name).")
        lines.append("  No = leave them flagged; restore them with git if they are wrong.")
    elif item.kind == "unconfirmed" and item.group is not None:
        first = item.group.entries[0]
        lines.append(
            f"UNCONFIRMED APPROVAL {', '.join(item.group.ids)}: {_action_words(first.action)} "
            f"{', '.join(item.group.law_ids)} approved by {first.approved_by} via "
            f"{first.details.get('channel') or 'unknown channel'}, without a terminal"
        )
        lines.append(
            "  Confirm or undo it in a terminal with `lawkeep approve` (undo puts the law files "
            "back as they were before; both are recorded)."
        )
    return lines


# ---------------------------------------------------------------------------------------------
# What a person sees (docs/OUTPUT-STYLE.md). `present` above stays the JSON `lines`.


def _view_draft(
    root: Path, item: Item, n: int, total: int, approved: list[LawInfo]
) -> list[RenderableType]:
    from lawkeep import explain

    count = f" {n} of {total}" if total > 1 else ""
    if not item.laws:
        return [
            ui.panel(
                ui.status("fail", f"{item.ref} contains no law, so there is nothing to approve."),
                ui.status("fail", "Recommended: reject it."),
                title=f"Draft{count}",
                tone="warn",
            )
        ]
    out: list[RenderableType] = []
    for k, info in enumerate(item.laws, 1):
        strength = explain.strength_status(
            item.strength.get(info.law_id),
            missing=None if info.law_id in item.strength else item.strength_missing,
        )
        desc = discovery.describe_inputs_in_file(item.file, info.qualname) if item.file else {}
        sub = f" · law {k} of {len(item.laws)}" if len(item.laws) > 1 else ""
        out.append(
            explain.draft_law_panel(
                info,
                probe=item.probes.get(info.law_id),
                strength=strength,
                descriptions=desc,
                similar=explain.similar_law(info.sentence, approved),
                title=f"Draft law{count}{sub}",
                file=item.ref,
            )
        )
    return out


def _proposal_recommendation(e: HistoryEntry) -> tuple[str, str]:
    strength = e.details.get("strength")
    if e.action == "add_law" and isinstance(strength, dict):
        return "warn", (
            "Think twice: this new law did not pass the strength check, so it would let real "
            "mistakes through. Say yes only if you still want it."
        )
    if e.action == "remove_law":
        return "warn", "Think twice: the law would be deleted and nothing would check this rule."
    if from_draft(e) and not e.details.get("new_version_runs", True):
        return "fail", "Recommended: reject it. The changed law does not run."
    if from_draft(e) and e.details.get("kind") in ("settings", "generators", "file"):
        return "warn", (
            "Read the change: it affects every law that uses this file. Say yes only if you "
            "asked for it or agree with the reason."
        )
    if e.action == "skip_law" or e.direction == "looser":
        return "warn", (
            "Think twice: this makes the law protect less. Say yes only if you asked for this "
            "change or agree with the reason."
        )
    if e.direction == "unclear":
        return "warn", (
            "Read the examples: lawkeep could not tell whether this protects more or less. "
            "Say yes only if the new sentence is what you want."
        )
    return "ok", "Recommended: approve if the new sentence is what you want."


def _who(actor: str | None) -> str:
    if not actor:
        return "unknown"
    if actor.startswith("agent:"):
        return f"coding agent ({actor.split(':', 1)[1]})"
    return actor.split(":", 1)[-1]


def from_draft(e: HistoryEntry) -> bool:
    """True for an edit the drafting agent made to an approved file (``draft_edits``)."""
    return bool(e.details.get("from_draft"))


def _changes(e: HistoryEntry) -> list[str]:
    raw: object = e.details.get("changes")
    if not isinstance(raw, list):
        return []
    return [str(c) for c in cast("list[object]", raw)]


def _view_proposal(item: Item, n: int, total: int) -> list[RenderableType]:
    from lawkeep import explain

    assert item.entry is not None
    e = item.entry
    kind = e.details.get("kind") if from_draft(e) else "law"
    if e.action == "remove_law":
        after = "(the law would be deleted)"
    elif e.action == "skip_law":
        after = "(the law would be skipped: lawkeep would stop checking it)"
    elif e.sentence_after and e.sentence_after == e.sentence_before:
        after = "the same sentence, but what the law checks changes"
    else:
        after = f"“{e.sentence_after}”" if e.sentence_after else "-"
    rows = _example_rows(e)
    explanation = e.details.get("explanation")
    what: list[tuple[str, str | None]]
    if kind == "law":
        what = [
            ("Law now:", f"“{e.sentence_before}”" if e.sentence_before else "(no law yet)"),
            ("Would become:", after),
        ]
        laws: object = e.details.get("laws")
        if from_draft(e) and isinstance(laws, list) and len(cast("list[object]", laws)) > 1:
            what.append(("Laws touched:", ", ".join(str(x) for x in cast("list[object]", laws))))
    else:
        what = [
            (
                "What:",
                {
                    "settings": "Settings (lawkeep.toml)",
                    "generators": "Input generators (laws/strategies.py)",
                }.get(str(kind), str(e.details.get("target_file") or "a file")),
            ),
            ("Changes:", "; ".join(_changes(e)) or "-"),
        ]
    parts: list[RenderableType] = [
        ui.status(
            "ok" if e.direction in ("stricter", "same") else "warn",
            explain.direction_text(e.direction),
        ),
    ]
    if from_draft(e):
        parts.append(
            ui.status(
                "info",
                f"The drafting AI changed {e.details.get('target_file')} during `lawkeep draft` "
                "although it was asked to write drafts only. The approved version is still in "
                "place; nothing changes unless you say yes.",
            )
        )
    parts += [
        ui.blank(),
        ui.label_value(
            [
                *what,
                ("Asked by:", _who(e.actor)),
                ("Why:", e.reason or "(no reason given)"),
                (
                    "What changes:",
                    explain.plain_explanation(explanation) if explanation else None,
                ),
            ]
        ),
    ]
    if rows:
        parts += [
            ui.blank(),
            ui.bold("Examples: does each version of the law accept what the code did?"),
            explain.examples_table(rows, proposal=True),
        ]
    diff = e.details.get("diff")
    if from_draft(e) and isinstance(diff, str) and diff and kind != "law":
        parts += [ui.blank(), ui.bold("The change:"), ui.dim(diff)]
    tone, rec = _proposal_recommendation(e)
    ident = f"law id {e.law_id} · " if e.law_id else f"file {e.details.get('target_file')} · "
    parts += [
        ui.blank(),
        ui.status(tone, ui.bold(rec)),
        ui.ident(f"{ident}decision id {e.id}"),
    ]
    count = f" {n} of {total}" if total > 1 else ""
    title = "Change made by the drafting AI" if from_draft(e) else "Proposed law change"
    return [ui.panel(*parts, title=f"{title}{count}", tone="warn")]


def _view_unrecorded(item: Item) -> list[RenderableType]:
    review = item.review or {}
    parts: list[RenderableType] = [
        ui.status(
            "warn",
            "These law files were changed directly, without going through lawkeep (an "
            "unrecorded change). lawkeep cannot tell who changed them or whether a person "
            "agreed.",
        ),
        ui.indent(ui.group(*[ui.dim(p) for p in item.paths])),
    ]
    if review.get("laws"):
        parts.append(ui.label_value([("Laws in these files:", ", ".join(review["laws"]))]))
    if review.get("weakening"):
        parts.append(ui.warning("This change looks looser: " + "; ".join(review["weakening"])))
    elif review.get("compared_with"):
        parts.append(
            ui.status(
                "info",
                f"Compared with {review['compared_with']}, lawkeep found no obvious weakening. "
                "It did not run the laws, so read the change yourself (`git diff`).",
            )
        )
    parts += [
        ui.blank(),
        ui.label_value(
            [
                ("Yes:", "accept the files as they are now (recorded with your name)."),
                ("No:", "leave them flagged; put them back with git if they are wrong."),
            ]
        ),
    ]
    return [ui.panel(*parts, title="Law files changed outside lawkeep", tone="warn")]


_ACTION_WORDS = {
    "add_law": "a new law",
    "add_example": "a new example for",
    "change_law": "a change to",
    "rename_target": "a renamed law",
    "remove_law": "deleting",
    "skip_law": "skipping",
    "change_settings": "a settings change",
    "accept_unrecorded_change": "accepting law files changed outside lawkeep",
}


def _action_words(action: str) -> str:
    return _ACTION_WORDS.get(action, action.replace("_", " "))


def _view_unconfirmed(item: Item, n: int, total: int) -> list[RenderableType]:
    assert item.group is not None
    first = item.group.entries[0]
    sentences = [e.sentence_after or e.sentence_before for e in item.group.entries]
    what = "; ".join(f"“{x}”" for x in sentences if x) or ", ".join(item.group.law_ids)
    parts: list[RenderableType] = [
        ui.status(
            "warn",
            "A coding agent recorded this approval on someone's behalf, without a terminal. "
            "lawkeep cannot tell whether a person really said yes.",
        ),
        ui.blank(),
        ui.label_value(
            [
                ("Approved:", f"{_action_words(first.action)} {what}".strip()),
                ("Recorded as approved by:", _who(first.approved_by)),
                ("Where:", str(first.details.get("channel") or "unknown")),
                ("When:", first.timestamp),
                ("Asked by:", _who(first.actor)),
                ("Why:", first.reason or "(no reason given)"),
            ]
        ),
        ui.blank(),
        ui.label_value(
            [
                ("Confirm:", "you did say yes; lawkeep records it with your name."),
                (
                    "Undo:",
                    "put the law files back as they were before this approval (recorded).",
                ),
                ("Skip:", "decide later."),
            ]
        ),
        ui.blank(),
        ui.status("warn", ui.bold("Confirm only if you remember approving this; else undo.")),
        ui.ident(f"decision id {', '.join(item.group.ids)}"),
    ]
    count = f" {n} of {total}" if total > 1 else ""
    return [ui.panel(*parts, title=f"Approval made without a terminal{count}", tone="warn")]


def overview(items: list[Item]) -> RenderableType:
    """The one waiting list at a glance: what kinds wait, how many, and what lawkeep suggests."""
    from lawkeep import waiting

    counts = {k: 0 for k in waiting.KINDS}
    for it in items:
        counts[it.category] = counts.get(it.category, 0) + 1
    rows: list[list[RenderableType]] = []
    for kind in waiting.KINDS:
        if not counts.get(kind):
            continue
        one, many = waiting.LABELS[kind]
        meaning, suggestion = waiting.EXPLAIN[kind]
        rows.append(
            [
                ui.bold(f"{counts[kind]} {one if counts[kind] == 1 else many}"),
                meaning,
                suggestion,
            ]
        )
    safe = sum(1 for it in items if it.batch_safe)
    parts: list[RenderableType] = [
        ui.heading(f"{ui.plural(len(items), 'thing waits', 'things wait')} for your decision"),
        ui.table(["What", "What it means", "lawkeep suggests"], rows, ratios=[3, 5, 4]),
    ]
    if safe:
        parts.append(
            ui.status(
                "ok",
                f"{ui.plural(safe, 'item is', 'items are')} recommended and safe to approve "
                "together (new drafts that work and are strong, and stricter changes).",
            )
        )
    return ui.group(*parts)


def view(
    root: Path, item: Item, n: int = 1, total: int = 1, approved: list[LawInfo] | None = None
) -> list[RenderableType]:
    """Renderables for one waiting item (what a person reads before deciding)."""
    if approved is None:
        try:
            approved = discovery.discover_laws(root).laws
        except Exception:  # noqa: BLE001 - only used to spot duplicates
            approved = []
    if item.kind == "draft":
        return _view_draft(root, item, n, total, approved)
    if item.kind in ("proposal", "waiting") and item.entry is not None:
        return _view_proposal(item, n, total)
    if item.kind == "unrecorded":
        return _view_unrecorded(item)
    if item.kind == "unconfirmed":
        return _view_unconfirmed(item, n, total)
    return []


def _question(item: Item) -> str:
    if item.kind == "draft":
        n = len(item.laws)
        if n == 1:
            return "Approve this law?"
        return f"Approve all {n} laws in this draft?" if n else "Approve this draft?"
    if item.kind == "unrecorded":
        return "Accept these changed law files?"
    if item.kind == "unconfirmed":
        return "Confirm or undo this approval?"
    return "Approve this change?"


def _decision_line(item: Item, yes: bool, ok: bool, message: str) -> list[RenderableType]:
    if not ok:
        return [ui.status("fail", f"Could not do that: {message}")]
    sentences = ", ".join(f"“{i.sentence}”" for i in item.laws if i.sentence)
    if item.kind == "draft":
        text = (
            f"Approved. {sentences or 'The draft'} is now a law; `lawkeep check` will check it."
            if yes
            else "Rejected. The draft was deleted."
        )
    elif item.kind == "unrecorded":
        text = (
            "Accepted. The changed law files are recorded with your name."
            if yes
            else "Left flagged. Put the files back with git if they are wrong."
        )
    elif item.kind == "unconfirmed":
        text = (
            "Confirmed. Your yes is recorded."
            if yes
            else "Undone. The law files are back as they were before that approval."
        )
    else:
        text = "Approved. The change is applied and recorded." if yes else "Rejected."
    return [ui.status("ok" if yes else "info", text), ui.indent(ui.dim(message))]


def _final_screen(
    code: int,
    decided: list[dict[str, Any]],
    waiting: list[Item],
    problems: list[str],
    notes: list[str],
    *,
    root: Path,
    show_waiting: bool,
    extra: list[str] | None = None,
) -> str:
    """The closing screen: verdict, what happened, the items still waiting, the next step."""
    out: list[RenderableType] = []
    n_w = len(waiting)
    if code == exitcodes.SETUP_PROBLEM:
        out.append(
            ui.banner(
                "PROBLEM",
                f"lawkeep could not do everything you asked "
                f"({ui.plural(len(problems), 'problem')}).",
                tone="problem",
            )
        )
    elif n_w:
        done = f" You decided {len(decided)}." if decided else " Nothing was decided yet."
        out.append(
            ui.banner(
                "WAITING FOR YOUR DECISION",
                f"{ui.plural(n_w, 'thing waits', 'things wait')} for a person's decision.{done}",
                tone="wait",
            )
        )
    elif decided:
        out.append(
            ui.banner(
                "DONE",
                f"You decided {ui.plural(len(decided), 'item')}. Every decision is recorded in "
                "the law history.",
                tone="ok",
            )
        )
    else:
        out.append(
            ui.banner(
                "NOTHING TO DECIDE",
                "Nothing waits for you: no drafts, proposed law changes, law changes made "
                "outside lawkeep or approvals to confirm.",
                tone="ok",
            )
        )
    for p in problems:
        out.append(ui.status("fail", p))
    for line in extra or []:
        out.append(ui.status("info", line))
    for n in notes:
        out.append(ui.status("info", n.removeprefix("note: ")))
    if show_waiting and waiting:
        out += [
            ui.blank(),
            overview(waiting),
            ui.blank(),
            ui.dim(
                "A law is a rule your code must always follow. Read each sentence and its "
                "examples, then decide."
            ),
        ]
        try:
            approved = discovery.discover_laws(root).laws
        except Exception:  # noqa: BLE001
            approved = []
        for k, it in enumerate(waiting, 1):
            out.append(ui.blank())
            out += view(root, it, k, len(waiting), approved)
    out.append(ui.blank())
    if n_w:
        first = next((it for it in waiting if it.kind != "unconfirmed"), None)
        if first is None:
            out.append(
                ui.next_step(
                    "confirm or undo each approval in a terminal with `lawkeep approve` (a "
                    "coding agent cannot do this for you)."
                )
            )
        else:
            cmd = (
                "lawkeep approve --accept-unrecorded --yes"
                if first.kind == "unrecorded"
                else f"lawkeep approve {first.ref} --yes"
            )
            out.append(
                ui.next_step(
                    "decide in a terminal with `lawkeep approve` (it asks about each item and "
                    f"offers to approve the safe ones together), or run `{cmd}` (or `--no`). "
                    "A coding agent must first ask the person in its own permission prompt."
                )
            )
    elif code == exitcodes.SETUP_PROBLEM:
        out.append(ui.next_step("run `lawkeep approve` with no arguments to see what is waiting."))
    elif decided:
        out.append(ui.next_step("run `lawkeep check` to check your code against every law."))
    else:
        out.append(ui.next_step("nothing to do. New drafts appear here after `lawkeep draft`."))
    return ui.render(*out)


# ---------------------------------------------------------------------------------------------
# Decisions


def _interactive() -> bool:
    """True when a person can be asked in this terminal (tests patch this)."""
    return sys.stdin.isatty()


def _is_weakening(item: Item) -> bool:
    """Approved only by id (never by ``--yes`` without ids): changes that weaken or may weaken
    a law, and every change the drafting agent made to an approved file (the person reviews
    each of those, even a stricter one)."""
    e = item.entry
    if e is None:
        return False
    return (
        e.direction in ("looser", "unclear")
        or e.action in ("remove_law", "skip_law")
        or from_draft(e)
    )


def unrecorded_review(root: Path, changed: list[str]) -> dict[str, Any]:
    """What a person accepts with ``--accept-unrecorded``: which laws changed and whether the
    edit obviously weakens them (compared with the last git commit; no code runs)."""
    import subprocess

    from lawkeep.direction import static_weakening

    out: dict[str, Any] = {"laws": [], "weakening": [], "compared_with": None}
    try:
        cfg = config.load_config(root)
        examples = cfg.check.get_profile().examples
    except LawkeepError:
        examples = 200
    for rel in changed:
        p = root / rel
        if rel == paths.CONFIG_FILENAME:
            out["weakening"].append(
                "lawkeep.toml changed (settings such as examples per law apply to every law)"
            )
            continue
        if not rel.endswith(".py"):
            continue
        try:
            old_src = subprocess.run(
                ["git", "show", f"HEAD:./{rel}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            old_src = None
        old_text = old_src.stdout if old_src is not None and old_src.returncode == 0 else None
        new_text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        if old_text is not None:
            out["compared_with"] = "the last git commit"
        old_laws = discovery.laws_in_source(old_text, file=p, root=root).by_id() if old_text else {}
        new_laws = discovery.laws_in_source(new_text, file=p, root=root).by_id() if new_text else {}
        for law_id in sorted(set(old_laws) | set(new_laws)):
            if law_id not in out["laws"]:
                out["laws"].append(law_id)
            if law_id not in new_laws:
                out["weakening"].append(f"{law_id} is deleted")
            elif law_id in old_laws and old_text and new_text:
                for why in static_weakening(
                    old_text,
                    old_laws[law_id].qualname,
                    new_text,
                    new_laws[law_id].qualname,
                    examples,
                ):
                    out["weakening"].append(f"{law_id}: {why}")
        if old_text is None and new_text is not None and not new_laws:
            out["laws"].append(rel)
    return out


def _ask(question: str) -> bool | None:
    """Ask in the terminal; None when there is no terminal (tests patch this)."""
    return output.yes_no(question, default=False, stream_in=sys.stdin)


UNCONFIRMED_CHOICES = {"c": "confirm", "u": "undo", "s": "skip"}


def _choose(question: str, options: dict[str, str]) -> str | None:
    """Ask for one of several answers (a letter or the word); None when there is no terminal
    or no answer (tests patch this)."""
    if not sys.stdin.isatty():
        return None
    keys = "/".join(options)
    while True:
        sys.stdout.write(f"{question} [{keys}] ")
        sys.stdout.flush()
        answer = sys.stdin.readline()
        if not answer:
            return None
        a = answer.strip().lower()
        for key, word in options.items():
            if a in (key, word):
                return word
        sys.stdout.write(
            "Please answer " + ", ".join(f"{k} ({w})" for k, w in options.items()) + ".\n"
        )


def _is_batch_safe(item: Item, approved: list[LawInfo]) -> bool:
    """May this item go in "approve all recommended new drafts and stricter changes"?

    Only new drafts whose every law works with the code, is measured strong and is not a
    likely duplicate, and waiting proposals that are stricter (or same meaning). Never anything
    looser, unclear, a deletion or skip, a weak new law, a change by the drafting AI, an
    unrecorded change or an unconfirmed approval.
    """
    from lawkeep import explain

    if item.kind == "draft" and item.file is not None and item.laws:
        for info in item.laws:
            strength = explain.strength_status(
                item.strength.get(info.law_id),
                missing=None if info.law_id in item.strength else item.strength_missing,
            )
            tone, _ = explain.recommendation(
                item.probes.get(info.law_id),
                strength,
                explain.similar_law(info.sentence, approved),
            )
            if tone != "ok" or not strength.measured or strength.weak:
                return False
        return True
    if item.kind == "proposal" and item.entry is not None:
        e = item.entry
        return (
            not _is_weakening(item)
            and e.direction in ("stricter", "same")
            and e.action not in ("remove_law", "skip_law")
            and not isinstance(e.details.get("strength"), dict)
        )
    return False


def _mark_batch_safe(items: list[Item], approved: list[LawInfo]) -> None:
    for it in items:
        it.batch_safe = _is_batch_safe(it, approved)


def _approve_draft(
    root: Path, item: Item, person: str, channel: str, terminal: bool = False
) -> tuple[bool, str]:
    assert item.file is not None
    ddir = paths.drafts_dir(root)
    target = paths.laws_dir(root) / item.file.relative_to(ddir)
    if target.exists():
        return False, (
            f"{paths.rel(root, target)} already exists, so the draft {item.ref} cannot be moved "
            "there. To change an existing law use `lawkeep propose`; or rename the draft file."
        )
    if not item.laws:
        try:
            item.file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return False, (
                f"{item.ref} cannot be read as UTF-8 text, so lawkeep cannot find its laws. "
                "Save it as UTF-8 and try again, or reject it"
            )
        except OSError:
            pass
        return False, f"{item.ref} has no @law in it; reject it instead"
    side = read_sidecar(root)
    meta = side["files"].get(item.ref, {})
    notes: list[str] = []
    parked = ddir / DRAFT_STRATEGIES
    if parked.is_file():
        shutil.copyfile(parked, paths.strategies_path(root))
        parked.unlink()
        notes.append("installed the input generators kept in laws/drafts/strategies.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(item.file), str(target))
    ids: list[str] = []
    for info in item.laws:
        p = item.probes.get(info.law_id)
        from lawkeep import explain

        evidence: list[str] = []
        if p is not None:
            evidence.append(explain.probe_one_line(p))
        if item.strength.get(info.law_id) is not None:
            evidence.append(explain.strength_one_line(item.strength[info.law_id]) or "")
        rec = history.record_change(
            root,
            action="add_law",
            actor=meta.get("actor") or "agent:other",
            law_id=info.law_id,
            direction="stricter",
            reason=meta.get("request") or "",
            permission_used="ask",
            approved_by=person,
            status="applied",
            sentence_after=info.sentence,
            details={
                "evidence": " · ".join(e for e in evidence if e) or None,
                "examples": [r.to_dict() for r in (p.rows if p else [])],
                "channel": channel,
                "terminal": terminal,
                "draft_file": item.ref,
                "permission_key": "add_law",
            },
        )
        ids.append(rec.entry.id)
    side["files"].pop(item.ref, None)
    write_sidecar(root, side)
    extra = f" ({'; '.join(notes)})" if notes else ""
    return True, (
        f"Approved {', '.join(info.law_id for info in item.laws)}: moved to {paths.rel(root, target)}, "
        f"recorded as {', '.join(ids)}{extra}."
    )


def _reject_draft(
    root: Path, item: Item, person: str, channel: str, terminal: bool = False
) -> tuple[bool, str]:
    assert item.file is not None
    side = read_sidecar(root)
    meta = side["files"].get(item.ref, {})
    item.file.unlink(missing_ok=True)
    for info in item.laws or [LawInfo(law_id=item.ref, sentence=None, file=item.ref, qualname="")]:
        history.record_change(
            root,
            action="reject_draft",
            actor=person,
            law_id=info.law_id,
            reason=meta.get("request") or "",
            permission_used="ask",
            status="rejected",
            sentence_after=info.sentence,
            details={"channel": channel, "draft_file": item.ref, "drafted_by": meta.get("actor")},
        )
    side["files"].pop(item.ref, None)
    write_sidecar(root, side)
    extra = ""
    parked = paths.drafts_dir(root) / DRAFT_STRATEGIES
    if parked.is_file() and not draft_files(root):
        parked.unlink()
        extra = " The input generators kept for the drafts were removed too."
    return True, f"Rejected the draft {item.ref}; it was deleted.{extra}"


def _decide_recorded(
    root: Path, item: Item, yes: bool, person: str, channel: str, terminal: bool = False
) -> tuple[bool, str]:
    """`_decide`, plus: a yes recorded without a terminal keeps a copy of the files it changed
    (``approvals.keep_copies``), so a person can undo it later."""
    keep = yes and not terminal and item.kind != "unconfirmed"
    before = approvals.snapshot(root) if keep else {}
    n0 = len(history.read(root)) if keep else 0
    ok, message = _decide(root, item, yes, person, channel, terminal)
    if ok and keep:
        try:
            approvals.keep_copies(root, before, history.read(root)[n0:])
        except OSError:
            pass
    return ok, message


def _decide(
    root: Path, item: Item, yes: bool, person: str, channel: str, terminal: bool = False
) -> tuple[bool, str]:
    if item.kind == "unconfirmed":
        assert item.group is not None
        if not terminal:
            return False, (
                "An approval made without a terminal is confirmed or undone by a person in a "
                "terminal: run `lawkeep approve` there."
            )
        decide_group = approvals.confirm if yes else approvals.undo
        return decide_group(root, item.group, person=person, channel=channel)
    if item.kind == "unrecorded":
        if not yes:
            return True, (
                "Left the unrecorded change flagged. Restore the files with git "
                f"(e.g. `git checkout -- {' '.join(item.paths)}`) if they are wrong."
            )
        review = item.review or {}
        weak: list[str] = review.get("weakening") or []
        how = f"via {channel}" + ("" if terminal else ", no terminal")
        evidence = (
            f"{', '.join(item.paths)} changed outside lawkeep; "
            + (f"looks looser: {'; '.join(weak)}" if weak else "no obvious weakening found")
            + f" · accepted {how}"
        )
        rec = history.record_change(
            root,
            action="accept_unrecorded_change",
            actor=person,
            law_id=", ".join(review.get("laws") or []) or None,
            direction="looser" if weak else "unclear",
            permission_used="ask",
            approved_by=person,
            reason="a person accepted law files changed outside lawkeep",
            details={
                "paths": item.paths,
                "channel": channel,
                "terminal": terminal,
                "laws": review.get("laws") or [],
                "weakening": weak,
                "evidence": evidence,
            },
        )
        return True, f"Accepted the change to {', '.join(item.paths)} (recorded as {rec.entry.id})."
    if yes and not lock.diff_against_lock(root).is_empty:
        return False, (
            "Laws changed outside lawkeep, so lawkeep will not apply anything until a person "
            "decides about that: run `lawkeep approve --accept-unrecorded`."
        )
    if item.kind == "draft":
        return (_approve_draft if yes else _reject_draft)(root, item, person, channel, terminal)
    assert item.entry is not None
    if item.kind == "proposal":
        if read_meta(root, item.entry) is None and yes:
            return False, (
                f"The parked proposal {item.entry.id} is missing; reject it with "
                f"`lawkeep approve {item.entry.id} --no`."
            )
        if yes:
            return apply_proposal(
                root, item.entry, approved_by=person, channel=channel, terminal=terminal
            )
        return reject_proposal(root, item.entry, decided_by=person, channel=channel)
    # a waiting entry without a parked file: record the decision only
    e = item.entry
    history.record_change(
        root,
        action=e.action,
        actor=e.actor if yes else person,
        law_id=e.law_id,
        direction=e.direction,
        reason=e.reason,
        permission_used="ask",
        approved_by=person if yes else None,
        status="applied" if yes else "rejected",
        sentence_before=e.sentence_before,
        sentence_after=e.sentence_after,
        details={"channel": channel, "terminal": terminal},
        refers_to=e.id,
    )
    return True, f"{'Approved' if yes else 'Rejected'} {e.id} ({e.law_id})."


def _person(root: Path, by: str | None, terminal: bool = True) -> str:
    if by:
        return by if by.startswith("person:") else f"person:{by}"
    if not terminal:
        # Without a terminal lawkeep cannot tell who said yes; never borrow the git user name.
        return "person:unnamed"
    return history.default_person(root)


def _waiting_summary(items: list[Item]) -> dict[str, Any]:
    """The additive ``waiting_for_person`` JSON for these items (same shape as `check`)."""
    from lawkeep import waiting

    wl = waiting.WaitingList(
        [
            waiting.WaitingItem(
                it.category,
                it.ref,
                it.title,
                it.group.ids
                if it.group is not None
                else ([it.ref] if it.kind != "unrecorded" else it.paths),
            )
            for it in items
        ]
    )
    return wl.to_dict()


def _decision_word(item: Item, yes: bool) -> str:
    if item.kind == "unconfirmed":
        return "confirmed" if yes else "undone"
    return "approved" if yes else "rejected"


@dataclass
class _Session:
    """What happened in one `lawkeep approve` run."""

    lines: list[str] = field(default_factory=list[str])
    decided: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    waiting: list[Item] = field(default_factory=list["Item"])
    problems: list[str] = field(default_factory=list[str])


def _record(
    root: Path,
    sess: _Session,
    it: Item,
    yes: bool,
    *,
    person: str,
    channel: str,
    terminal: bool,
    show: bool,
) -> bool:
    ok, message = _decide_recorded(root, it, yes, person, channel, terminal)
    (sess.lines if ok else sess.problems).append(message)
    if show:
        ui.show(*_decision_line(it, yes, ok, message))
    if ok:
        sess.decided.append(
            {
                **it.to_dict(),
                "decision": _decision_word(it, yes),
                "message": message,
                "channel": channel,
                "terminal": terminal,
                "by": person,
            }
        )
    return ok


def _ask_each(
    root: Path,
    items: list[Item],
    sess: _Session,
    *,
    person: str,
    channel: str | None,
    approved_laws: list[LawInfo],
    offer_batch: bool,
) -> None:
    """A person in a terminal decides: changes made outside lawkeep first, then (optionally)
    every safe item at once, then the rest one by one."""
    ui.show(
        overview(items),
        ui.dim(
            "A law is a rule your code must always follow. Read each sentence and its "
            "examples, then answer y (approve) or n (reject)."
        ),
    )
    first = [it for it in items if it.kind == "unrecorded"]
    rest = [it for it in items if it.kind != "unrecorded"]
    total = len(items)
    n = 0
    for it in first:
        n += 1
        ui.show(ui.blank(), *view(root, it, n, total, approved_laws))
        answer = _ask(_question(it))
        if answer is None:
            sess.waiting.extend(first[n - 1 :] + rest)
            return
        _record(
            root,
            sess,
            it,
            answer,
            person=person,
            channel=channel or "terminal",
            terminal=True,
            show=True,
        )
    safe = [it for it in rest if it.batch_safe] if offer_batch else []
    if len(safe) >= 2 and lock.diff_against_lock(root).is_empty:
        ui.show(
            ui.blank(),
            ui.heading(f"Approve the {len(safe)} recommended items together?"),
            ui.bullets([it.title for it in safe]),
            ui.dim(
                "Only new drafts that work with your code and are strong, and stricter "
                "changes. Never anything looser or unclear, changes by the drafting AI, law "
                "changes made outside lawkeep, or approvals made without a terminal."
            ),
        )
        answer = _ask(f"Approve all {len(safe)} recommended new drafts and stricter changes?")
        if answer is None:
            sess.waiting.extend(rest)
            return
        if answer:
            for it in safe:
                _record(
                    root,
                    sess,
                    it,
                    True,
                    person=person,
                    channel=channel or "terminal (approve all recommended)",
                    terminal=True,
                    show=True,
                )
            rest = [it for it in rest if it not in safe]
    for k, it in enumerate(rest):
        n += 1
        ui.show(ui.blank(), *view(root, it, n, total, approved_laws))
        if it.kind == "unconfirmed":
            choice = _choose(_question(it), UNCONFIRMED_CHOICES)
            if choice is None:
                sess.waiting.extend(rest[k:])
                return
            if choice == "skip":
                sess.waiting.append(it)
                continue
            yes = choice == "confirm"
        else:
            answer = _ask(_question(it))
            if answer is None:
                sess.waiting.extend(rest[k:])
                return
            yes = answer
        _record(
            root,
            sess,
            it,
            yes,
            person=person,
            channel=channel or "terminal",
            terminal=True,
            show=True,
        )


def select(
    items: list[Item], root: Path, ids: list[str], *, yes: bool, accept_unrecorded: bool
) -> tuple[list[Item], list[Item], list[str]]:
    """What one ``lawkeep approve`` run decides: ``(decided, held back, unmatched ids)``.

    With ids: the items they name. ``--accept-unrecorded`` without ids: only law files changed
    outside lawkeep. ``--yes`` without ids: everything except weakening proposals and changes
    by the drafting AI (held back: those are approved one at a time, by id). Also used by the
    guard to tell the person what an agent's ``lawkeep approve`` would decide."""
    if ids:
        selected = [it for it in items if any(it.matches(t, root) for t in ids)]
        unmatched = [t for t in ids if not any(it.matches(t, root) for it in items)]
        return selected, [], unmatched
    if accept_unrecorded:
        # "accept that hand edit" must not also approve drafts or weakening proposals
        return [it for it in items if it.kind == "unrecorded"], [], []
    if yes:
        held_back = [it for it in items if _is_weakening(it)]
        return [it for it in items if not _is_weakening(it)], held_back, []
    return items, [], []


def run(args: argparse.Namespace) -> int:
    root = paths.require_root(args.root)
    cfg = config.load_config(root)
    notes = [f"note: {w}" for w in cfg.warnings]
    terminal = _interactive()
    # No ids and no --yes/--no: the one waiting list (everything, nothing decided without a
    # person in a terminal).
    listing = not args.ids and not (args.yes or args.no) and not args.accept_unrecorded
    items = collect(root, args.accept_unrecorded or listing, unconfirmed=listing or bool(args.ids))
    problems: list[str] = []
    items, held_back, unmatched = select(
        items, root, args.ids, yes=bool(args.yes), accept_unrecorded=bool(args.accept_unrecorded)
    )
    for t in unmatched:
        problems.append(f"Nothing waiting matches {t!r}.")
    if not args.ids and args.accept_unrecorded:
        if not items:
            notes.append(
                "No law files changed outside lawkeep. (--accept-unrecorded without ids decides "
                "only such changes; drafts and proposals are approved by their id.)"
            )
    elif not args.ids and args.yes:
        if held_back and not items:
            problems.append(
                "Weakening proposals, and changes the drafting AI made to approved files, are "
                "approved one at a time: name each one, for example "
                f"`lawkeep approve {held_back[0].ref} --yes`."
            )
    if not items and held_back:
        report = SimpleReport(
            kind="approve",
            exit_code=exitcodes.WAITING,
            summary="WAITING FOR YOUR DECISION: " + " ".join(problems),
            lines=notes + [ln for it in held_back for ln in present(it)],
            data={
                "waiting": [it.to_dict() for it in held_back],
                "decided": [],
                "problems": [],
                "waiting_for_person": _waiting_summary(held_back),
            },
            hint="Approve a weakening change only by its id, after the person has seen it.",
        )
        text = None
        if not args.json:
            text = _final_screen(
                report.exit_code,
                [],
                held_back,
                [],
                notes,
                root=root,
                show_waiting=True,
                extra=[
                    "Changes that weaken a law, and changes the drafting AI made to approved "
                    "files, are approved one at a time, by their id, after the person has seen "
                    "them: " + ", ".join(f"`lawkeep approve {it.ref} --yes`" for it in held_back)
                ],
            )
        output.emit(report, args.json, text=text)
        return report.exit_code
    if not items:
        code = exitcodes.SETUP_PROBLEM if problems else exitcodes.ALL_HOLD
        report = SimpleReport(
            kind="approve",
            exit_code=code,
            summary=" ".join(problems) if problems else "Nothing is waiting for your decision.",
            lines=notes,
            data={
                "waiting": [],
                "decided": [],
                "problems": problems,
                "waiting_for_person": _waiting_summary([]),
            },
            hint="Run `lawkeep approve` with no arguments to see everything waiting."
            if problems
            else None,
        )
        text = None
        if not args.json:
            text = _final_screen(code, [], [], problems, notes, root=root, show_waiting=False)
        output.emit(report, args.json, text=text)
        return report.exit_code

    notes += [f"note: {n}" for n in _grade_drafts(root, cfg, items)]
    try:
        approved_laws = discovery.discover_laws(root).laws
    except Exception:  # noqa: BLE001 - only used to spot duplicates
        approved_laws = []
    _mark_batch_safe(items, approved_laws)
    person = _person(root, args.by, terminal)
    sess = _Session(lines=list(notes), problems=problems)
    sess.waiting.extend(held_back)
    extra: list[str] = []
    if held_back:
        sess.lines.append(
            f"note: {len(held_back)} weakening proposal(s) or drafting-agent change(s) were "
            "not decided by this --yes "
            f"without ids; approve each one by its id: " + ", ".join(it.ref for it in held_back)
        )
        extra.append(
            f"{ui.plural(len(held_back), 'change')} weaken a law or came from the drafting "
            "AI, so `--yes` without ids did not decide them. Approve each one by its id: "
            + ", ".join(f"`lawkeep approve {it.ref} --yes`" for it in held_back)
        )

    asking = not (args.yes or args.no)
    if args.yes and not terminal and not args.channel and not args.by:
        sess.waiting = items + held_back
        sess.lines.append(
            "There is no terminal here, so lawkeep cannot tell who said yes. If a person said "
            "yes in your agent's permission prompt, run the command again with "
            '--channel "agent permission prompt" --by "<their name>". Nothing was decided.'
        )
        extra.append(sess.lines[-1])
    elif asking and (args.json or not terminal):
        sess.waiting = items + held_back
    elif asking:
        _ask_each(
            root,
            items,
            sess,
            person=person,
            channel=args.channel,
            approved_laws=approved_laws,
            offer_batch=listing,
        )
    else:
        # accept unrecorded changes first, so later approvals start from a clean lock
        items.sort(key=lambda it: 0 if it.kind == "unrecorded" else 1)
        yes = bool(args.yes)
        channel = args.channel or (
            f"command line (--{'yes' if args.yes else 'no'}"
            + (")" if terminal else ", no terminal)")
        )
        for it in items:
            _record(
                root, sess, it, yes, person=person, channel=channel, terminal=terminal, show=False
            )

    waiting, decided, problems, lines = sess.waiting, sess.decided, sess.problems, sess.lines
    for it in waiting:
        lines += present(it)
    codes = [exitcodes.ALL_HOLD]
    if waiting:
        codes.append(exitcodes.WAITING)
    if problems:
        codes.append(exitcodes.SETUP_PROBLEM)
    code = exitcodes.combine(*codes)
    parts: list[str] = []
    if decided:
        parts.append(f"{len(decided)} decided")
    if waiting:
        parts.append(f"{len(waiting)} waiting for a person's decision")
    if problems:
        parts.append(f"{len(problems)} problem(s): " + " ".join(problems))
    summary = "; ".join(parts) + "."
    if waiting:
        summary = "WAITING FOR YOUR DECISION: " + summary
    from lawkeep import presence

    report = SimpleReport(
        kind="approve",
        exit_code=code,
        summary=summary,
        lines=lines,
        data={
            "waiting": [it.to_dict() for it in waiting],
            "decided": decided,
            "problems": problems,
            "approved_by": person,
            "waiting_for_person": _waiting_summary(waiting),
            **presence.detect().to_dict(),
        },
        hint=(
            "Decide with `lawkeep approve ID --yes` or `--no` (an agent should first ask the "
            "person in its own permission prompt)."
            if waiting
            else None
        ),
    )
    text = None
    if not args.json:
        if (args.yes or args.no) and decided:
            for d in decided:
                word = "Approved" if d["decision"] == "approved" else "Rejected"
                extra.append(f"{word}: {d.get('message', '')}")
        text = _final_screen(
            code,
            decided,
            waiting,
            problems,
            notes,
            root=root,
            show_waiting=True,
            extra=extra,
        )
    output.emit(report, args.json, text=text)
    return report.exit_code
