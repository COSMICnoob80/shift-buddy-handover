"""Every refusal is named: the gap list must say what could not be read.

Scope: every fixture case whose ``expected`` block declares a refusal (or zero
patients, which is the all-pages-unreadable case).  For each, this module proves
three things about the real pipeline:

1. every refusal reason the code recorded is quoted in ``gaps.md``;
2. the page it happened on is identified in ``gaps.md``;
3. ``handoff.md`` invents nothing for the refused page -- refusal markers never
   leak into it, and the shipped handoff still passes its own verifier.

Two assertions originally failed against the committed code and were kept,
unweakened, as ``expectedFailure`` with the defect named in the docstring.  Both
defects are now fixed in ``src/`` and the markers are gone; the tests stay as the
regression lock and name the fix in their docstrings.
"""

from __future__ import annotations

import re
import unittest

from tests import _support as support

REFUSAL_MARKER = re.compile(r"\[[^\]\n]*\b(?:illegible|unreadable)\b[^\]\n]*\]", re.I)


def _refusal_cases() -> list:
    """Cases whose expected behaviour includes a refusal."""
    wanted = []
    for case in support.load_cases():
        expected = case.get("expected") or {}
        if expected.get("refusals", 0) > 0 or expected.get("patients", 1) == 0:
            wanted.append(case)
    return wanted


class RefusalNamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = support.workspace()
        cls.root = cls._tmp.__enter__()
        cls.results = {}
        for case in _refusal_cases():
            cls.results[case["id"]] = support.run_pipeline(case, cls.root / case["id"])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def test_cases_were_found(self):
        self.assertGreaterEqual(
            len(self.results), 8, f"expected the refusal family, found {sorted(self.results)}"
        )

    def test_every_run_completed(self):
        for case_id, result in self.results.items():
            with self.subTest(case=case_id):
                self.assertEqual(0, result.rc, f"{case_id}: {result.stderr}")
                self.assertTrue(result.gaps, f"{case_id}: no gaps.md")

    def test_every_recorded_refusal_reason_is_quoted_in_gaps(self):
        for case_id, result in self.results.items():
            for reason in result.refused_fields():
                with self.subTest(case=case_id, reason=reason):
                    self.assertIn(
                        reason,
                        result.gaps,
                        f"{case_id}: refusal recorded but not named in gaps.md",
                    )

    def test_every_unreadable_page_number_is_named(self):
        for case_id, result in self.results.items():
            unreadable = (result.summary or {}).get("unreadable_pages") or []
            for page in unreadable:
                with self.subTest(case=case_id, page=page):
                    self.assertIn(
                        f"page {page}",
                        result.gaps.lower(),
                        f"{case_id}: unreadable page {page} not named in gaps.md",
                    )

    def test_refusal_count_matches_the_spec(self):
        """EVALS §9: refusals = unreadable pages + per-patient refused fields."""
        for case_id, result in self.results.items():
            summary = result.summary or {}
            counted = len(summary.get("unreadable_pages") or []) + len(result.refused_fields())
            expected = next(
                c["expected"]["refusals"] for c in _refusal_cases() if c["id"] == case_id
            )
            with self.subTest(case=case_id):
                self.assertEqual(expected, counted, f"{case_id}: refusal count drift")

    def test_recorded_reason_for_an_unreadable_page_survives_into_gaps(self):
        """FIXED (src): the reason ingest records now reaches gaps.md.

        ``src.ingest`` stores a precise reason per unreadable page (for a
        zero-byte page: "page file is empty (0 bytes)") and ``audit.run_start``
        preserves it in ``refusal_reason``.  ``src.cli._unreadable_details``
        carries that reason through to ``compose_gaps``, which prints
        "- page N: <reason>", so the gap list names the page *and why* it could
        not be read (EVALS.md §3.2).
        """
        checked = 0
        for case_id, result in self.results.items():
            inputs = (result.run_start() or {}).get("inputs") or []
            for item in inputs:
                reason = item.get("refusal_reason")
                if item.get("readable") is not False or not reason:
                    continue
                checked += 1
                with self.subTest(case=case_id, page=item.get("page"), reason=reason):
                    self.assertIn(
                        reason,
                        result.gaps,
                        f"{case_id}: page {item.get('page')} reason {reason!r} "
                        "did not survive into gaps.md",
                    )
        self.assertGreater(checked, 0, "no unreadable page carried a reason to check")


class RefusalInventionTests(unittest.TestCase):
    """A refused value must never be invented into the handoff."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = support.workspace()
        cls.root = cls._tmp.__enter__()
        cls.results = {}
        for case in _refusal_cases():
            result = support.run_pipeline(case, cls.root / case["id"])
            if result.handoff is not None:
                cls.results[case["id"]] = result

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def test_no_refusal_marker_leaks_into_the_handoff(self):
        for case_id, result in self.results.items():
            leaked = REFUSAL_MARKER.findall(result.handoff)
            with self.subTest(case=case_id):
                self.assertEqual(
                    [], leaked, f"{case_id}: refusal marker rendered as content: {leaked}"
                )

    def test_shipped_handoff_passes_its_own_verifier(self):
        for case_id, result in self.results.items():
            ok, violations = support.verify_handoff(result)
            with self.subTest(case=case_id):
                self.assertTrue(ok, f"{case_id}: handoff not traceable to facts: {violations}")

    def test_bed_and_mrn_are_never_fabricated_for_a_refused_patient(self):
        for case_id, result in self.results.items():
            for patient in (result.summary or {}).get("patients") or []:
                if patient.get("bed") is not None:
                    with self.subTest(case=case_id, patient=patient.get("id")):
                        self.assertIn(f"Bed {patient['bed']}", result.handoff)

    def test_a_refused_name_is_not_rendered_as_the_string_none(self):
        """FIXED (src): a refused name renders as an explicit refusal marker.

        C-016's page says "name illegible on this sheet".  ``src.compose`` now
        builds the heading through ``_heading_name``, which renders
        "name not readable" when ``name_as_written`` is absent (and the action
        roll-up omits the name), so the literal ``None`` never reaches the
        clinician-facing document and nothing is invented in its place.
        """
        offenders = {}
        for case_id, result in self.results.items():
            lines = [ln for ln in result.handoff.splitlines() if re.search(r"\bNone\b", ln)]
            if lines:
                offenders[case_id] = lines
        self.assertEqual(
            {}, offenders, f"handoff renders a refused field as 'None': {offenders}"
        )


if __name__ == "__main__":
    unittest.main()
