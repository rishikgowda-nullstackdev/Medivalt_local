"""
MediVault Local - Geriatric & Renal Decision Support Automated Test Suite
Tests:
- Cockcroft-Gault Creatinine Clearance (CrCl) calculation accuracy
- Narrow-therapeutic drug renal dosing titration
- 2023 AGS Beers Criteria geriatric inappropriate medication screening
- Full safety integration via evaluate_full_safety
"""

import unittest
from ai_engine.geriatric_renal import calculate_cockcroft_gault, GeriatricRenalEngine
from ai_engine.engine import evaluate_full_safety


class TestGeriatricRenal(unittest.TestCase):

    def test_cockcroft_gault_male(self):
        """
        Verify male Cockcroft-Gault CrCl calculation:
        Age 64, Weight 78kg, SCr 1.0 mg/dL:
        CrCl = ((140 - 64) * 78) / (72 * 1.0) = (76 * 78) / 72 = 5928 / 72 = 82.3 mL/min
        """
        crcl = calculate_cockcroft_gault(age=64, weight_kg=78.0, serum_creatinine=1.0, is_female=False)
        self.assertEqual(crcl, 82.3)

    def test_cockcroft_gault_female(self):
        """
        Verify female Cockcroft-Gault CrCl calculation (with 0.85 multiplier):
        Age 76, Weight 50kg, SCr 1.8 mg/dL:
        CrCl = [((140 - 76) * 50) / (72 * 1.8)] * 0.85 = (3200 / 129.6) * 0.85 = 24.69 * 0.85 = 21.0 mL/min
        """
        crcl = calculate_cockcroft_gault(age=76, weight_kg=50.0, serum_creatinine=1.8, is_female=True)
        self.assertEqual(crcl, 21.0)

    def test_cockcroft_gault_invalid_inputs(self):
        """Verify graceful None handling on invalid or missing clinical parameters."""
        self.assertIsNone(calculate_cockcroft_gault(None, 50.0, 1.0, False))
        self.assertIsNone(calculate_cockcroft_gault(65, None, 1.0, False))
        self.assertIsNone(calculate_cockcroft_gault(65, 50.0, 0, False))

    def test_renal_titration_gabapentin_overdose(self):
        """Verify Gabapentin dose titration alert when CrCl < 30 mL/min."""
        alerts = GeriatricRenalEngine.evaluate_renal_titration("gabapentin", crcl=21.0)
        self.assertGreater(len(alerts), 0)
        alert = alerts[0]
        self.assertEqual(alert["severity"], "CRITICAL")
        self.assertEqual(alert["interaction_type"], "RENAL_TITRATION")
        self.assertIn("Reduce dose: 200mg to 300mg", alert["recommendation"])

    def test_renal_titration_normal_clearance(self):
        """Verify zero titration alerts for Gabapentin when CrCl is normal (> 60 mL/min)."""
        alerts = GeriatricRenalEngine.evaluate_renal_titration("gabapentin", crcl=85.0)
        self.assertEqual(len(alerts), 0)

    def test_beers_criteria_elderly_anticholinergic(self):
        """Verify 2023 AGS Beers Criteria alert for Diphenhydramine in patient >= 65yo."""
        alerts = GeriatricRenalEngine.evaluate_beers_criteria("diphenhydramine", age=76)
        self.assertGreater(len(alerts), 0)
        alert = alerts[0]
        self.assertEqual(alert["severity"], "CRITICAL")
        self.assertEqual(alert["interaction_type"], "BEERS_CRITERIA")
        self.assertIn("Acute Delirium", alert["clinical_mechanism"])
        self.assertIn("Melatonin", alert["recommendation"])

    def test_beers_criteria_young_patient(self):
        """Verify Beers criteria does NOT trigger for young patient (< 65yo)."""
        alerts = GeriatricRenalEngine.evaluate_beers_criteria("diphenhydramine", age=32)
        self.assertEqual(len(alerts), 0)

    def test_beers_criteria_sedative_fall_hazard(self):
        """Verify Beers criteria flags Zolpidem / Z-drugs for ataxia and fall risk in elderly."""
        alerts = GeriatricRenalEngine.evaluate_beers_criteria("zolpidem", age=72)
        self.assertGreater(len(alerts), 0)
        alert = alerts[0]
        self.assertEqual(alert["severity"], "CRITICAL")
        self.assertIn("Fall Hazard", alert["clinical_mechanism"])

    def test_full_safety_integration_geriatric_renal(self):
        """Verify end-to-end integration of Beers and CrCl in evaluate_full_safety."""
        demographics = {"age": 76, "gender": "female", "weight_kg": 50.0}
        labs = {"creatinine": {"value": 1.8, "unit": "mg/dL"}}
        
        status, alerts, canonical, alts = evaluate_full_safety(
            proposed_med="Gabapentin",
            conditions=["chronic kidney disease"],
            medications=["lisinopril"],
            allergies=[],
            labs=labs,
            demographics=demographics
        )
        self.assertEqual(status, "CRITICAL")
        types = [a["interaction_type"] for a in alerts]
        self.assertIn("RENAL_TITRATION", types)


if __name__ == "__main__":
    unittest.main()
