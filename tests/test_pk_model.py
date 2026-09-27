"""
Unit and Integration Tests for MediVault Local Clinical PK Simulator
Validates Rowland & Tozer Glomerular Scaling, Multi-Dose Accumulation,
Toxic Threshold Alarms, Interactive Titration, and API Endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from ai_engine.pk_model import (
    PK_DRUG_DATABASE,
    resolve_pk_drug,
    calculate_patient_ke,
    simulate_pk_curve,
)
from backend.main import app
from backend.orchestrator import ClinicalOrchestrator


class TestPharmacokineticSimulator(unittest.TestCase):
    """Test suite for 1-compartment PK elimination and accumulation engine."""

    def setUp(self):
        self.client = TestClient(app)

    def test_pk_drug_database_integrity(self):
        """Verifies all configured PK drugs have physiologically sound parameters."""
        self.assertGreaterEqual(len(PK_DRUG_DATABASE), 6)
        required_keys = {
            "display_name", "drug_class", "vd_l_kg", "half_life_normal_h",
            "fe_renal", "ka_h", "standard_dose_mg", "standard_interval_h",
            "c_toxic_mg_l", "c_mec_mg_l", "toxicity_hazard"
        }
        for drug_key, data in PK_DRUG_DATABASE.items():
            for key in required_keys:
                self.assertIn(key, data, f"Drug {drug_key} missing {key}")
            self.assertGreater(data["vd_l_kg"], 0.0)
            self.assertGreater(data["half_life_normal_h"], 0.0)
            self.assertTrue(0.0 <= data["fe_renal"] <= 1.0)
            self.assertGreater(data["c_toxic_mg_l"], data["c_mec_mg_l"])

    def test_resolve_pk_drug(self):
        """Tests exact, case-insensitive, and brand-name drug resolution."""
        # Generic names
        key, profile = resolve_pk_drug("ketorolac")
        self.assertEqual(key, "ketorolac")
        self.assertIsNotNone(profile)

        key, _ = resolve_pk_drug("METFORMIN")
        self.assertEqual(key, "metformin")

        # Brand names
        key, _ = resolve_pk_drug("Toradol 10mg")
        self.assertEqual(key, "ketorolac")

        key, _ = resolve_pk_drug("Advil 400mg")
        self.assertEqual(key, "ibuprofen")

        key, _ = resolve_pk_drug("Lasix 40mg")
        self.assertEqual(key, "furosemide")

        # Unmatched drug
        key, profile = resolve_pk_drug("UnknownDrugXYZ")
        self.assertIsNone(key)
        self.assertIsNone(profile)

    def test_rowland_tozer_ke_scaling(self):
        """Tests Rowland & Tozer renal clearance rate scaling across eGFR tiers."""
        # For Ketorolac (fe = 0.91, normal t1/2 = 5.3h)
        # Normal kidney (eGFR 90): ke_patient == ke_norm
        ke_norm, t12_norm = calculate_patient_ke("ketorolac", egfr=90.0)
        self.assertAlmostEqual(t12_norm, 5.3, places=1)

        # Mild impairment (eGFR 60)
        ke_mild, t12_mild = calculate_patient_ke("ketorolac", egfr=60.0)
        self.assertLess(ke_mild, ke_norm)
        self.assertGreater(t12_mild, t12_norm)

        # Moderate impairment (eGFR 35) -> half-life should more than double
        ke_mod, t12_mod = calculate_patient_ke("ketorolac", egfr=35.0)
        self.assertGreater(t12_mod, 10.0)

        # Severe ESRD (eGFR 15) -> half-life extends dramatically
        ke_esrd, t12_esrd = calculate_patient_ke("ketorolac", egfr=15.0)
        self.assertGreater(t12_esrd, 18.0)

    def test_pk_simulation_normal_vs_impaired(self):
        """Simulates 72h accumulation curve and verifies impaired kidney retention."""
        # Simulate Ketorolac in healthy patient (eGFR 90)
        sim_normal = simulate_pk_curve("ketorolac", egfr=90.0, weight_kg=70.0)
        self.assertNotIn("error", sim_normal)
        self.assertFalse(sim_normal["toxic_exceeded"])
        self.assertAlmostEqual(sim_normal["half_life_multiplier"], 1.0, places=1)
        self.assertEqual(len(sim_normal["patient_curve"]), len(sim_normal["time_points"]))

        # Simulate Ketorolac in CKD Stage 3 patient (eGFR 30)
        sim_ckd = simulate_pk_curve("ketorolac", egfr=30.0, weight_kg=70.0)
        self.assertNotIn("error", sim_ckd)
        self.assertGreater(sim_ckd["half_life_patient_h"], sim_normal["half_life_patient_h"])
        self.assertGreater(sim_ckd["peak_patient_mg_l"], sim_normal["peak_patient_mg_l"])
        self.assertGreater(sim_ckd["accumulation_ratio"], sim_normal["accumulation_ratio"])

    def test_toxic_ceiling_detection(self):
        """Verifies toxic concentration alarms when accumulation crosses c_toxic."""
        # High dose Ketorolac (30mg q6h) in severe renal failure (eGFR 15)
        sim = simulate_pk_curve(
            "ketorolac",
            egfr=15.0,
            weight_kg=70.0,
            dose_mg=30.0,
            interval_hours=6.0
        )
        self.assertTrue(sim["toxic_exceeded"])
        self.assertEqual(sim["status_color"], "#ef4444")
        self.assertIn("CRITICAL ACCUMULATION", sim["severity_label"])
        self.assertIn("titration", sim["titration_advice"].lower())

    def test_renal_titration_recovery(self):
        """Tests that dose reduction and interval prolongation restore safe levels."""
        # Baseline toxic: 30mg q6h at eGFR 20
        toxic_sim = simulate_pk_curve(
            "ketorolac",
            egfr=20.0,
            weight_kg=70.0,
            dose_mg=30.0,
            interval_hours=6.0
        )
        self.assertTrue(toxic_sim["toxic_exceeded"])

        # Titrated regimen: 10mg q12h at eGFR 20
        safe_sim = simulate_pk_curve(
            "ketorolac",
            egfr=20.0,
            weight_kg=70.0,
            dose_mg=10.0,
            interval_hours=12.0
        )
        self.assertFalse(safe_sim["toxic_exceeded"])
        self.assertLess(safe_sim["peak_patient_mg_l"], toxic_sim["c_toxic_mg_l"])

    def test_api_pk_drugs_endpoint(self):
        """Tests GET /api/pk/drugs returns configured drug catalog."""
        res = self.client.get("/api/pk/drugs")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("drugs", data)
        self.assertGreaterEqual(data["total"], 6)
        drug_names = [d["drug_key"] for d in data["drugs"]]
        self.assertIn("ketorolac", drug_names)
        self.assertIn("lisinopril", drug_names)
        self.assertIn("metformin", drug_names)

    def test_api_pk_simulate_endpoint(self):
        """Tests POST /api/pk/simulate computes valid PK clearance curves."""
        payload = {
            "drug_name": "Toradol",
            "egfr": 35.0,
            "weight_kg": 65.0,
            "dose_mg": 10.0,
            "interval_hours": 8.0,
            "total_hours": 48.0
        }
        res = self.client.post("/api/pk/simulate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["drug_key"], "ketorolac")
        self.assertEqual(data["egfr"], 35.0)
        self.assertGreater(data["half_life_multiplier"], 1.5)
        self.assertEqual(len(data["time_points"]), 49)  # 48h / 1.0h + 1

    def test_api_pk_simulate_invalid_drug(self):
        """Tests POST /api/pk/simulate with unknown drug returns 400."""
        payload = {
            "drug_name": "NonExistentDrug999",
            "egfr": 50.0
        }
        res = self.client.post("/api/pk/simulate", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_orchestrator_attaches_pk_simulation(self):
        """Tests that ClinicalOrchestrator attaches pk_simulation to review."""
        # Single review with Ketorolac for patient PT-101 (eGFR 38)
        result = ClinicalOrchestrator.process_review(
            proposed_med="Toradol 10mg",
            patient_id="PT-101"
        )
        self.assertIn("pk_simulation", result)
        self.assertIsNotNone(result["pk_simulation"])
        self.assertEqual(result["pk_simulation"]["drug_key"], "ketorolac")
        self.assertAlmostEqual(result["pk_simulation"]["egfr"], 38.0, delta=2.0)

        # Multi-prescription bundle review containing Ketorolac
        bundle_result = ClinicalOrchestrator.process_prescription_review(
            proposed_meds=["Tab Ketorolac 10mg PO Q6H", "Cap Omeprazole 20mg PO QD"],
            patient_id="PT-101"
        )
        self.assertIn("pk_simulation", bundle_result)
        self.assertIsNotNone(bundle_result["pk_simulation"])
        self.assertEqual(bundle_result["pk_simulation"]["drug_key"], "ketorolac")


if __name__ == "__main__":
    unittest.main()
