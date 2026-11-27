"""Assembly: ingest -> extract -> structure -> rules -> compose -> verify -> audit.

The kill switch is honoured between pages (passed into ``ingest``) and between
every stage here.  ``handoff.md`` is written only when ``verify`` passes; on
failure the violations are audited, the handoff is absent, and the exit is 1.
Every output byte goes through :meth:`src.audit.Audit.safe_write`, which refuses
paths outside ``out/``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .audit import Audit, AuditPathRefused
from .killswitch import KillSwitch, trip

PINNED = (
    ("ingest", "ingest"),
    ("extract", "extract"),
    ("structure", "structure"),
    ("rules", "apply"),
    ("compose", "compose"),
    ("compose", "compose_gaps"),
    ("verify", "verify"),
)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _model_label() -> str:
    path = os.environ.get("SBH_MODEL_PATH")
    if not path:
        return "template"
    candidate = Path(path).expanduser()
    if candidate.is_file() and candidate.suffix.lower() == ".gguf":
        return "local-gguf"
    return "template"


def _load_modules() -> dict:
    package = __package__ or "src"
    loaded: dict = {}
    missing: list[str] = []
    for module_name, attr in PINNED:
        try:
            module = importlib.import_module(f"{package}.{module_name}")
        except Exception as exc:
            missing.append(f"{package}.{module_name} ({exc.__class__.__name__}: {exc})")
            continue
        fn = getattr(module, attr, None)
        if fn is None:
            missing.append(f"{package}.{module_name}.{attr}")
        else:
            loaded[attr] = fn
    if missing:
        raise RuntimeError("pipeline modules unavailable: " + "; ".join(missing))
    return loaded


def _unreadable_pages(pages: list, fields_doc: dict | None = None) -> list:
    found = {
        page.get("page")
        for page in pages or []
        if isinstance(page, dict) and page.get("readable") is False
    }
    for page in (fields_doc or {}).get("pages") or []:
        if isinstance(page, dict) and page.get("unreadable") is True:
            found.add(page.get("page"))
    return sorted(p for p in found if p is not None)


def _merge_injections(*sources: list) -> list:
    merged: list = []
    seen: set = set()
    for source in sources:
        for item in source or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("page"), item.get("quote"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _patient_record(patient: dict) -> dict:
    record = dict(patient or {})
    refused = record.get("refused_fields")
    if refused is None:
        refused = list(record.get("refused") or [])
    record["refused_fields"] = list(refused or [])
    for key in ("pages", "issues", "pending", "actions", "ambiguities"):
        if record.get(key) is None:
            record[key] = []
    return record


def _shift(shift_date: str) -> dict:
    return {
        "date": shift_date,
        "ward": os.environ.get("SBH_WARD", "RO"),
        "handover_to": os.environ.get("SBH_HANDOVER_TO", "night"),
    }


def _status_record(
    state: dict, exit_reason: str, verify: dict | None, stop: dict | None
) -> dict:
    return {
        "run_id": state["run_id"],
        "shift": state["shift"],
        "state": exit_reason,
        "exit_reason": exit_reason,
        "updated_at": _now(),
        "started_at": state["started_at"],
        "out_dir": str(state["out_dir"]),
        "model": state["model"],
        "patients": len(state["patients"]),
        "unreadable_pages": state["unreadable_pages"],
        "contradictions": len(state["contradictions"]),
        "injections": len(state["injections"]),
        "verify": verify or {"ok": None, "violations": []},
        "stopped_by": (stop or {}).get("stopped_by"),
        "honoured_in": (stop or {}).get("honoured_in"),
        "inputs": [
            {
                "page": p.get("page"),
                "sha256": p.get("sha256"),
                "readable": p.get("readable"),
            }
            for p in state["pages"]
            if isinstance(p, dict)
        ],
    }


def _tripped(ks: KillSwitch | None) -> bool:
    if ks is None:
        return False
    if ks.check():
        return True
    return ks.stopped_by is not None


def _run_once(
    inbox: Path, out_root: Path, date_override: str | None, ks: KillSwitch | None
) -> int:
    modules = _load_modules()
    started_at = _now()
    stop = ks.check if ks is not None else None

    try:
        pages_doc = modules["ingest"](str(inbox), stop=stop)
    except Exception as exc:
        out_dir = out_root / (date_override or _today())
        audit = Audit(str(out_dir))
        audit.run_start(_now(), _shift(out_dir.name), [], _model_label())
        audit.run_end(
            _now(), "error", {"stage": "ingest", "error": f"{type(exc).__name__}: {exc}"}
        )
        audit.close()
        print(f"ingest failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    pages = pages_doc.get("pages") or []
    shift_date = date_override or pages_doc.get("shift_date") or _today()
    run_id = pages_doc.get("run_id") or started_at
    out_dir = out_root / shift_date
    audit = Audit(str(out_dir))
    model = _model_label()
    shift = _shift(shift_date)
    audit.run_start(run_id, shift, pages, model)

    state = {
        "run_id": run_id,
        "shift": shift,
        "shift_date": shift_date,
        "pages": pages,
        "out_dir": out_dir,
        "model": model,
        "started_at": started_at,
        "patients": [],
        "contradictions": [],
        "injections": [],
        "unreadable_pages": _unreadable_pages(pages),
        "gaps": [],
    }
    handoff_path = out_dir / "handoff.md"
    if handoff_path.exists():
        handoff_path.unlink()

    def summary_doc() -> dict:
        """ARCHITECTURE §4 plus the two §9 extensions (injections, ambiguities)."""
        return {
            "run_id": state["run_id"],
            "shift": state["shift"],
            "patients": state["patients"],
            "unreadable_pages": state["unreadable_pages"],
            "contradictions": state["contradictions"],
            "injections": state["injections"],
        }

    def finish(exit_reason: str, handoff_text: str | None, verify: dict | None) -> None:
        gaps_error = None
        try:
            gaps_text = modules["compose_gaps"](
                state["patients"],
                state["contradictions"],
                state["unreadable_pages"],
                state["injections"],
                state["gaps"],
            )
        except Exception as exc:
            gaps_error = f"{type(exc).__name__}: {exc}"
            gaps_text = (
                "# Gaps and refusals\n\n"
                f"gaps.md could not be composed ({gaps_error}).\n"
                f"unreadable pages: {state['unreadable_pages']}\n"
            )
        audit.safe_write(out_dir / "summary.json", json.dumps(summary_doc(), indent=2, default=str))
        audit.safe_write(out_dir / "gaps.md", gaps_text)
        if verify and verify.get("ok") and handoff_text is not None:
            audit.safe_write(handoff_path, handoff_text)
        stop_fields = ks.audit_fields() if ks is not None else None
        status = _status_record(state, exit_reason, verify, stop_fields)
        audit.safe_write(out_dir / "status.json", json.dumps(status, indent=2, default=str))
        for patient in state["patients"]:
            audit.patient(state["run_id"], patient)
        audit.run_end(
            state["run_id"],
            exit_reason,
            {
                "model": model,
                "verify_ok": None if verify is None else verify.get("ok"),
                "violations": [] if verify is None else verify.get("violations"),
                "patients": len(state["patients"]),
                "unreadable_pages": state["unreadable_pages"],
                "contradictions": len(state["contradictions"]),
                "injections": len(state["injections"]),
                "gaps_error": gaps_error,
                **({"stopped_by": stop_fields["stopped_by"], "honoured_in": stop_fields["honoured_in"]} if stop_fields else {}),
            },
        )
        audit.close()

    if _tripped(ks):
        finish("stopped", None, None)
        return 0

    try:
        fields_doc = modules["extract"](pages_doc)
        state["unreadable_pages"] = _unreadable_pages(pages, fields_doc)
    except Exception as exc:
        finish("error", None, {"ok": None, "violations": [f"extract: {exc}"]})
        return 1
    if _tripped(ks):
        finish("stopped", None, None)
        return 0

    try:
        struct_doc = modules["structure"](fields_doc, run_start=started_at)
        state["patients"] = [
            _patient_record(p) for p in struct_doc.get("patients") or []
        ]
        state["injections"] = _merge_injections(
            fields_doc.get("injections"), struct_doc.get("injections")
        )
    except Exception as exc:
        finish("error", None, {"ok": None, "violations": [f"structure: {exc}"]})
        return 1
    if _tripped(ks):
        finish("stopped", None, None)
        return 0

    try:
        rules_doc = modules["apply"](state["patients"], state["injections"])
        state["patients"] = [
            _patient_record(p) for p in rules_doc.get("patients") or state["patients"]
        ]
        state["contradictions"] = list(rules_doc.get("contradictions") or [])
        state["gaps"] = list(rules_doc.get("gaps") or [])
        state["injections"] = _merge_injections(
            state["injections"], rules_doc.get("injections")
        )
    except Exception as exc:
        finish("error", None, {"ok": None, "violations": [f"rules: {exc}"]})
        return 1
    if _tripped(ks):
        finish("stopped", None, None)
        return 0

    try:
        handoff_text, _allowed = modules["compose"](
            state["patients"], state["contradictions"], state["shift"]
        )
    except Exception as exc:
        finish("error", None, {"ok": None, "violations": [f"compose: {exc}"]})
        return 1
    if _tripped(ks):
        finish("stopped", None, None)
        return 0

    try:
        ok, violations = modules["verify"](handoff_text, summary_doc())
    except Exception as exc:
        finish("error", None, {"ok": None, "violations": [f"verify: {exc}"]})
        return 1
    verify_result = {"ok": bool(ok), "violations": list(violations or [])}

    if not verify_result["ok"]:
        finish("verify_failed", None, verify_result)
        print(
            f"verifier refused the handoff: {len(verify_result['violations'])} violation(s)",
            file=sys.stderr,
        )
        return 1

    finish("completed", handoff_text, verify_result)
    print(f"handoff written: {handoff_path} ({len(state['patients'])} patient(s))")
    return 0


def _snapshot(inbox: Path) -> dict:
    snapshot: dict = {}
    if not inbox.is_dir():
        return snapshot
    for entry in sorted(inbox.iterdir()):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        snapshot[entry.name] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def _cmd_run(args) -> int:
    inbox = Path(args.inbox).expanduser()
    out_root = Path(args.out).expanduser()
    if not inbox.is_dir():
        print(f"inbox not found: {inbox}", file=sys.stderr)
        return 1
    ks = KillSwitch()
    try:
        return _run_once(inbox, out_root, args.date, ks)
    finally:
        ks.restore()


def _cmd_watch(args) -> int:
    inbox = Path(args.inbox).expanduser()
    out_root = Path(args.out).expanduser()
    if not inbox.is_dir():
        print(f"inbox not found: {inbox}", file=sys.stderr)
        return 1
    ks = KillSwitch()
    interval = max(0.2, float(args.interval))
    try:
        seen = _snapshot(inbox)
        if seen:
            _run_once(inbox, out_root, args.date, ks)
        while True:
            if _tripped(ks):
                return 0
            deadline = time.monotonic() + interval
            while time.monotonic() < deadline:
                if _tripped(ks):
                    return 0
                time.sleep(0.1)
            current = _snapshot(inbox)
            if any(name not in seen for name in current):
                _run_once(inbox, out_root, args.date, ks)
                seen = current
            else:
                seen = current
    except KeyboardInterrupt:
        return 0
    finally:
        ks.restore()


def _cmd_kill(args) -> int:
    path = trip(args.stop_path)
    print(path)
    return 0


def _cmd_status(args) -> int:
    out_root = Path(args.out).expanduser()
    candidates = sorted(
        out_root.glob("*/status.json"),
        key=lambda p: p.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        print(json.dumps({"state": "no-runs", "out_dir": str(out_root)}, indent=2))
        return 0
    print(candidates[0].read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Shift Buddy handover agent: run, watch, kill, status.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="one run over the inbox")
    run_parser.add_argument("--inbox", default="inbox")
    run_parser.add_argument("--out", default="out")
    run_parser.add_argument("--date", default=None, help="force the shift date")
    run_parser.set_defaults(handler=_cmd_run)

    watch_parser = sub.add_parser("watch", help="poll the inbox and run on new files")
    watch_parser.add_argument("--inbox", default="inbox")
    watch_parser.add_argument("--out", default="out")
    watch_parser.add_argument("--date", default=None)
    watch_parser.add_argument("--interval", type=float, default=2.0)
    watch_parser.set_defaults(handler=_cmd_watch)

    kill_parser = sub.add_parser("kill", help="create the STOP file")
    kill_parser.add_argument("--stop-path", default=None)
    kill_parser.set_defaults(handler=_cmd_kill)

    status_parser = sub.add_parser("status", help="print the latest status.json")
    status_parser.add_argument("--out", default="out")
    status_parser.set_defaults(handler=_cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except AuditPathRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
