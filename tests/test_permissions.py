"""Permissions, enforced in code: writes stay inside out/, and nothing egresses.

Two PERMISSIONS.md rows are demonstrated here:

* row 5 -- a write anywhere other than ``out/`` is denied by
  :meth:`src.audit.Audit.safe_write` (a real ``AuditPathRefused``), while a write
  inside ``out/`` succeeds and lands atomically.
* row 6 -- no network call happens on a normal run.  The honest form is used:
  ``socket.socket.connect`` is patched to raise, a full pipeline runs over a real
  fixture case, and it must still succeed without the patch ever firing.

The refusal cases are tried three ways -- absolute escape, ``..`` traversal, and
an audit directory anchored outside the root -- because the guard resolves paths
before comparing them, so a naive string check would miss two of the three.
"""

from __future__ import annotations

import ast
import socket
import unittest
from pathlib import Path
from unittest import mock

from tests import _support as support

FORBIDDEN_CLIENT_MODULES = {"socket", "requests", "urllib", "urllib3", "httpx", "http", "aiohttp"}


class WriteGuardTests(unittest.TestCase):
    def _audit(self, tmp):
        from src.audit import Audit

        out_root = tmp / "out"
        out_root.mkdir(parents=True, exist_ok=True)
        return Audit(str(out_root / "2026-11-27"), root=str(out_root)), out_root

    def test_write_outside_out_is_refused(self):
        from src.audit import AuditPathRefused

        with support.workspace() as tmp:
            audit, out_root = self._audit(tmp)
            try:
                target = tmp / "escaped.md"
                with self.assertRaises(AuditPathRefused) as caught:
                    audit.safe_write(target, "patient data")
                self.assertFalse(target.exists(), "refused write still created the file")
                self.assertIn(str(out_root), str(caught.exception))
            finally:
                audit.close()

    def test_dotdot_traversal_is_refused(self):
        from src.audit import AuditPathRefused

        with support.workspace() as tmp:
            audit, _ = self._audit(tmp)
            try:
                target = tmp / "out" / "2026-11-27" / ".." / ".." / "escaped.md"
                with self.assertRaises(AuditPathRefused):
                    audit.safe_write(target, "patient data")
                self.assertFalse((tmp / "escaped.md").exists())
            finally:
                audit.close()

    def test_audit_directory_anchored_outside_root_is_refused(self):
        from src.audit import Audit, AuditPathRefused

        with support.workspace() as tmp:
            out_root = tmp / "out"
            out_root.mkdir()
            with self.assertRaises(AuditPathRefused):
                Audit(str(tmp / "elsewhere"), root=str(out_root))

    def test_write_inside_out_succeeds_and_is_whole(self):
        with support.workspace() as tmp:
            audit, out_root = self._audit(tmp)
            try:
                target = out_root / "2026-11-27" / "handoff.md"
                written = audit.safe_write(target, "# Handoff\n")
                self.assertEqual(target.resolve(), written)
                self.assertEqual("# Handoff\n", target.read_text(encoding="utf-8"))
                leftovers = [p.name for p in target.parent.iterdir() if p.suffix == ".tmp"]
                self.assertFalse(leftovers, f"temp files left behind: {leftovers}")
            finally:
                audit.close()

    def test_create_directories_under_out_is_allowed(self):
        with support.workspace() as tmp:
            audit, out_root = self._audit(tmp)
            try:
                nested = out_root / "2026-11-27" / "sections" / "sbar.md"
                audit.safe_write(nested, "S: ...\n")
                self.assertTrue(nested.exists())
            finally:
                audit.close()


class NoEgressTests(unittest.TestCase):
    def test_full_pipeline_runs_with_connect_poisoned(self):
        """Patch the socket layer to raise; a whole run must still complete."""
        case = support.cases_by_id()["C-001"]
        attempts = []

        def deny(*args, **kwargs):
            attempts.append(args)
            raise AssertionError("network connect attempted during a local run")

        with support.workspace() as tmp, mock.patch.object(
            socket.socket, "connect", deny
        ), mock.patch.object(socket.socket, "connect_ex", deny), mock.patch.object(
            socket, "create_connection", deny
        ):
            result = support.run_pipeline(case, tmp)

        self.assertEqual([], attempts, f"the run tried to open a socket: {attempts}")
        self.assertEqual(0, result.rc, result.stderr)
        self.assertIn("handoff.md", result.files, "a clean case must still ship its handoff")
        ok, violations = support.verify_handoff(result)
        self.assertTrue(ok, f"handoff failed its own verifier: {violations}")

    def test_refused_egress_attempt_would_be_loud(self):
        """Guard the guard: the patch really does intercept a connect()."""
        with mock.patch.object(socket.socket, "connect", side_effect=AssertionError("denied")):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(AssertionError):
                    sock.connect(("127.0.0.1", 9))
            finally:
                sock.close()

    def test_source_imports_no_network_client(self):
        """Static counterpart to the runtime probe: no client library is imported."""
        offenders = []
        for path in sorted(support.REPO_ROOT.glob("src/*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module.split(".")[0]]
                for name in names:
                    if name in FORBIDDEN_CLIENT_MODULES:
                        offenders.append(f"{path.name}: {name}")
        self.assertEqual([], offenders, f"network client imports found: {offenders}")

    def test_run_writes_nothing_outside_out(self):
        case = support.cases_by_id()["C-003"]
        with support.workspace() as tmp:
            # Materialise the input first so the snapshot only sees pipeline writes.
            support.build_case_inbox(case, tmp / "inbox")
            before = {p for p in tmp.rglob("*") if p.is_file()}
            result = support.run_pipeline(case, tmp)
            after = {p for p in tmp.rglob("*") if p.is_file()}

        self.assertEqual(0, result.rc, result.stderr)
        out_root = (result.out).resolve()
        strays = [
            str(path.relative_to(tmp))
            for path in after - before
            if out_root not in path.resolve().parents and path.resolve() != out_root
        ]
        self.assertEqual([], strays, f"files written outside out/: {strays}")


if __name__ == "__main__":
    unittest.main()
