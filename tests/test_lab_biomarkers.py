"""
MediVault Local - Quantitative Lab Biomarker Guardrails Test Suite
Verifies:
1. Regex numerical lab extraction (eGFR, Creatinine, Potassium K+, INR, Platelets, BP).
2. Deterministic mathematical evaluation against contraindications_lab SQLite table.
3. Dose titration warnings vs absolute contraindications.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pipeline import extract_lab_biomarkers, extract_entities
from ai_engine.lab_evaluator import LabBiomarkerEvaluator


class TestLabBiomarkers(unittest.TestCase):

    def test_01_lab_extraction_from_clinical_text(self):
        """Verify numerical lab parser extracts numbers and units correctly."""
        note = (
            "Lab results: eGFR 28 mL/min/1.73m2, Serum Creatinine 2.4 mg/dL, "
            "Potassium: 5.4 mEq/L, current INR 3.8, Platelets 42k, BP 148/92 mmHg."
        )
        labs = extract_lab_biomarkers(note)

        self.assertIn("eGFR", labs)
        self.assertEqual(labs["eGFR"]["value"], 28.0)
        self.assertEqual(labs["eGFR"]["status"], "CRITICAL_LOW")

        self.assertIn("Creatinine", labs)
        self.assertEqual(labs["Creatinine"]["value"], 2.4)

        self.assertIn("Potassium", labs)
        self.assertEqual(labs["Potassium"]["value"], 5.4)
        self.assertEqual(labs["Potassium"]["status"], "CRITICAL_HIGH")

        self.assertIn("INR", labs)
        self.assertEqual(labs["INR"]["value"], 3.8)
        self.assertEqual(labs["INR"]["status"], "CRITICAL_HIGH")

        self.assertIn("Platelets", labs)
        self.assertEqual(labs["Platelets"]["value"], 42.0)
        self.assertEqual(labs["Platelets"]["status"], "CRITICAL_LOW")

        self.assertIn("BloodPressure", labs)
        self.assertEqual(labs["BloodPressure"]["systolic"], 148)
        self.assertEqual(labs["BloodPressure"]["diastolic"], 92)

    def test_02_metformin_severe_renal_failure_cutoff(self):
        """Metformin with eGFR < 30 mL/min must trigger CRITICAL lactic acidosis alert."""
        labs = {"egfr": {"value": 26.0, "unit": "mL/min/1.73m2"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("metformin", "Glucophage", labs)

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertIn("lactic acidosis", alerts[0]["clinical_mechanism"].lower())

    def test_03_metformin_moderate_renal_failure_cutoff(self):
        """Metformin with eGFR 38 mL/min (30-44 range) must trigger WARNING dose titration."""
        labs = {"egfr": {"value": 38.0, "unit": "mL/min/1.73m2"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("metformin", "Glucophage", labs)

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "WARNING")
        self.assertIn("1000mg/day", alerts[0]["recommendation"].lower())

    def test_04_metformin_normal_renal_function(self):
        """Metformin with normal eGFR (75 mL/min) must pass with 0 lab alerts."""
        labs = {"egfr": {"value": 75.0, "unit": "mL/min/1.73m2"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("metformin", None, labs)
        self.assertEqual(len(alerts), 0)

    def test_05_hyperkalemia_with_ace_inhibitor(self):
        """Lisinopril with Potassium > 5.0 mEq/L must trigger CRITICAL hyperkalemia alert."""
        labs = {"potassium": {"value": 5.4, "unit": "mEq/L"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("lisinopril", "Zestril", labs)

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertIn("hyperkalem", alerts[0]["clinical_mechanism"].lower())

    def test_06_supratherapeutic_inr_with_warfarin(self):
        """Warfarin with INR > 3.5 must trigger CRITICAL supratherapeutic hemorrhage warning."""
        labs = {"inr": {"value": 3.9, "unit": "INR"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("warfarin", "Coumadin", labs)

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertIn("hemorrhage", alerts[0]["clinical_mechanism"].lower())

    def test_07_thrombocytopenia_with_antiplatelet(self):
        """Aspirin or Clopidogrel with Platelets < 50k must trigger CRITICAL bleeding alert."""
        labs = {"platelets": {"value": 35.0, "unit": "x10^3/uL"}}
        alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs("clopidogrel", "Plavix", labs)

        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertIn("thrombocytopenia", alerts[0]["clinical_mechanism"].lower())


if __name__ == "__main__":
    unittest.main()
