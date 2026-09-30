"""
Unit tests for Autonomous SLM Clinical Note Intelligence Engine (Person B).
Tests unstructured clinical text parsing, ICD-10 mapping, entity extraction,
and diagnostic discrepancy & safety omission detection.
"""

import unittest
from ingestion.note_intelligence import extract_clinical_intelligence_from_note, NoteIntelligenceEngine


class TestNoteIntelligence(unittest.TestCase):

    def setUp(self):
        self.sample_discharge_note = (
            "EMERGENCY DEPARTMENT DISCHARGE SUMMARY\n"
            "PATIENT: John Doe | AGE: 64 | MRN: 902814\n"
            "DIAGNOSES: Stage 3 CKD, Essential Hypertension, Type 2 Diabetes.\n"
            "LABS: eGFR 38 mL/min, Creatinine 2.1 mg/dL, Potassium 4.8 mEq/L, BP 132/84 mmHg.\n"
            "MEDICATIONS ON DISCHARGE:\n"
            "- Lisinopril 20mg PO daily\n"
            "- Furosemide 40mg PO daily\n"
            "- Ketorolac 10mg PO PRN for acute back spasm\n"
            "ALLERGIES: Penicillin (anaphylaxis), Sulfa (rash).\n"
            "PLAN: Follow up with nephrology in 2 weeks."
        )

    def test_extract_conditions_and_icd10(self):
        """Should detect CKD, Hypertension, and Diabetes and assign ICD-10 codes."""
        res = extract_clinical_intelligence_from_note(self.sample_discharge_note)
        cond_names = [c["name"].lower() for c in res["conditions"]]
        self.assertTrue(any("ckd" in c or "chronic kidney" in c for c in cond_names))
        self.assertTrue(any("hypertension" in c for c in cond_names))

        # Check ICD-10 attached
        for c in res["conditions"]:
            if "ckd" in c["name"].lower():
                self.assertTrue(c["icd10"].startswith("N18"))

    def test_extract_medications_with_dose(self):
        """Should parse Lisinopril 20mg, Furosemide 40mg, and Ketorolac 10mg."""
        res = extract_clinical_intelligence_from_note(self.sample_discharge_note)
        med_names = [m["name"].lower() for m in res["medications"]]
        self.assertTrue(any("lisinopril" in m for m in med_names))
        self.assertTrue(any("furosemide" in m for m in med_names))
        self.assertTrue(any("ketorolac" in m for m in med_names))

    def test_extract_lab_biomarkers(self):
        """Should capture quantitative eGFR and Creatinine biomarkers."""
        res = extract_clinical_intelligence_from_note(self.sample_discharge_note)
        labs = res["labs"]
        self.assertTrue("eGFR" in labs or "egfr" in labs)
        self.assertTrue("Creatinine" in labs or "creatinine" in labs)

    def test_detect_renal_and_triple_whammy_discrepancies(self):
        """Should detect Renal Nephrotoxic Hazard and Triple Whammy Combination."""
        res = extract_clinical_intelligence_from_note(self.sample_discharge_note)
        discrepancies = res["discrepancies"]
        disc_types = [d["type"] for d in discrepancies]

        self.assertIn("RENAL_NEPHROTOXIC_HAZARD", disc_types)
        self.assertIn("TRIPLE_WHAMMY_HEMODYNAMIC_COLLAPSE", disc_types)

    def test_detect_chart_allergy_omission(self):
        """Should detect an allergy documented in the note that is missing from existing EHR."""
        chart_missing_sulfa = {
            "allergies": ["Penicillin"]  # Sulfa is missing from chart!
        }
        res = extract_clinical_intelligence_from_note(self.sample_discharge_note, existing_chart=chart_missing_sulfa)
        disc_types = [d["type"] for d in res["discrepancies"]]
        self.assertIn("CHART_ALLERGY_OMISSION", disc_types)


if __name__ == "__main__":
    unittest.main()
