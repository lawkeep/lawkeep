"""Run laws for the gate (``lawkeep check``) and collect one LawResult per law.

Owner: workstream B (gate).

Laws run through the law-running core in its ``check`` mode (``lawkeep.lawrun``; the
isolation rules, the request on stdin and the write-once results pipe are described there):
a fresh ``python -I -S -B`` process with cwd = root, only Hypothesis's own pytest plugin and
``lawkeep.pytest_plugin`` loaded (plus ``extra_plugins`` from the caller), ``--noconftest``
(the plugin loads only the fixtures of ``laws/conftest.py``), an empty pytest ini, no cache,
``--import-mode=importlib``, the project's source folders and root first on ``sys.path``,
explicit law files as targets (never the project's existing tests), and the profile
(examples, fixed seed, backend, deadline), law ids and ledger in the request.

The code under test runs in the same process as the plugin, so it is trusted: it could still
tamper with the run on purpose. The integrity check flags source files that reach for
lawkeep, pytest or Hypothesis (``integrity.scan_source``); see the README's "Known limits".
"""

from __future__ import annotations

import dataclasses
import difflib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lawkeep import discovery, lawrun, paths
from lawkeep.config import Config, Profile
from lawkeep.errors import SetupError
from lawkeep.models import LawResult

_CROSSHAIR_HINT = (
    "Install the optional symbolic backend: uv add 'lawkeep[deep]' "
    "(or pip install 'lawkeep[deep]'), or run without --deep-check."
)

#: pytest plugins and options of the ``check`` mode (on top of ``lawrun.pytest_args``).
GATE_PLUGINS = ["_hypothesis_pytestplugin", "lawkeep.pytest_plugin"]
GATE_PYTEST_OPTIONS = ["--tb=short", "-o", "console_output_style=classic"]


@dataclass
class RunOutcome:
    results: list[LawResult] = field(default_factory=list["LawResult"])
    notes: list[str] = field(default_factory=list[str])  # plain English
    collection_errors: list[str] = field(default_factory=list[str])  # plain English, per file
    returncode: int = 0  # pytest's own exit code (-1 = timed out)
    stdout: str = ""
    stderr: str = ""
    #: Failing inputs found in this run that are not yet in laws/failing_examples.jsonl:
    #: [{"law_id", "choices" (base64), "example" ({arg: repr} or None), "failure"}].
    #: The runner never writes the ledger itself; ``lawkeep check`` saves these.
    new_failures: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    #: Tests in the law files that have no @law and were therefore not run (pytest node ids).
    ignored: list[str] = field(default_factory=list[str])
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "notes": self.notes,
            "collection_errors": self.collection_errors,
            "returncode": self.returncode,
            "new_failures": self.new_failures,
            "ignored": self.ignored,
            "timed_out": self.timed_out,
        }


def resolve_profile(cfg: Config, profile: str | Profile | None) -> Profile:
    """A Profile object from a name (``None`` = the configured default) or a Profile."""
    if isinstance(profile, Profile):
        return profile
    return cfg.check.get_profile(profile)


def crosshair_available() -> bool:
    return (
        importlib.util.find_spec("hypothesis_crosshair_provider") is not None
        and importlib.util.find_spec("crosshair") is not None
    )


def run_pytest(
    root: Path,
    cfg: Config,
    targets: list[str],
    *,
    profile: str | Profile | None = None,
    law_ids: list[str] | None = None,
    extra_plugins: list[str] | None = None,
    extra_sys_path: list[str] | None = None,
    extra_args: list[str] | None = None,
    ledger: str | None = None,
    timeout: float | None = None,
) -> RunOutcome:
    """Run the given law files (paths relative to root) in the ``check`` mode.

    ``profile`` may be a profile name or a ``config.Profile`` (e.g. with ``backend`` changed).
    ``extra_sys_path``: folders put before the project's source folders (e.g. where an
    ``extra_plugins`` module lives). ``ledger``: another saved failing examples file, or ""
    for none. Never raises for failing laws; raises SetupError when pytest itself cannot run.
    """
    root = Path(root).resolve()
    prof = resolve_profile(cfg, profile)
    if prof.backend == "crosshair" and not crosshair_available():
        raise SetupError(
            "The CrossHair backend (symbolic search, experimental) is not installed.",
            hint=_CROSSHAIR_HINT,
        )
    targets = [str(t) for t in targets]
    missing = [t for t in targets if not (root / t).exists()]
    if missing:
        raise SetupError(
            f"These law files do not exist: {', '.join(missing)}.",
            hint="Pass paths relative to the project root, for example laws/refunds.py.",
        )
    if not targets:
        return RunOutcome(notes=["There were no law files to run."], returncode=5)
    gate: dict[str, Any] = {
        "profile": dataclasses.asdict(prof),
        "law_ids": list(law_ids or []),
    }
    if ledger is not None:
        gate["ledger"] = ledger
    run = lawrun.run(
        root,
        cfg,
        "check",
        {"gate": gate},
        pytest_targets=targets,
        pytest_plugins=[*GATE_PLUGINS, *(extra_plugins or [])],
        pytest_extra=[*GATE_PYTEST_OPTIONS, *(extra_args or [])],
        extra_sys_path=extra_sys_path,
        timeout=timeout,
    )
    if run.timed_out:
        return RunOutcome(
            notes=[
                f"The laws did not finish within {timeout:g} seconds and were stopped. "
                f"A law (or the code it calls) may be stuck in an endless loop."
            ],
            returncode=-1,
            stdout=run.stdout,
            stderr=run.stderr,
            timed_out=True,
        )
    if run.unreadable:
        raise SetupError(
            f"lawkeep could not read the law results ({run.unreadable[0][:80]!r}). Something "
            f"in the law run (possibly the code under test) wrote to lawkeep's results channel.",
        )
    data = run.first("check")
    if data is None or len(run.of_type("check")) > 1:
        raise SetupError(
            f"lawkeep could not run the laws (the test runner stopped with code "
            f"{run.returncode}). Last output:\n{run.output_tail(15)}",
            hint="Check that pytest and hypothesis are installed and that the law files "
            "are valid Python.",
        )
    return _outcome_from_payload(data, run)


