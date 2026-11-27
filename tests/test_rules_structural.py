"""Regression lock for commit c7f91b1: missing fields are structural, not cued.

Before that commit ``src.rules._missing_for`` only flagged ``allergy`` and
``covering_clinician`` when the page *said* the field was absent ("no allergy
field recorded...").  A page that simply never mentioned an allergy produced no
gap, so a clinician could read a handoff that looked complete when a mandatory
field had never been assessed.

Each test below drives the real ``extract -> structure -> rules.apply`` chain, so
a regression anywhere along that path is caught, not just one inside ``rules``.
"""

from __future__ import annotations

import unittest

from tests import _support as support

# No allergy line, no covering line, and no prose acknowledging either.
NO_CUE_TEXT = (
    "BED 70 MRN 00-9001 'Ali R.' — community-acquired pneumonia day 2.\n"
    "Ceftriaxone 1g OD day 2 of 5.\n"
    "ACTION: repeat CXR AM.\n"
)

# Same absence, but the page explicitly says so.  Must behave identically.
CUED_TEXT = (
    "BED 72 MRN 00-9002 'Sara K.' — community-acquired pneumonia day 2.\n"
    "No allergy field recorded on this sheet.\n"
    "No covering clinician named.\n"
    "ACTION: repeat CXR AM.\n"
)

# Both mandatory fields carry a real value.
VALUES_TEXT = (
    "BED 71 MRN 00-9003 'Nadia Q.' — community-acquired pneumonia day 2.\n"
    "Allergy: PENICILLIN (rash).\n"
    "Covering clinician: Dr Hamid.\n"
    "ACTION: repeat CXR AM.\n"
)


def _stage(text: str, page: int = 1):
    """Run the real extract -> structure -> rules chain over one page."""
    from src.extract import extract
    from src.rules import apply
    from src.structure import structure

    pages_doc = {
        "run_id": "2026-11-27T20:00:00+05:00",
        "shift_date": "2026-11-27",
        "pages": [
            {
                "page": page,
                "path": f"handoff_2026-11-27_{page:02d}.txt",
                "sha256": "0" * 64,
                "order": page,
                "kind": "text",
                "text": text,
                "exif_time": None,
                "readable": True,
                "refusal_reason": None,
                "ocr_confidence": None,
                "unusual": [],
            }
        ],
    }
    fields_doc = extract(pages_doc)
    struct_doc = structure(fields_doc, run_start="2026-11-27T20:00:00+05:00")
    rules_doc = apply(struct_doc["patients"], struct_doc["injections"])
    return struct_doc["patients"], rules_doc


class StructuralMissingFieldTests(unittest.TestCase):
    def test_absent_fields_flagged_without_any_prose_cue(self):
        patients, rules = _stage(NO_CUE_TEXT)
        self.assertEqual(1, len(patients))
        patient = patients[0]
        self.assertIsNone(patient["allergy"], "fixture precondition: no allergy line")
        self.assertIsNone(patient["covering"], "fixture precondition: no covering line")

        absent = rules["missing"][patient["id"]]
        self.assertIn("allergy", absent, "allergy was not flagged without a cue")
        self.assertIn(
            "covering_clinician", absent, "covering_clinician was not flagged without a cue"
        )

    def test_cue_text_and_silent_text_are_treated_identically(self):
        _, silent = _stage(NO_CUE_TEXT)
        _, cued = _stage(CUED_TEXT)
        silent_absent = set(next(iter(silent["missing"].values())))
        cued_absent = set(next(iter(cued["missing"].values())))
        self.assertEqual(
            cued_absent, silent_absent, "absence was judged from prose rather than structure"
        )

    def test_present_values_flag_neither_field(self):
        patients, rules = _stage(VALUES_TEXT)
        patient = patients[0]
        self.assertEqual("PENICILLIN (rash)", patient["allergy"])
        self.assertEqual("Dr Hamid", patient["covering"])
        self.assertEqual({}, rules["missing"], "a fully-specified patient was flagged")
        self.assertEqual([], rules["gaps"], "gaps emitted for a fully-specified patient")

    def test_each_field_is_judged_on_its_own(self):
        allergy_only = (
            "BED 73 MRN 00-9004 'Tariq L.' — CAP.\nAllergy: NKDA.\nACTION: repeat CXR AM.\n"
        )
        covering_only = (
            "BED 74 MRN 00-9005 'Zoya M.' — CAP.\nCovering: Dr Farid.\nACTION: repeat CXR AM.\n"
        )
        _, with_allergy = _stage(allergy_only)
        _, with_covering = _stage(covering_only)

        self.assertNotIn("allergy", next(iter(with_allergy["missing"].values())))
        self.assertIn("covering_clinician", next(iter(with_allergy["missing"].values())))
        self.assertIn("allergy", next(iter(with_covering["missing"].values())))
        self.assertNotIn("covering_clinician", next(iter(with_covering["missing"].values())))

    def test_a_refused_value_still_counts_as_absent(self):
        """'allergy: [illegible]' is not a documented allergy; it must stay a gap."""
        text = (
            "BED 75 MRN 00-9006 'Bilal N.' — CAP.\n"
            "Allergy: [illegible]\n"
            "ACTION: repeat CXR AM.\n"
        )
        patients, rules = _stage(text)
        self.assertIsNone(patients[0]["allergy"], "refusal marker was stored as a value")
        absent = rules["missing"][patients[0]["id"]]
        self.assertIn("allergy", absent, "a refused allergy silenced the gap")

    def test_flag_reaches_gaps_and_issues(self):
        patients, rules = _stage(NO_CUE_TEXT)
        patient = patients[0]
        messages = " ".join(rules["gaps"]).lower()
        self.assertIn("allergy status not recorded", messages)
        self.assertIn("covering clinician not named", messages)
        issues = " ".join(patient["issues"]).lower()
        self.assertIn("allergy status not recorded", issues)
        self.assertIn("covering clinician not named", issues)


class StructuralGapsEndToEndTests(unittest.TestCase):
    """The same invariant, seen through the assembled pipeline's gaps.md."""

    def test_gaps_md_lists_both_fields_for_a_silent_page(self):
        case = support.make_case([support.text_page(NO_CUE_TEXT)], case_id="SYN-STRUCT")
        with support.workspace() as tmp:
            result = support.run_pipeline(case, tmp)

        self.assertEqual(0, result.rc, result.stderr)
        section = result.gaps.split("## Missing mandatory fields", 1)[1]
        section = section.split("##", 1)[0].lower()
        self.assertIn("allergy status not recorded", section)
        self.assertIn("covering clinician not named", section)
        self.assertIn("bed 70", section)

    def test_gaps_md_lists_neither_field_when_both_are_present(self):
        case = support.make_case([support.text_page(VALUES_TEXT)], case_id="SYN-STRUCT-OK")
        with support.workspace() as tmp:
            result = support.run_pipeline(case, tmp)

        self.assertEqual(0, result.rc, result.stderr)
        section = result.gaps.split("## Missing mandatory fields", 1)[1]
        section = section.split("##", 1)[0].lower()
        self.assertNotIn("allergy status not recorded", section)
        self.assertNotIn("covering clinician not named", section)


if __name__ == "__main__":
    unittest.main()
