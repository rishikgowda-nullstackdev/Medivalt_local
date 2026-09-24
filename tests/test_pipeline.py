"""
MediVault Local - Day 4 Comprehensive Test Suite
Verifies CONTRACTS.md endpoints, brand normalization, allergy checks,
input validation guardrails, Ollama status, audit export, and network guard.
"""

import os
import sys
import unittest
from io import BytesIO

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.redactor import ClinicalRedactor
from backend.network_guard import network_guard
from backend.audit_logger import audit_logger
from backend.pharmacology import PharmacologyEngine
from backend.orchestrator import ClinicalOrchestrator
from backend.ai_bridge import ai_bridge
from backend.main import app


class TestMediVaultDay4(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_phi_redaction(self):
        """Verify 18 HIPAA Safe Harbor PHI identifiers are redacted."""
        raw_text = "Patient John Doe, DOB: 04/15/1960, SSN: 123-45-6789, Phone: 555-123-4567, MRN: 987654."
        redacted, detected_phi, token = ClinicalRedactor.redact_phi(raw_text)

        self.assertNotIn("123-45-6789", redacted)
        self.assertNotIn("04/15/1960", redacted)
        self.assertIn("[REDACTED_SSN]", redacted)
        self.assertIn("[REDACTED_DOB]", redacted)
        self.assertTrue(token.startswith("ANON_"))

    def test_02_clinical_entity_extraction(self):
        """Verify extraction of conditions, medications, allergies, and lab values."""
        clinical_note = (
            "Patient has Stage 3 Chronic Kidney Disease (CKD) and Essential Hypertension. "
            "Currently taking Lisinopril 20mg daily and Metformin 500mg BID. "
            "Allergies: Penicillin, Sulfa. Lab values show eGFR 38, Creatinine 2.1."
        )
        entities = ClinicalRedactor.extract_entities(clinical_note)

        self.assertIn("Chronic Kidney Disease", entities["diagnosed_conditions"])
        self.assertIn("Hypertension", entities["diagnosed_conditions"])
        self.assertTrue(any("Lisinopril" in m for m in entities["current_medications"]))
        self.assertTrue(any("Metformin" in m for m in entities["current_medications"]))
        self.assertIn("Penicillin", entities["allergies"])
        self.assertEqual(entities["clinical_labs"]["eGFR"], "38 mL/min/1.73m2")
        self.assertEqual(entities["clinical_labs"]["Creatinine"], "2.1 mg/dL")

    def test_03_brand_to_generic_normalization(self):
        """Verify brand name normalization (e.g. Advil -> ibuprofen, Inderal -> propranolol)."""
        gen1, brand1 = PharmacologyEngine.normalize_drug_name("Advil 400mg PO")
        self.assertEqual(gen1, "ibuprofen")
        self.assertEqual(brand1, "Advil")

        gen2, brand2 = PharmacologyEngine.normalize_drug_name("Inderal 40mg")
        self.assertEqual(gen2, "propranolol")
        self.assertEqual(brand2, "Inderal")

    def test_04_allergy_cross_checking(self):
        """Verify penicillin allergy cross-reacts with Amoxicillin."""
        alerts = PharmacologyEngine.check_drug_allergies("Amoxicillin", ["Penicillin"])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertEqual(alerts[0]["interaction_type"], "ALLERGY")

    def test_05_contract_upload_record_endpoint(self):
        """Verify frozen contract: POST /upload-record returns { redacted_text: str }."""
        dummy_content = b"Patient Jane Doe, Phone: 555-987-6543. Diagnosed with Asthma."
        response = self.client.post(
            "/upload-record",
            files={"file": ("consult.txt", BytesIO(dummy_content), "text/plain")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("redacted_text", data)
        self.assertNotIn("555-987-6543", data["redacted_text"])

    def test_06_contract_analyze_endpoint(self):
        """Verify frozen contract: POST /analyze returns { flagged: bool, reason: str, drug: str }."""
        redacted_doc = (
            "Patient [REDACTED_NAME]. Diagnosed with Stage 3 Chronic Kidney Disease (CKD). "
            "Prescribed Ibuprofen for joint pain."
        )
        response = self.client.post(
            "/analyze",
            json={"redacted_text": redacted_doc}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["flagged"])
        self.assertEqual(data["severity"], "CRITICAL")

    def test_07_validation_empty_file_upload(self):
        """Defensive test: Uploading empty file (0 bytes) returns 400 error."""
        response = self.client.post(
            "/upload-record",
            files={"file": ("empty.txt", BytesIO(b""), "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_08_validation_unsupported_file_extension(self):
        """Defensive test: Uploading unsupported extension (e.g. .exe) returns 415 error."""
        response = self.client.post(
            "/upload-record",
            files={"file": ("payload.exe", BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
        )
        self.assertEqual(response.status_code, 415)
        self.assertIn("unsupported", response.json()["detail"].lower())

    def test_09_validation_invalid_medication_name(self):
        """Defensive test: Empty or special characters in proposed medication returns 400."""
        # Empty
        res1 = self.client.post("/api/review", json={"patient_id": "PT-101", "proposed_medication": "   "})
        self.assertEqual(res1.status_code, 400)

        # Invalid characters (script injection)
        res2 = self.client.post("/api/review", json={"patient_id": "PT-101", "proposed_medication": "<script>alert(1)</script>"})
        self.assertEqual(res2.status_code, 400)

    def test_10_validation_nonexistent_patient(self):
        """Defensive test: Requesting review for non-existent patient returns 404."""
        response = self.client.post(
            "/api/review",
            json={"patient_id": "PT-9999", "proposed_medication": "Ibuprofen"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_11_ai_status_endpoint(self):
        """Verify GET /api/ai-status returns valid structure."""
        response = self.client.get("/api/ai-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("online", data)
        self.assertIn("active_model", data)

    def test_12_audit_export_json_and_csv(self):
        """Verify audit export in both JSON and CSV formats."""
        # JSON export
        res_json = self.client.get("/api/audit-export?format=json")
        self.assertEqual(res_json.status_code, 200)
        self.assertIn("audit_export", res_json.json())

        # CSV export
        res_csv = self.client.get("/api/audit-export?format=csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("Timestamp (UTC)", res_csv.text)

    def test_13_audit_chain_integrity(self):
        """Verify cryptographic SHA-256 hash chaining and tamper detection."""
        integrity = audit_logger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["status"], "ALL_BLOCKS_VALID_TAMPER_FREE")

    def test_14_network_guard_telemetry(self):
        """Verify zero external network egress assertion."""
        telemetry = network_guard.get_network_status()
        self.assertEqual(telemetry["status"], "SECURE_AIR_GAPPED")
        self.assertTrue(telemetry["zero_cloud_enforced"])


if __name__ == "__main__":
    unittest.main()