def _outcome_from_payload(data: dict[str, Any], run: lawrun.LawRunResult) -> RunOutcome:
    outcome = RunOutcome(
        returncode=run.returncode,
        stdout=run.stdout,
        stderr=run.stderr,
        notes=[str(n) for n in data.get("notes", [])],
        new_failures=list(data.get("new_failures", [])),
        ignored=[str(i) for i in data.get("ignored", [])],
    )
    for item in data.get("results", []):
        outcome.results.append(LawResult.from_dict(item))
    for err in data.get("collection_errors", []):
        path = err.get("path") or "a law file"
        msg = (err.get("message") or "").strip()
        last = msg.splitlines()[-1] if msg else "unknown error"
        outcome.collection_errors.append(f"{path} could not be loaded: {last}")
    if outcome.ignored:
        shown = ", ".join(outcome.ignored[:5]) + (" ..." if len(outcome.ignored) > 5 else "")
        outcome.notes.append(
            f"{len(outcome.ignored)} test(s) in laws/ have no @law sentence, so the gate did "
            f'not run them: {shown}. Add @law("<plain-English rule>") to make one a law, or '
            f"move it out of laws/."
        )
    return outcome


def law_files(root: Path, *, include_drafts: bool = False) -> list[str]:
    """Root-relative paths of the law files the gate runs."""
    return [
        paths.rel(root, p) for p in discovery.iter_python_files(root, include_drafts=include_drafts)
    ]


def run_laws(
    root: Path,
    cfg: Config,
    *,
    profile: str | Profile | None = None,
    law_ids: list[str] | None = None,
    include_drafts: bool = False,
    timeout: float | None = None,
) -> RunOutcome:
    """Run every approved law in laws/ (drafts only when asked).

    Laws that lawkeep finds by reading the files but that did not run (for example because
    their file failed to import) are reported with status ``error`` and a plain explanation.
    """
    root = Path(root).resolve()
    static = discovery.discover_laws(root, include_drafts=include_drafts)
    wanted = set(law_ids) if law_ids else None
    notes: list[str] = []
    if wanted is not None:
        known = {i.law_id for i in static.laws}
        unknown = sorted(wanted - known)
        if unknown:
            hints = ["Check the spelling (`lawkeep check` with no --law runs every law)."]
            for name in unknown:
                guess = difflib.get_close_matches(name, sorted(known), n=1)
                if guess:
                    hints.append(f"Did you mean {guess[0]}?")
            raise SetupError(
                f"No law has the id(s) {', '.join(unknown)}, so nothing was checked. Known "
                f"laws: {', '.join(sorted(known)) or 'none'}.",
                hint=" ".join(hints),
            )
    files = law_files(root, include_drafts=include_drafts)
    if wanted is not None:
        wanted_files = {i.file for i in static.laws if i.law_id in wanted}
        files = [f for f in files if f in wanted_files]
    if not files:
        if not notes:
            notes.append("There are no law files in laws/ yet, so nothing was checked.")
        return RunOutcome(notes=notes, returncode=5)
    outcome = run_pytest(root, cfg, files, profile=profile, law_ids=law_ids, timeout=timeout)
    outcome.notes = notes + outcome.notes
    ran = {r.law_id for r in outcome.results}
    errors_by_file: dict[str, str] = {}
    for msg in outcome.collection_errors:
        errors_by_file[msg.split(" could not be loaded:", 1)[0]] = msg
    for info in static.laws:
        if info.law_id in ran or (wanted is not None and info.law_id not in wanted):
            continue
        if outcome.timed_out:
            why = "The run was stopped because it took too long (see notes)."
        elif info.file in errors_by_file:
            why = errors_by_file[info.file]
        else:
            why = (
                f"lawkeep found this law in {info.file} but pytest did not run it. Check that "
                f"the file imports cleanly and that the law is a test function or class."
            )
        outcome.results.append(
            LawResult(
                law_id=info.law_id,
                sentence=info.sentence,
                status="error",
                level="L1",
                failure_message=why,
                file=info.file,
            )
        )
        ran.add(info.law_id)
    return outcome
