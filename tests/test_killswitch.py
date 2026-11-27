"""Kill switch: STOP file and SIGTERM are honoured quickly, cleanly, and audited.

Three layers are exercised, all real code:

* ``src.killswitch.KillSwitch`` -- the latch and its measured latency.
* ``src.ingest.ingest(stop=...)`` -- proves the page in flight finishes whole and
  the remainder is *named* as unprocessed rather than silently dropped.
* ``src.cli`` as a subprocess -- exit code, audit record, and a complete set of
  output artifacts with no half-written file left behind.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

from tests import _support as support

BUDGET_S = 2.0
PAGE_FIELDS = {
    "page",
    "path",
    "sha256",
    "order",
    "kind",
    "text",
    "exif_time",
    "readable",
    "refusal_reason",
    "ocr_confidence",
    "unusual",
}


def _page_text(index: int) -> str:
    return (
        f"BED {index} MRN 00-7{index:03d} 'Patient {index} X.' — problem {index}.\n"
        f"ACTION: review {index}.\n"
    )


def _wait_for_dir(path: Path, proc, timeout: float = 25.0) -> None:
    """Block until ``path`` exists, failing loudly if the child exits first."""
    deadline = time.monotonic() + timeout
    while not path.exists():
        if proc.poll() is not None:
            raise AssertionError(f"run finished (exit {proc.returncode}) before {path.name}/ appeared")
        if time.monotonic() > deadline:
            raise AssertionError(f"{path} never appeared")
        time.sleep(0.01)


class KillSwitchLatencyTests(unittest.TestCase):
    def test_stop_file_in_temp_cwd_detected_under_budget(self):
        from src.killswitch import KillSwitch

        with support.workspace() as tmp:
            previous = Path.cwd()
            os.chdir(tmp)
            try:
                ks = KillSwitch()
                self.assertEqual("./STOP", ks.stop_path)
                self.assertFalse(ks.check(), "tripped before STOP existed")
                (tmp / "STOP").write_text("", encoding="utf-8")
                started = time.monotonic()
                tripped = ks.check()
                elapsed = time.monotonic() - started
            finally:
                os.chdir(previous)
                ks.restore()

        self.assertTrue(tripped, "STOP file was not detected")
        self.assertLess(elapsed, BUDGET_S, f"detection took {elapsed:.3f}s")
        self.assertEqual("STOP", ks.stopped_by)
        self.assertIsInstance(ks.honoured_in, float)
        self.assertLess(ks.honoured_in, BUDGET_S)
        self.assertEqual("STOP", ks.audit_fields()["stopped_by"])

    def test_explicit_stop_path_and_single_latch(self):
        from src.killswitch import KillSwitch

        with support.workspace() as tmp:
            stop_path = tmp / "STOP"
            ks = KillSwitch(str(stop_path))
            try:
                stop_path.write_text("", encoding="utf-8")
                self.assertTrue(ks.check())
                first = ks.honoured_in
                self.assertFalse(ks.check(), "check() must latch exactly once")
                self.assertEqual(first, ks.honoured_in)
                self.assertTrue(ks.armed())
            finally:
                ks.restore()

    def test_no_stop_file_is_not_armed(self):
        from src.killswitch import KillSwitch

        with support.workspace() as tmp:
            ks = KillSwitch(str(tmp / "STOP"))
            try:
                self.assertFalse(ks.check())
                self.assertIsNone(ks.stopped_by)
                self.assertIsNone(ks.honoured_in)
            finally:
                ks.restore()

    def test_trip_creates_the_stop_file(self):
        from src.killswitch import KillSwitch, trip

        with support.workspace() as tmp:
            ks = None
            path = trip(str(tmp / "STOP"))
            try:
                self.assertTrue(Path(path).exists())
                ks = KillSwitch(path)
                self.assertTrue(ks.check())
                self.assertEqual("STOP", ks.stopped_by)
            finally:
                if ks is not None:
                    ks.restore()


class IngestAtomicityTests(unittest.TestCase):
    """The page in flight completes; the rest is named, not silently dropped."""

    def test_pages_before_stop_are_complete_and_rest_are_named(self):
        from src.ingest import ingest

        with support.workspace() as inbox:
            for index in range(1, 7):
                (inbox / f"handoff_2026-11-27_{index:02d}.txt").write_text(
                    _page_text(index), encoding="utf-8"
                )

            calls = {"n": 0}

            def stop():
                calls["n"] += 1
                return calls["n"] >= 3

            doc = ingest(str(inbox), stop=stop)

        self.assertTrue(doc.get("stopped"), "ingest did not report the stop")
        pages = doc["pages"]
        self.assertEqual([1, 2], [p["page"] for p in pages])

        for page in pages:
            self.assertEqual(
                PAGE_FIELDS, set(page), "the finished page record is missing fields"
            )
            self.assertIsNotNone(page["sha256"], "finished page has no hash")
            self.assertTrue(page["readable"])
            self.assertTrue(page["text"].strip(), "finished page has no text")

        self.assertEqual(
            [f"handoff_2026-11-27_{i:02d}.txt" for i in (3, 4, 5, 6)],
            doc["unprocessed_files"],
            "unprocessed pages were not named",
        )
        self.assertEqual(3, calls["n"], "stop was not polled once per page")


class CliStopTests(unittest.TestCase):
    def test_stop_present_before_run(self):
        """STOP already on disk: nothing is processed, exit 0, audited."""
        with support.workspace() as tmp:
            support.write_inbox(tmp / "inbox", [_page_text(1)])
            (tmp / "STOP").write_text("", encoding="utf-8")
            proc = support.run_cli(
                ["run", "--inbox", str(tmp / "inbox"), "--out", str(tmp / "out"),
                 "--date", "2026-11-27"],
                cwd=tmp,
                SBH_STOP_FILE=str(tmp / "STOP"),
            )
            result = support.collect_outputs(
                tmp / "out", proc.returncode, proc.stdout, proc.stderr
            )

        self.assertEqual(0, proc.returncode, f"stop must exit 0: {proc.stderr}")
        self.assertFalse(result.handoff_written, "handoff written after a stop")
        self.assertEqual("stopped", (result.status or {}).get("state"))
        run_end = result.run_end()
        self.assertIsNotNone(run_end, "no run_end record after a stop")
        self.assertEqual("stopped", run_end["exit_reason"])
        self.assertEqual("STOP", run_end["stopped_by"])
        self.assertIsInstance(run_end["honoured_in"], float)
        self.assertLess(run_end["honoured_in"], BUDGET_S)

    def test_stop_arriving_mid_run_leaves_only_whole_artifacts(self):
        with support.workspace() as tmp:
            inbox, out, stop_path = tmp / "inbox", tmp / "out", tmp / "STOP"
            support.write_inbox(inbox, [_page_text(i) for i in range(1, 401)])
            proc = subprocess.Popen(
                [sys.executable, "-m", "src.cli", "run", "--inbox", str(inbox),
                 "--out", str(out), "--date", "2026-11-27"],
                cwd=str(tmp),
                env=support.cli_env(SBH_STOP_FILE=str(stop_path)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                _wait_for_dir(out, proc)
                stop_path.write_text("", encoding="utf-8")
                stdout, stderr = proc.communicate(timeout=30)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
            result = support.collect_outputs(out, proc.returncode, stdout, stderr)

        self.assertEqual(0, proc.returncode, f"stop must exit 0: {stderr}")
        self.assertIsNotNone(result.summary, "summary.json is missing or unparsable")
        self.assertIsNotNone(result.status, "status.json is missing or unparsable")
        self.assertIn("gaps.md", result.files)
        self.assertFalse([f for f in result.files if f.endswith(".tmp")], result.files)
        self.assertTrue(result.audit, "audit.jsonl is empty")
        for path in result.shift.glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(result.handoff_written, "handoff written after a mid-run stop")
        self.assertEqual("stopped", (result.status or {}).get("state"))
        run_end = result.run_end()
        self.assertIsNotNone(run_end)
        self.assertEqual("stopped", run_end["exit_reason"])
        self.assertEqual("STOP", run_end["stopped_by"])
        self.assertLess(run_end["honoured_in"], BUDGET_S)


class SigtermTests(unittest.TestCase):
    def test_sigterm_exits_cleanly_and_audits(self):
        with support.workspace() as tmp:
            inbox, out = tmp / "inbox", tmp / "out"
            support.write_inbox(inbox, [_page_text(i) for i in range(1, 801)])
            proc = subprocess.Popen(
                [sys.executable, "-m", "src.cli", "run", "--inbox", str(inbox),
                 "--out", str(out), "--date", "2026-11-27"],
                cwd=str(tmp),
                env=support.cli_env(SBH_STOP_FILE=str(tmp / "STOP")),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                _wait_for_dir(out, proc)
                sent_at = time.monotonic()
                proc.send_signal(signal.SIGTERM)
                stdout, stderr = proc.communicate(timeout=30)
                elapsed = time.monotonic() - sent_at
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
            result = support.collect_outputs(out, proc.returncode, stdout, stderr)

        self.assertEqual(0, proc.returncode, f"SIGTERM must exit 0: {stderr}")
        self.assertLess(elapsed, 10.0, f"shutdown took {elapsed:.2f}s")
        self.assertFalse(result.handoff_written, "handoff written after SIGTERM")
        run_end = result.run_end()
        self.assertIsNotNone(run_end, "no run_end record after SIGTERM")
        self.assertEqual("stopped", run_end["exit_reason"])
        self.assertEqual("SIGTERM", run_end["stopped_by"])
        self.assertIsInstance(run_end["honoured_in"], float)
        self.assertLess(run_end["honoured_in"], BUDGET_S)
        self.assertEqual("stopped", (result.status or {}).get("state"))
        self.assertFalse([f for f in result.files if f.endswith(".tmp")], result.files)


if __name__ == "__main__":
    unittest.main()
