"""Append-only audit trail plus the out/-only write guard.

Every byte this process writes goes through :meth:`Audit.safe_write`, which
refuses any path that does not live under an ``out/`` directory.  Records are
fsynced one line at a time so a kill at any instant leaves a complete trail.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

AUDIT_FILE = "audit.jsonl"
AUDIT_VERSION = 1


class AuditPathRefused(PermissionError):
    """Raised when a write target escapes the out root the caller anchored on."""


def _now_precise() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _contains(root: Path, target: Path) -> bool:
    """True when ``target`` is ``root`` or lives anywhere beneath it.

    Both paths are already resolved, so ``..`` segments and symlinks have been
    collapsed to their real targets before this comparison.
    """
    return target == root or root in target.parents


class Audit:
    """Append-only writer. One ``run_start``, one record per patient, one ``run_end``."""

    def __init__(self, out_dir: str, root: str | None = None):
        self.dir = Path(out_dir).expanduser().resolve()
        anchor = Path(root).expanduser().resolve() if root is not None else self.dir
        if not _contains(anchor, self.dir):
            raise AuditPathRefused(f"refusing audit directory outside {anchor}: {self.dir}")
        self.anchor = anchor
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self._assert_inside(self.dir / AUDIT_FILE)
        self._fh = open(self.path, "a", encoding="utf-8")
        self._starts: dict[str, tuple[str, float]] = {}

    # ------------------------------------------------------------------ guard

    def _assert_inside(self, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        if not _contains(self.anchor, target):
            raise AuditPathRefused(f"refusing write outside {self.anchor}: {target}")
        return target

    def safe_write(self, path: str | Path, text: str) -> Path:
        """Guard, then write atomically (temp sibling + fsync + rename)."""
        target = self._assert_inside(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, target)
            dir_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return target

    # ----------------------------------------------------------------- writing

    def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str)
        self._fh.write(line + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    # ------------------------------------------------------------- public API

    def event(self, run_id: str, kind: str, **fields) -> None:
        """Append one real, timestamped trace record.

        Used for the live view: ``run_begin`` (the run is live, before the slow
        ingest), ``page`` as each page is read, ``stage`` around each pipeline
        stage. Every field comes from the work actually done at that instant.
        """
        record = {
            "v": AUDIT_VERSION,
            "kind": kind,
            "run_id": run_id,
            "ts": _now_precise(),
        }
        record.update(fields)
        self._append(record)

    def run_start(self, run_id: str, shift: dict, pages: list, model: str) -> None:
        started = _now_precise()
        self._starts[run_id] = (started, datetime.now().timestamp())
        inputs = []
        for page in pages or []:
            if not isinstance(page, dict):
                continue
            inputs.append(
                {
                    "page": page.get("page"),
                    "path": page.get("path"),
                    "sha256": page.get("sha256"),
                    "kind": page.get("kind"),
                    "readable": bool(page.get("readable", True)),
                    "refusal_reason": page.get("refusal_reason"),
                }
            )
        self._append(
            {
                "v": AUDIT_VERSION,
                "kind": "run_start",
                "run_id": run_id,
                "ts": started,
                "shift": shift,
                "model": model,
                "page_count": len(inputs),
                "inputs": inputs,
                "input_hashes": {
                    str(i.get("path")): i.get("sha256")
                    for i in inputs
                    if i.get("path")
                },
            }
        )

    def patient(self, run_id: str, patient: dict) -> None:
        patient = patient or {}
        confidence: dict = {"granularity": "patient+item"}
        overall = patient.get("confidence")
        if isinstance(overall, (int, float)):
            confidence["overall"] = overall
        for key in ("meds", "actions", "pending"):
            values = [
                item.get("confidence")
                for item in patient.get(key) or []
                if isinstance(item, dict)
                and isinstance(item.get("confidence"), (int, float))
            ]
            if values:
                confidence[key] = values
        refusals = patient.get("refused_fields")
        if refusals is None:
            refusals = patient.get("refused")
        self._append(
            {
                "v": AUDIT_VERSION,
                "kind": "patient",
                "run_id": run_id,
                "ts": _now_precise(),
                "patient_id": patient.get("id"),
                "bed": patient.get("bed") or patient.get("bed_latest"),
                "bed_first": patient.get("bed_first"),
                "bed_latest": patient.get("bed_latest"),
                "mrn": patient.get("mrn"),
                "name_as_written": patient.get("name_as_written"),
                "pages": patient.get("pages"),
                "confidence": confidence,
                "refusals": refusals or [],
                "ambiguities": patient.get("ambiguities") or [],
            }
        )

    def run_end(self, run_id: str, exit_reason: str, extra: dict | None = None) -> None:
        extra = dict(extra or {})
        stopped_by = extra.pop("stopped_by", None)
        honoured_in = extra.pop("honoured_in", None)
        started_iso, started_epoch = self._starts.get(run_id, (_now_precise(), None))
        duration = (
            round(datetime.now().timestamp() - started_epoch, 3)
            if started_epoch is not None
            else None
        )
        record = {
            "v": AUDIT_VERSION,
            "kind": "run_end",
            "run_id": run_id,
            "ts": _now_precise(),
            "started_at": started_iso,
            "exit_reason": exit_reason,
            "duration_s": duration,
            "stopped_by": stopped_by,
            "honoured_in": honoured_in,
        }
        record.update(extra)
        self._append(record)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass

    def __enter__(self) -> "Audit":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
