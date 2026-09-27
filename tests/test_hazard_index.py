"""
MediVault Local - Clinical Hazard Index & Patient Vulnerability Gauge Tests
Tests sovereign 0-100 hazard scoring across organ stress, polypharmacy burden,
DDI alert severity, allergy cross-reactivity, and age vulnerability.
Validates both mathematical engine accuracy and backend API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from ai_engine.hazard_index import calculate_hazard_index


class TestClinicalHazardIndex(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_baseline_safe_profile(self):
        """Verifies that a patient with normal labs and no drug alerts gets a LOW hazard score (<30)."""
        result = calculate_hazard_index(
            biomarkers={
                "eGFR": {"value": 85.0, "unit": "mL/min"},
                "Creatinine": {"value": 0.9, "unit": "mg/dL"},
                "Potassium": {"value": 4.1, "unit": "mEq/L"}
            },
            alerts=[],
            active_medications=["Metformin 500mg"],
            conditions=["Type 2 Diabetes Mellitus"],
            allergies=["NKDA"],
            demographics={"age": 45, "gender": "female"},
            overall_status="SAFE"
        )

        self.assertIsInstance(result, dict)
        self.assertLess(result["score"], 30)
        self.assertEqual(result["risk_tier"], "LOW")
        self.assertEqual(result["color"], "#10b981")
        self.assertLessEqual(result["needle_degrees"], 54.0)
        self.assertEqual(result["category_breakdown"]["organ_stress"]["score"], 0)
        self.assertEqual(result["category_breakdown"]["drug_interactions"]["score"], 0)

    def test_02_ckd_organ_stress_profile(self):
        """Verifies that moderate-severe CKD derangements elevate organ stress points."""
        result = calculate_hazard_index(
            biomarkers={
                "eGFR": {"value": 38.0, "unit": "mL/min/1.73m2"},
                "Creatinine": {"value": 1.9, "unit": "mg/dL"}
            },
            alerts=[],
            active_medications=["Lisinopril 20mg", "Amlodipine 5mg"],
            conditions=["Chronic Kidney Disease Stage 3b", "Hypertension"],
            allergies=[],
            demographics={"age": 64, "gender": "male"},
            overall_status="SAFE"
        )

        organ_score = result["category_breakdown"]["organ_stress"]["score"]
        self.assertGreaterEqual(organ_score, 20)
        self.assertGreaterEqual(result["score"], 30)
        self.assertIn("moderate-severe ckd", result["primary_driver"].lower())

    def test_03_acute_critical_interaction(self):
        """Verifies that a CRITICAL contraindication alert pushes hazard index into HIGH or CRITICAL tier."""
        result = calculate_hazard_index(
            biomarkers={"eGFR": {"value": 35.0, "unit": "mL/min"}},
            alerts=[{
                "severity": "CRITICAL",
                "interaction_type": "DRUG_DISEASE",
                "contraindicated_factor": "Chronic Kidney Disease Stage 3b",
                "clinical_mechanism": "Inhibition of renal prostaglandins causes acute hemodynamics collapse"
            }],
            active_medications=["Lisinopril 20mg"],
            conditions=["Chronic Kidney Disease"],
            allergies=[],
            demographics={"age": 68, "gender": "male"},
            overall_status="CRITICAL"
        )

        self.assertGreaterEqual(result["score"], 70)
        self.assertIn(result["risk_tier"], ["HIGH", "CRITICAL"])
        self.assertGreaterEqual(result["needle_degrees"], 126.0)
        self.assertGreaterEqual(result["category_breakdown"]["drug_interactions"]["score"], 30)

    def test_04_polypharmacy_and_triple_whammy(self):
        """Verifies polypharmacy burden scoring with multiple interacting agents."""
        active_meds = [
            "Lisinopril 20mg", "Furosemide 40mg", "Metformin 1000mg",
            "Amlodipine 10mg", "Atorvastatin 40mg", "Omeprazole 20mg",
            "Aspirin 81mg", "Gabapentin 300mg", "Ibuprofen 400mg"
        ]
        result = calculate_hazard_index(
            biomarkers={"eGFR": {"value": 48.0}},
            alerts=[{
                "severity": "CRITICAL",
                "interaction_type": "POLYPHARMACY",
                "rule_name": "Triple Whammy Cascade",
                "clinical_mechanism": "ACEi + Diuretic + NSAID triple insult"
            }],
            active_medications=active_meds,
            conditions=["Hypertension", "Heart Failure"],
            demographics={"age": 72}
        )

        self.assertGreaterEqual(result["category_breakdown"]["polypharmacy"]["score"], 15)
        self.assertGreaterEqual(result["score"], 65)

    def test_05_geriatric_and_allergy_factors(self):
        """Verifies age vulnerability (Age >= 85) and active allergy cross-reactivity points."""
        result = calculate_hazard_index(
            biomarkers={},
            alerts=[{
                "severity": "CRITICAL",
                "interaction_type": "ALLERGY",
                "contraindicated_factor": "Penicillin (Cross-reactive with Amoxicillin)",
                "clinical_mechanism": "IgE-mediated beta-lactam hypersensitivity"
            }],
            active_medications=["Metoprolol 50mg"],
            allergies=["Penicillin"],
            demographics={"age": 87, "gender": "female"}
        )

        self.assertEqual(result["category_breakdown"]["allergy_risks"]["score"], 10)
        self.assertGreaterEqual(result["category_breakdown"]["age_vulnerability"]["score"], 8)

    def test_06_endpoint_get_patient_hazard_index(self):
        """Tests GET /api/hazard-index/{patient_id} for valid and invalid patients."""
        # PT-101 (CKD patient)
        res101 = self.client.get("/api/hazard-index/PT-101")
        self.assertEqual(res101.status_code, 200)
        d101 = res101.json()
        self.assertIn("score", d101)
        self.assertIn("risk_tier", d101)
        self.assertIn("needle_degrees", d101)
        self.assertIn("category_breakdown", d101)
        self.assertEqual(d101["patient_id"], "PT-101")
        self.assertGreater(d101["score"], 30)

        # PT-102 (Younger Asthma patient)
        res102 = self.client.get("/api/hazard-index/PT-102")
        self.assertEqual(res102.status_code, 200)
        self.assertEqual(res102.json()["risk_tier"], "LOW")

        # Unknown patient -> 404
        res_unknown = self.client.get("/api/hazard-index/PT-NONEXISTENT")
        self.assertEqual(res_unknown.status_code, 404)

    def test_07_review_endpoint_integrates_hazard_index(self):
        """Tests that POST /api/review returns the computed hazard_index object."""
        payload = {
            "patient_id": "PT-101",
            "proposed_medication": "Ketorolac",
            "dosage": "10mg PO"
        }
        res = self.client.post("/api/review", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("hazard_index", data)
        hz = data["hazard_index"]
        self.assertIsNotNone(hz)
        self.assertIn("score", hz)
        self.assertIn("risk_tier", hz)
        self.assertIn("category_breakdown", hz)
        self.assertGreaterEqual(hz["score"], 60)

    def test_08_prescription_bundle_integrates_hazard_index(self):
        """Tests that POST /api/review with multi-medicine bundles returns hazard_index."""
        payload = {
            "patient_id": "PT-101",
            "proposed_medications": [
                {"medication": "Lisinopril", "dosage": "20mg"},
                {"medication": "Furosemide", "dosage": "40mg"},
                {"medication": "Ibuprofen", "dosage": "400mg"}
            ]
        }
        res = self.client.post("/api/review", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("hazard_index", data)
        hz = data["hazard_index"]
        self.assertIsNotNone(hz)
        self.assertGreaterEqual(hz["score"], 70)
        self.assertIn(hz["risk_tier"], ["HIGH", "CRITICAL"])


if __name__ == "__main__":
    unittest.main()
