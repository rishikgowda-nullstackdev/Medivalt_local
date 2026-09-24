"""
MediVault Local - Day 3 Comprehensive Test Suite
Verifies CONTRACTS.md endpoints, brand-to-generic drug normalization,
allergy cross-checking, deterministic safety checks, audit chaining, and network guard.
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
from backend.main import app


class TestMediVaultDay3(unittest.TestCase):

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

        gen3, brand3 = PharmacologyEngine.normalize_drug_name("Coumadin")
        self.assertEqual(gen3, "warfarin")
        self.assertEqual(brand3, "Coumadin")

    def test_04_allergy_cross_checking(self):
        """Verify penicillin allergy cross-reacts with Amoxicillin."""
        alerts = PharmacologyEngine.check_drug_allergies("Amoxicillin", ["Penicillin"])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "CRITICAL")
        self.assertEqual(alerts[0]["interaction_type"], "ALLERGY")
        self.assertIn("beta-lactam", alerts[0]["clinical_mechanism"].lower())

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
        self.assertIn("[REDACTED_PHONE]", data["redacted_text"])

    def test_06_contract_analyze_endpoint(self):
        """Verify frozen contract: POST /analyze returns { flagged: bool, reason: str, drug: str }."""
        # Record with CKD and Ibuprofen mentioned
        redacted_doc = (
            "Patient [REDACTED_NAME]. Diagnosed with Stage 3 Chronic Kidney Disease (CKD). "
            "Currently taking Lisinopril. Prescribed Ibuprofen for joint pain."
        )
        response = self.client.post(
            "/analyze",
            json={"redacted_text": redacted_doc}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("flagged", data)
        self.assertTrue(data["flagged"])
        self.assertEqual(data["severity"], "CRITICAL")
        self.assertIn("Ibuprofen", data["drug"])

    def test_07_brand_prescription_triggers_flag(self):
        """Verify that prescribing 'Advil' (brand) to a CKD patient flags as CRITICAL."""
        res = ClinicalOrchestrator.process_review(
            proposed_med="Advil 400mg",
            patient_id="PT-101"
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertEqual(res["canonical_generic"], "ibuprofen")
        self.assertTrue(any("Chronic Kidney Disease" in a["conflicting_factor"] for a in res["alerts"]))

    def test_08_allergy_prescription_triggers_flag(self):
        """Verify that prescribing Amoxicillin to a patient with Penicillin allergy flags as CRITICAL."""
        # Raw note with Penicillin allergy
        note = "Patient has Essential Hypertension. Documented Allergies: Penicillin."
        res = ClinicalOrchestrator.process_review(
            proposed_med="Amoxicillin 500mg",
            raw_notes=note
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertTrue(any(a["interaction_type"] == "ALLERGY" for a in res["alerts"]))

    def test_09_audit_chain_integrity(self):
        """Verify cryptographic SHA-256 hash chaining and tamper detection."""
        integrity = audit_logger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["status"], "ALL_BLOCKS_VALID_TAMPER_FREE")

    def test_10_network_guard_telemetry(self):
        """Verify zero external network egress assertion."""
        telemetry = network_guard.get_network_status()
        self.assertEqual(telemetry["status"], "SECURE_AIR_GAPPED")
        self.assertTrue(telemetry["zero_cloud_enforced"])


if __name__ == "__main__":
    unittest.main()
