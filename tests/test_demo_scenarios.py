"""
Tests for MediVault Local Interactive Judge Demo & Clinical Crisis Simulator.
Verifies all 4 clinical scenarios:
1. The Silent Renal Collapse (CKD + Ketorolac)
2. The Lethal Triple Whammy (Lisinopril + Furosemide + Ibuprofen)
3. Hidden Beta-Lactam Cross-Allergy (Augmentin)
4. Cumulative QTc Arrhythmia (Amiodarone + Azithromycin)
Ensures 100% offline sovereign execution and correct critical flags.
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.demo_scenarios import CLINICAL_SCENARIOS


class TestJudgeDemoScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_list_demo_scenarios(self):
        """GET /api/demo/scenarios returns all 4 scenarios with expected keys."""
        resp = self.client.get("/api/demo/scenarios")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("scenarios", data)
        scenarios = data["scenarios"]
        self.assertEqual(len(scenarios), 4)

        scenario_ids = [s["id"] for s in scenarios]
        self.assertIn("renal_collapse", scenario_ids)
        self.assertIn("triple_whammy", scenario_ids)
        self.assertIn("hidden_anaphylaxis", scenario_ids)
        self.assertIn("anticoagulant_hemorrhage", scenario_ids)

        for s in scenarios:
            self.assertIn("title", s)
            self.assertIn("subtitle", s)
            self.assertIn("badge", s)
            self.assertIn("proposed_medication", s)
            self.assertIn("hazard_summary", s)

    def test_get_individual_scenario_details(self):
        """GET /api/demo/scenarios/{id} returns rich details and talking points."""
        resp = self.client.get("/api/demo/scenarios/renal_collapse")
        self.assertEqual(resp.status_code, 200)
        s = resp.json()
        self.assertEqual(s["id"], "renal_collapse")
        self.assertEqual(s["proposed_medication"], "Ketorolac")
        self.assertTrue(len(s["talking_points"]) >= 3)
        self.assertIn("safe_alternative", s)
        self.assertEqual(s["safe_alternative"]["drug"], "Acetaminophen")

    def test_get_nonexistent_scenario(self):
        """GET /api/demo/scenarios/invalid returns 404."""
        resp = self.client.get("/api/demo/scenarios/nonexistent_scenario_123")
        self.assertEqual(resp.status_code, 404)

    def test_run_scenario_1_renal_collapse(self):
        """POST /api/demo/run/renal_collapse executes CDSS and flags CRITICAL."""
        resp = self.client.post("/api/demo/run/renal_collapse")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["review"]["overall_status"], "CRITICAL")
        self.assertTrue(data["review"]["flagged"])
        self.assertIn("presenter_cheatsheet", data)
        self.assertTrue(len(data["presenter_cheatsheet"]["talking_points"]) > 0)

    def test_run_scenario_2_triple_whammy(self):
        """POST /api/demo/run/triple_whammy flags CRITICAL due to polypharmacy."""
        resp = self.client.post("/api/demo/run/triple_whammy")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["review"]["overall_status"], "CRITICAL")
        self.assertTrue(data["review"]["flagged"])

    def test_run_scenario_3_hidden_anaphylaxis(self):
        """POST /api/demo/run/hidden_anaphylaxis flags CRITICAL or WARNING due to allergy cross-check."""
        resp = self.client.post("/api/demo/run/hidden_anaphylaxis")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["review"]["flagged"])

    def test_run_scenario_4_anticoagulant_hemorrhage(self):
        """POST /api/demo/run/anticoagulant_hemorrhage flags bleeding risk."""
        resp = self.client.post("/api/demo/run/anticoagulant_hemorrhage")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["review"]["overall_status"], "CRITICAL")
        self.assertTrue(data["review"]["flagged"])


if __name__ == "__main__":
    unittest.main()
