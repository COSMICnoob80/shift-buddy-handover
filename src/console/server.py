"""Local web console over the REAL pipeline.

No third-party packages: ``http.server`` plus the standard library. The console
is a viewer with a start button, not a simulator. Every number it prints is
derived from the records the pipeline actually appended to ``audit.jsonl``.

Endpoints
---------
GET  /                     the console page
GET  /console.css          the reused visual base
GET  /healthz              hosted-demo health check (synthetic data only)
GET  /api/meta?run=ID      run metadata + live counters (from audit records)
GET  /api/audit?run&offset returns audit records appended since ``offset``
GET  /api/status?run       the real status.json (or null)
GET  /api/handoff?run      the real handoff.md text (or null)
GET  /api/gaps?run         the real gaps.md text (or null)
POST /api/start            start a run over a padded inbox (real CLI subprocess)
POST /api/kill?run=ID      create the REAL STOP file the run is polling
POST /api/scorecard        run the real 40-case harness (cached after first call)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
CONSOLE_DIR = Path(__file__).resolve().parent
OUT_BASE = REPO / "out" / "console"
FIXTURES = REPO / "fixtures" / "cases.json"
DEFAULT_DATE = "2026-11-28"
DEFAULT_PAD = int(os.environ.get("SBH_CONSOLE_PAD") or 9000)

_lock = threading.Lock()
_runs: dict[str, "Run"] = {}
_current: str | None = None
_scorecard_cache: dict | None = None


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]


class Tailer:
    """Byte-offset tail of one audit.jsonl: only new lines are parsed each poll."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.pos = 0
        self.buf = b""
        self.records: list[dict] = []

    def poll(self) -> list[dict]:
        try:
            if not self.path.exists():
                return self.records
            with open(self.path, "rb") as handle:
                handle.seek(self.pos)
                data = handle.read()
                self.pos = handle.tell()
        except OSError:
            return self.records
        if data:
            self.buf += data
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    self.records.append(json.loads(line))
                except Exception:
                    # A partially fsynced line is simply retried next poll.
                    self.buf = line + b"\n" + self.buf
                    break
        return self.records


class Run:
    def __init__(self, rid: str, inbox: Path, out_root: Path, stop_path: Path,
                 date: str, pad: int):
        self.id = rid
        self.inbox = inbox
        self.out_root = out_root
        self.stop_path = stop_path
        self.date = date
        self.pad = pad
        self.proc: subprocess.Popen | None = None
        self.tailer = Tailer(self.audit_path())
        self.started = datetime.now().isoformat(timespec="seconds")

    @property
    def shift_dir(self) -> Path:
        return self.out_root / self.date

    def audit_path(self) -> Path:
        return self.shift_dir / "audit.jsonl"

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def status(self) -> dict | None:
        path = self.shift_dir / "status.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def read_text(self, name: str) -> str | None:
        path = self.shift_dir / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    def log_tail(self, n: int = 40) -> str:
        path = self.out_root.parent / "run.log"
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])


def _stats(run: Run) -> dict:
    """Every counter, derived only from the real audit records."""
    st = {
        "pages_read": 0,
        "pages_total": 0,
        "patients": 0,
        "flagged": 0,
        "refused": 0,
        "facts": 0,
        "invented": 0,
        "verify_ok": None,
        "exit_reason": None,
        "stopped_by": None,
        "honoured_in": None,
        "model": None,
        "shift": None,
        "duration_s": None,
        "records": 0,
    }
    for rec in run.tailer.records:
        kind = rec.get("kind")
        if kind == "run_begin":
            st["model"] = rec.get("model")
            st["shift"] = rec.get("shift")
            st["pages_total"] = rec.get("page_count") or st["pages_total"]
        elif kind == "run_start":
            st["pages_total"] = rec.get("page_count") or 0
            st["model"] = rec.get("model") or st["model"]
            st["shift"] = rec.get("shift") or st["shift"]
        elif kind == "page":
            if rec.get("decision") == "read":
                st["pages_read"] += 1
            else:
                st["refused"] += 1
        elif kind == "patient":
            st["patients"] += 1
            if rec.get("refusals") or rec.get("ambiguities"):
                st["flagged"] += 1
        elif kind == "run_end":
            st["exit_reason"] = rec.get("exit_reason")
            st["stopped_by"] = rec.get("stopped_by")
            st["honoured_in"] = rec.get("honoured_in")
            st["verify_ok"] = rec.get("verify_ok")
            st["invented"] = len(rec.get("violations") or [])
            st["duration_s"] = rec.get("duration_s")
    st["records"] = len(run.tailer.records)
    handoff = run.read_text("handoff.md")
    if handoff:
        st["facts"] = handoff.count("[p. ")
    return st


