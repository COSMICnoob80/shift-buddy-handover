"""Shared helpers for the guardrail suite.  Stdlib only; no third-party imports.

The helpers deliberately reuse the real fixture loader, inbox builder and output
readers from ``evals.run`` so the tests exercise the same 40-case data the eval
harness scores, instead of a parallel copy of them.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.run import (  # noqa: E402  (sys.path is set above)
    DEFAULT_DATE,
    build_inbox as _eval_build_inbox,
    load_cases as _eval_load_cases,
    read_audit as _eval_read_audit,
    read_outputs as _eval_read_outputs,
)

FIXTURES = REPO_ROOT / "fixtures" / "cases.json"

# Ambient variables that would change what the pipeline does.
_SCRUBBED_ENV = ("SBH_MODEL_PATH", "SBH_STOP_FILE", "SBH_WARD", "SBH_HANDOVER_TO")


@contextlib.contextmanager
def clean_env():
    """Temporarily remove pipeline-affecting env vars, restoring them after."""
    saved = {key: os.environ.pop(key) for key in _SCRUBBED_ENV if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


@contextlib.contextmanager
def workspace():
    path = Path(tempfile.mkdtemp(prefix="sbh-tests-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def load_cases() -> list:
    return _eval_load_cases(FIXTURES)


def cases_by_id() -> dict:
    return {case["id"]: case for case in load_cases()}


def make_case(
    pages: list,
    *,
    case_id: str = "SYN-1",
    family: str = "synthetic",
    date: str = DEFAULT_DATE,
    expected: dict | None = None,
) -> dict:
    return {
        "id": case_id,
        "family": family,
        "shift_date": date,
        "pages": pages,
        "expected": expected or {},
    }


def text_page(text: str, page: int = 1) -> dict:
    return {"page": page, "readable": True, "text": text}


def refused_page(page: int, reason: str) -> dict:
    return {"page": page, "readable": False, "reason": reason}


@dataclass
class RunResult:
    rc: int
    out: Path
    shift: Path | None
    summary: dict | None
    status: dict | None
    gaps: str
    handoff: str | None
    audit: list
    files: list
    stdout: str = ""
    stderr: str = ""

    @property
    def handoff_written(self) -> bool:
        return self.handoff is not None

    def run_end(self) -> dict | None:
        return next((rec for rec in self.audit if rec.get("kind") == "run_end"), None)

    def run_start(self) -> dict | None:
        return next((rec for rec in self.audit if rec.get("kind") == "run_start"), None)

    def patient_records(self) -> list:
        return [rec for rec in self.audit if rec.get("kind") == "patient"]

    def refused_fields(self) -> list:
        return [
            field
            for patient in (self.summary or {}).get("patients") or []
            for field in patient.get("refused_fields") or []
        ]


def collect_outputs(out, rc: int, stdout: str = "", stderr: str = "") -> RunResult:
    out = Path(out)
    found = _eval_read_outputs(out)
    shift = found.get("shift_dir")
    files = sorted(p.name for p in shift.iterdir()) if shift is not None else []
    return RunResult(
        rc=rc,
        out=out,
        shift=shift,
        summary=found.get("summary"),
        status=found.get("status"),
        gaps=found.get("gaps_text") or "",
        handoff=found.get("handoff_text"),
        audit=_eval_read_audit(out),
        files=files,
        stdout=stdout,
        stderr=stderr,
    )


def build_case_inbox(case: dict, inbox) -> None:
    """Materialise a case's pages into ``inbox`` using the eval harness builder.

    Exposed so a test can create the inputs before snapshotting a directory and
    then attribute every subsequent write to the pipeline.
    """
    _eval_build_inbox(case, Path(inbox))


def run_pipeline(case: dict, workdir, date: str | None = None) -> RunResult:
    """Drive the real assembly boundary (``src.cli._run_once``) in-process."""
    from src import cli

    date = date or case.get("shift_date") or DEFAULT_DATE
    inbox = Path(workdir) / "inbox"
    out = Path(workdir) / "out"
    build_case_inbox(case, inbox)
    stdout, stderr = io.StringIO(), io.StringIO()
    with clean_env(), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = cli._run_once(inbox, out, date, None)
    return collect_outputs(out, rc, stdout.getvalue(), stderr.getvalue())


def cli_env(**extra) -> dict:
    env = {key: value for key, value in os.environ.items() if key not in _SCRUBBED_ENV}
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.update({key: str(value) for key, value in extra.items()})
    return env


def run_cli(argv: list, cwd, timeout: float = 60, **env_extra):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *argv],
        cwd=str(cwd),
        env=cli_env(**env_extra),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def write_inbox(inbox: Path, texts: list, date: str = DEFAULT_DATE) -> None:
    """Smallest possible inbox: one text page per entry, ordered by seq."""
    inbox.mkdir(parents=True, exist_ok=True)
    for index, text in enumerate(texts, start=1):
        name = f"handoff_{date}_{index:02d}.txt"
        (inbox / name).write_text(text, encoding="utf-8")


def audit_lines(path: Path) -> list:
    """Every non-empty line of an audit file must parse as JSON on its own."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def verify_handoff(result: RunResult) -> tuple[bool, list]:
    """Re-run the real verifier over the shipped handoff and summary."""
    from src.verify import verify

    return verify(result.handoff or "", result.summary or {})
