"""Verifier poison: a token in prose that is not a fact must fail the run.

Every assertion here goes through the real ``src.verify.verify`` and the real
``src.cli._run_once`` assembly.  The poisoned composition is injected by
replacing ``src.compose.compose`` for the duration of one run, which is exactly
the boundary ``src.cli`` resolves at call time -- so the guard under test is the
real one, not a stand-in.
"""

from __future__ import annotations

import unittest
from unittest import mock

from tests import _support as support

FACTS = {
    "run_id": "2026-11-27T20:00:00+05:00",
    "shift": {"date": "2026-11-27", "ward": "RO", "handover_to": "night"},
    "patients": [
        {
            "id": "B12",
            "bed": "12",
            "mrn": "00-4417",
            "name_as_written": "Ayesha K.",
            "problem": "CAP",
            "allergy": None,
            "covering": None,
            "issues": [],
            "pages": [1],
            "meds": [
                {"name": "ceftriaxone", "dose": "1g", "freq": "OD", "day": 3, "of": 7, "page": 1}
            ],
            "actions": [
                {
                    "text": "repeat CXR tomorrow AM",
                    "when_raw": "tomorrow AM",
                    "due": "2026-11-28T06:00:00+05:00",
                    "page": 1,
                }
            ],
            "refused_fields": [],
            "ambiguities": [],
        }
    ],
    "unreadable_pages": [],
    "contradictions": [],
    "injections": [],
}

CLEAN_PROSE = (
    "## Bed 12 — Ayesha K. [p. 1]\n"
    "S: Bed 12, Ayesha K.; CAP [p. 1]\n"
    "B: Med: ceftriaxone 1g OD day 3 of 7 [p. 1]\n"
    "A: CAP — as written on the page [p. 1]\n"
    "R: repeat CXR tomorrow AM — due 2026-11-28T06:00:00+05:00 [p. 1]\n"
)

# kind -> (poisoned prose appended to the clean handoff, token that must be named)
POISON = {
    "dose": ("B: Med: haloperidol 50mg IV given at handover [p. 1]\n", "50mg"),
    "number": ("B: Urine output 3750 recorded overnight [p. 1]\n", "3750"),
    "bed": ("S: Patient moved to Bed 99 before handover [p. 1]\n", "99"),
    "time": ("R: repeat CXR at 12:45 [p. 1]\n", "12:45"),
    "identifier": ("S: MRN 99-1234 confirmed at bedside [p. 1]\n", "99-1234"),
}


class VerifyUnitTests(unittest.TestCase):
    def test_clean_prose_passes(self):
        from src.verify import verify

        ok, violations = verify(CLEAN_PROSE, FACTS)
        self.assertTrue(ok, f"clean prose rejected: {violations}")
        self.assertEqual([], violations)

    def test_each_poison_token_fails_and_is_named(self):
        from src.verify import verify

        for kind, (snippet, token) in POISON.items():
            with self.subTest(kind=kind):
                ok, violations = verify(CLEAN_PROSE + snippet, FACTS)
                self.assertFalse(ok, f"{kind} poison was accepted: {snippet!r}")
                self.assertTrue(violations, "a failing verify must explain itself")
                blob = " | ".join(violations).lower()
                self.assertIn(
                    token.lower(),
                    blob,
                    f"{kind} violation did not name {token!r}: {violations}",
                )

    def test_check_kind_is_named_too(self):
        from src.verify import verify

        _, violations = verify(CLEAN_PROSE + POISON["dose"][0], FACTS)
        self.assertIn("dose", violations[0].lower(), violations)


class CliVerifyGateTests(unittest.TestCase):
    """The CLI path must refuse to write handoff.md when verify fails."""

    def _case(self):
        return support.make_case(
            [
                support.text_page(
                    "BED 12 — MRN 00-4417 — 'Ayesha K.' (name altered)\n"
                    "Admitted 26/11, CAP. On ceftriaxone 1g OD day 3 of 7.\n"
                    "ACTION: repeat CXR tomorrow AM.\n"
                )
            ]
        )

    def test_clean_composition_writes_handoff(self):
        with support.workspace() as tmp:
            result = support.run_pipeline(self._case(), tmp)
            self.assertEqual(0, result.rc, result.stderr)
            self.assertIn("handoff.md", result.files)
            ok, violations = support.verify_handoff(result)
            self.assertTrue(ok, f"shipped handoff fails its own verifier: {violations}")

    def test_poisoned_composition_withholds_handoff_and_exits_nonzero(self):
        from src import compose as compose_module

        real_compose = compose_module.compose

        def poisoned(patients, contradictions, shift):
            text, allowed = real_compose(patients, contradictions, shift)
            return text + POISON["dose"][0], allowed

        with support.workspace() as tmp, mock.patch.object(
            compose_module, "compose", poisoned
        ):
            result = support.run_pipeline(self._case(), tmp)

        self.assertEqual(1, result.rc, "a verify failure must exit non-zero")
        self.assertFalse(
            result.handoff_written, "handoff.md was written despite a verify failure"
        )
        self.assertNotIn("handoff.md", result.files)
        self.assertIn("gaps.md", result.files, "the gap list must survive a failed run")

    def test_audit_and_status_name_the_violation(self):
        from src import compose as compose_module

        real_compose = compose_module.compose

        def poisoned(patients, contradictions, shift):
            text, allowed = real_compose(patients, contradictions, shift)
            return text + "S: MRN 99-1234 confirmed at bedside [p. 1]\n", allowed

        with support.workspace() as tmp, mock.patch.object(
            compose_module, "compose", poisoned
        ):
            result = support.run_pipeline(self._case(), tmp)

        self.assertEqual(1, result.rc)
        run_end = result.run_end()
        self.assertIsNotNone(run_end, "no run_end record after a verify failure")
        self.assertEqual("verify_failed", run_end["exit_reason"])
        self.assertFalse(run_end["verify_ok"])
        joined = " | ".join(run_end["violations"]).lower()
        self.assertIn("99-1234", joined, f"violation not named in audit: {run_end['violations']}")

        status = result.status or {}
        self.assertEqual("verify_failed", status.get("state"))
        self.assertFalse(status["verify"]["ok"])


if __name__ == "__main__":
    unittest.main()