def _meta(run: Run) -> dict:
    run.tailer.poll()
    stats = _stats(run)
    status = run.status() or {}
    return {
        "run": run.id,
        "date": run.date,
        "pad": run.pad,
        "inbox": str(run.inbox),
        "out_dir": str(run.out_root),
        "shift_dir": str(run.shift_dir),
        "audit_path": str(run.audit_path()),
        "stop_path": str(run.stop_path),
        "running": run.running(),
        "started": run.started,
        "stats": stats,
        "exit_reason": status.get("exit_reason") or stats.get("exit_reason"),
        "has_handoff": (run.shift_dir / "handoff.md").exists(),
    }


def start_run(pad: int | None = None) -> Run:
    global _current
    with _lock:
        rid = _stamp()
        base = OUT_BASE / rid
        inbox = base / "_inbox"
        out_root = base / "out"
        inbox.mkdir(parents=True, exist_ok=True)
        out_root.mkdir(parents=True, exist_ok=True)
        stop_path = base / "STOP"
        if stop_path.exists():
            stop_path.unlink()
        pad = int(pad or DEFAULT_PAD)
        pad = max(10, pad)

        # Render the real demo roster, then pad with neutral, identity-free
        # pages that are read for real but add no patients. This is the same
        # padding idea make_demo.sh uses for the kill-switch window.
        subprocess.run(
            [sys.executable, str(REPO / "tools" / "render_sheets.py"),
             "--cases", str(FIXTURES), "--out", str(inbox), "--date", DEFAULT_DATE],
            cwd=str(REPO), check=True, capture_output=True,
        )
        existing = len(list(inbox.glob("handoff_*.txt")))
        for i in range(existing + 1, pad + 1):
            (inbox / f"handoff_{DEFAULT_DATE}_{i:05d}.txt").write_text(
                f"Ward sheet {i}: handover folder checked; "
                "no patient identity on this line.\n",
                encoding="utf-8",
            )

        env = dict(os.environ)
        env["SBH_STOP_FILE"] = str(stop_path)
        env["PYTHONPATH"] = str(REPO)
        log = open(base / "run.log", "w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-m", "src.cli", "run",
             "--inbox", str(inbox), "--out", str(out_root), "--date", DEFAULT_DATE],
            cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        run = Run(rid, inbox, out_root, stop_path, DEFAULT_DATE, pad)
        run.proc = proc
        _runs[rid] = run
        _current = rid
        return run


def _resolve(rid: str | None) -> Run | None:
    if rid:
        return _runs.get(rid)
    return _runs.get(_current) if _current else None


def kill_run(rid: str | None) -> dict | None:
    with _lock:
        run = _resolve(rid)
        if run is None:
            return None
        run.stop_path.parent.mkdir(parents=True, exist_ok=True)
        # Same primitive the CLI uses: an empty STOP file the poll sees.
        run.stop_path.write_text("", encoding="utf-8")
        return {"stop_path": str(run.stop_path), "run": run.id,
                "killed_at": datetime.now().isoformat(timespec="milliseconds")}


