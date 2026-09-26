"""
Unit & Integration Tests for Multi-Medicine Prescription Evaluation & File Upload
Verifies:
1. Ingestion of multi-drug prescription files (.pdf, .txt) & freeform clinical sig notes.
2. Two-tier AI Engine evaluation (Deterministic rules + SLM novel reasoning).
3. Intra-prescription drug-drug interactions and polypharmacy cascades.
4. FastAPI endpoints (/api/upload-prescription, /api/review, /api/review-prescription).
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app
from ingestion.pipeline import extract_prescription_bundle
from ai_engine.engine import evaluate_prescription_set


class TestPrescriptionBundle(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_extract_prescription_bundle_text(self):
        """Verifies parsing of multi-line real-world prescription notations."""
        sample_text = """
        Patient: John Doe, Phone: 9876543210
        1. Tab Augmentin 625mg PO 1-0-1 x 5 days
        2. Cap Omeprazole 20mg OD before meals
        3. Tab Paracetamol 650mg PO SOS
        """
        bundle = extract_prescription_bundle(sample_text)
        
        self.assertNotIn("John Doe", bundle["redacted_text"])
        self.assertNotIn("9876543210", bundle["redacted_text"])
        self.assertGreaterEqual(len(bundle["prescriptions"]), 3)
        
        drug_names = [p["medication"].lower() for p in bundle["prescriptions"]]
        self.assertIn("augmentin", drug_names)
        self.assertIn("omeprazole", drug_names)
        self.assertIn("paracetamol", drug_names)

    def test_evaluate_prescription_set_triple_whammy(self):
        """Verifies detection of lethal triple whammy within a multi-drug prescription bundle."""
        proposed_meds = [
            {"medication": "Lisinopril", "dosage": "20mg", "route": "PO", "frequency": "QD"},
            {"medication": "Furosemide", "dosage": "40mg", "route": "PO", "frequency": "QD"},
            {"medication": "Ibuprofen", "dosage": "400mg", "route": "PO", "frequency": "TID"}
        ]
        conditions = ["chronic kidney disease", "hypertension"]
        existing_meds = []
        allergies = []
        labs = {"eGFR": {"value": 28.0, "unit": "mL/min/1.73m2"}}

        res = evaluate_prescription_set(
            proposed_meds=proposed_meds,
            conditions=conditions,
            existing_meds=existing_meds,
            allergies=allergies,
            labs=labs
        )

        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertTrue(res["flagged"])
        self.assertEqual(res["total_prescribed"], 3)
        self.assertGreaterEqual(res["flagged_count"], 1)
        
        ibu_eval = next((e for e in res["medication_evaluations"] if "ibuprofen" in e["medication"].lower()), None)
        self.assertIsNotNone(ibu_eval)
        self.assertEqual(ibu_eval["status"], "CRITICAL")
        self.assertGreater(len(ibu_eval["recommended_alternatives"]), 0)

    def test_evaluate_prescription_set_safe_bundle(self):
        """Verifies that a safe multi-drug care plan passes with overall SAFE status."""
        proposed_meds = [
            {"medication": "Amoxicillin", "dosage": "500mg", "route": "PO", "frequency": "TID"},
            {"medication": "Paracetamol", "dosage": "650mg", "route": "PO", "frequency": "TID"},
            {"medication": "Omeprazole", "dosage": "20mg", "route": "PO", "frequency": "OD"}
        ]
        conditions = ["osteoarthritis"]
        existing_meds = []
        allergies = ["Sulfa"]

        res = evaluate_prescription_set(
            proposed_meds=proposed_meds,
            conditions=conditions,
            existing_meds=existing_meds,
            allergies=allergies
        )

        self.assertEqual(res["overall_status"], "SAFE")
        self.assertFalse(res["flagged"])
        self.assertEqual(res["flagged_count"], 0)
        self.assertEqual(len(res["medication_evaluations"]), 3)

    def test_api_upload_prescription(self):
        """Verifies POST /api/upload-prescription endpoint."""
        file_content = b"Rx:\n1. Tab Advil 400mg TID\n2. Tab Lisinopril 20mg QD"
        response = self.client.post(
            "/api/upload-prescription",
            files={"file": ("rx.txt", file_content, "text/plain")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("prescriptions", data)
        self.assertGreaterEqual(len(data["prescriptions"]), 2)
        drug_names = [p["medication"].lower() for p in data["prescriptions"]]
        self.assertTrue("advil" in drug_names or "ibuprofen" in drug_names)

    def test_api_upload_prescription_pdf(self):
        """Verifies POST /api/upload-prescription with actual binary PDF file."""
        import os
        pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "prescription_triple_whammy.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            response = self.client.post(
                "/api/upload-prescription",
                files={"file": ("prescription_triple_whammy.pdf", pdf_bytes, "application/pdf")}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("prescriptions", data)
            self.assertGreaterEqual(len(data["prescriptions"]), 2)
            drug_names = [p["medication"].lower() for p in data["prescriptions"]]
    def test_api_review_multi_medicine_bundle(self):
        """Verifies POST /api/review endpoint with multi-line prescription text."""
        payload = {
            "patient_id": "PT-101",
            "prescription_text": "Tab Advil 400mg PO TID\nTab Paracetamol 650mg PO SOS"
        }
        response = self.client.post("/api/review", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["overall_status"], "CRITICAL")
        self.assertIn("medication_evaluations", data)
        self.assertGreaterEqual(len(data["medication_evaluations"]), 2)
        self.assertIn("audit_hash", data)
        self.assertTrue(data["zero_cloud_verified"])


if __name__ == "__main__":
    unittest.main()



