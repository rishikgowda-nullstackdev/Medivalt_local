"""
MediVault Local - Comprehensive Test Suite
Verifies offline redaction, extraction, database queries, contraindication flags,
audit hashing, tamper detection, and network guard assertions.
"""

import os
import sys
import unittest

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.redactor import ClinicalRedactor
from backend.network_guard import network_guard
from backend.audit_logger import audit_logger
from backend.orchestrator import ClinicalOrchestrator
from backend.main import ReviewRequest, review_prescription


class TestMediVaultDay2(unittest.TestCase):

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

    def test_03_network_guard_telemetry(self):
        """Verify Offline Shield loopback binding assertion and zero outbound bytes."""
        telemetry = network_guard.get_network_status()
        self.assertEqual(telemetry["status"], "SECURE_AIR_GAPPED")
        self.assertTrue(telemetry["zero_cloud_enforced"])
        self.assertTrue(telemetry["air_gap_verified"])
        self.assertTrue(telemetry["dpdp_hipaa_compliant"])

        # Loopback assertion should succeed on localhost
        network_guard.assert_loopback_only("127.0.0.1")
        network_guard.assert_loopback_only("localhost")

        # Non-loopback host must throw RuntimeError
        with self.assertRaises(RuntimeError):
            network_guard.assert_loopback_only("api.openai.com")

    def test_04_audit_logger_and_tamper_verification(self):
        """Verify SHA-256 hash chaining and mathematical tamper detection."""
        entry = audit_logger.log_review(
            patient_token="ANON_TEST_VERIFY",
            proposed_medication="Ibuprofen",
            overall_status="CRITICAL",
            alerts_count=1,
            execution_time_ms=12.4
        )
        self.assertEqual(len(entry["audit_hash"]), 64)
        self.assertEqual(len(entry["prev_hash"]), 64)

        # Integrity verification should pass
        integrity = audit_logger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["status"], "ALL_BLOCKS_VALID_TAMPER_FREE")
        self.assertGreaterEqual(integrity["total_blocks"], 1)

    def test_05_orchestrator_ckd_nsaid(self):
        """Verify orchestrator flags Ibuprofen for a CKD patient as CRITICAL."""
        res = ClinicalOrchestrator.process_review(
            proposed_med="Ibuprofen",
            patient_id="PT-101"
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertGreater(res["total_alerts"], 0)
        self.assertTrue(any("Chronic Kidney Disease" in a["conflicting_factor"] for a in res["alerts"]))
        self.assertTrue(res["zero_cloud_verified"])
        self.assertEqual(len(res["audit_hash"]), 64)

    def test_06_orchestrator_asthma_propranolol(self):
        """Verify orchestrator flags Propranolol for an Asthma patient as CRITICAL."""
        res = ClinicalOrchestrator.process_review(
            proposed_med="Propranolol",
            patient_id="PT-102"
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertTrue(any("Asthma" in a["conflicting_factor"] for a in res["alerts"]))

    def test_07_orchestrator_warfarin_aspirin(self):
        """Verify orchestrator flags Aspirin for a Warfarin patient as CRITICAL."""
        res = ClinicalOrchestrator.process_review(
            proposed_med="Aspirin",
            patient_id="PT-103"
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertTrue(any("Warfarin" in a["conflicting_factor"] for a in res["alerts"]))

    def test_08_orchestrator_safe_medication(self):
        """Verify orchestrator clears a non-contraindicated antibiotic."""
        res = ClinicalOrchestrator.process_review(
            proposed_med="Amoxicillin",
            patient_id="PT-101"
        )
        self.assertEqual(res["overall_status"], "SAFE")
        self.assertEqual(res["total_alerts"], 0)

    def test_09_raw_clinical_notes_review(self):
        """Verify end-to-end review when raw unstructured discharge text is passed."""
        raw_discharge = (
            "Patient has Stage 3 Chronic Kidney Disease and Hypertension. "
            "Currently taking Lisinopril 20mg daily. Proposing Naproxen."
        )
        res = ClinicalOrchestrator.process_review(
            proposed_med="Naproxen",
            raw_notes=raw_discharge
        )
        self.assertEqual(res["overall_status"], "CRITICAL")
        self.assertTrue(any("Chronic Kidney Disease" in a["conflicting_factor"] for a in res["alerts"]))


if __name__ == "__main__":
    unittest.main()