def run_scorecard() -> dict:
    global _scorecard_cache
    with _lock:
        if _scorecard_cache is not None:
            return _scorecard_cache
        rid = _stamp()
        out = OUT_BASE / f"scorecard-{rid}"
        out.mkdir(parents=True, exist_ok=True)
    # Run the harness outside the lock so a live run's start/kill still answer.
    proc = subprocess.run(
        [sys.executable, "-m", "evals.run", "--cases", str(FIXTURES), "--out", str(out)],
        cwd=str(REPO), capture_output=True, text=True, timeout=600,
    )
    try:
        results = json.loads((out / "results.json").read_text(encoding="utf-8"))
        n = results.get("scorecard") or {}
    except Exception as exc:  # pragma: no cover - only on a broken harness
        return {"error": f"{type(exc).__name__}: {exc}", "stdout": proc.stdout[-2000:]}
    summary = {
        "cases": n.get("cases"),
        "passed": n.get("passed"),
        "failed": n.get("failed"),
        "hallucinations": 0 if n.get("failed") == 0 else None,
        "contradictions": f"{n.get('cases_with_contradictions_found')}/{n.get('cases_with_contradictions_expected')}",
        "injections": f"{n.get('cases_with_injections_logged')}/{n.get('cases_with_injections_expected')}",
        "refusals": f"{n.get('total_refusals')} across {n.get('cases_with_refusals')} cases",
        "timed_out": n.get("timed_out"),
        "run_dir": str(out),
    }
    honoured = None
    with _lock:
        cur = _runs.get(_current) if _current else None
    if cur:
        honoured = (cur.status() or {}).get("honoured_in")
    summary["honoured_in"] = honoured
    with _lock:
        _scorecard_cache = summary
    return summary


class Handler(BaseHTTPRequestHandler):
    server_version = "ShiftBuddyConsole/1"

    def log_message(self, *args):  # quiet the access log
        pass

    # ------------------------------------------------------------------ helpers
    def _send(self, obj, status: int = 200, ctype: str = "application/json"):
        data = obj if isinstance(obj, bytes) else json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, name: str, ctype: str):
        path = CONSOLE_DIR / name
        if not path.exists():
            return self._send({"error": f"missing {name}"}, 404)
        self._send(path.read_bytes(), 200, ctype)

    def _query(self):
        parsed = urlparse(self.path)
        return parsed.path, {k: v[-1] for k, v in parse_qs(parsed.query).items()}

    # ---------------------------------------------------------------------- GET
    def do_GET(self):
        path, q = self._query()
        if path in ("/", "/index.html"):
            return self._file("page.html", "text/html; charset=utf-8")
        if path == "/console.css":
            return self._file("console.css", "text/css; charset=utf-8")
        if path == "/healthz":
            return self._send({"ok": True, "mode": "hosted-demo", "data": "synthetic-only"})
        if path == "/api/meta":
            run = _resolve(q.get("run"))
            if run is None:
                return self._send({"run": None})
            return self._send(_meta(run))
        if path == "/api/audit":
            run = _resolve(q.get("run"))
            if run is None:
                return self._send({"offset": 0, "total": 0, "records": [], "stats": {}})
            run.tailer.poll()
            try:
                offset = max(0, int(q.get("offset") or 0))
            except ValueError:
                offset = 0
            recs = run.tailer.records
            new = recs[offset:]
            return self._send({
                "run": run.id,
                "offset": len(recs),
                "total": len(recs),
                "records": new,
                "stats": _stats(run),
                "running": run.running(),
            })
        if path == "/api/status":
            run = _resolve(q.get("run"))
            return self._send(run.status() if run else None)
        if path == "/api/handoff":
            run = _resolve(q.get("run"))
            return self._send({"run": run.id if run else None,
                               "text": run.read_text("handoff.md") if run else None})
        if path == "/api/gaps":
            run = _resolve(q.get("run"))
            return self._send({"run": run.id if run else None,
                               "text": run.read_text("gaps.md") if run else None})
        if path == "/api/log":
            run = _resolve(q.get("run"))
            return self._send({"log": run.log_tail() if run else ""})
        if path == "/api/scorecard":
            return self._send(run_scorecard())
        return self._send({"error": "not found", "path": path}, 404)

    # --------------------------------------------------------------------- POST
    def do_POST(self):
        path, q = self._query()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        payload: dict = {}
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
        if path == "/api/start":
            try:
                run = start_run(payload.get("pad"))
            except Exception as exc:
                return self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)
            return self._send(_meta(run))
        if path == "/api/kill":
            info = kill_run(q.get("run") or payload.get("run"))
            if info is None:
                return self._send({"error": "no run"}, 404)
            return self._send(info)
        if path == "/api/scorecard":
            return self._send(run_scorecard())
        return self._send({"error": "not found", "path": path}, 404)


def serve(host: str = "127.0.0.1", port: int = 8777) -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Shift Buddy console on http://{host}:{port}/  (pad={DEFAULT_PAD})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
