"""
MediVault Local - Automated Integration Test Suite
Verifies offline redaction, extraction, database queries, contraindication flags, and audit hashing.
"""

import os
import sys
import unittest

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.redactor import ClinicalRedactor
from backend.main import get_db, record_audit_log, ReviewRequest, review_prescription


class TestMediVaultLocal(unittest.TestCase):

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

    def test_03_ckd_nsaid_contraindication(self):
        """Verify that prescribing Ibuprofen to a CKD patient triggers a CRITICAL flag."""
        req = ReviewRequest(patient_id="PT-101", proposed_medication="Ibuprofen")
        res = review_prescription(req)

        self.assertEqual(res.overall_status, "CRITICAL")
        self.assertGreater(res.total_alerts, 0)
        self.assertTrue(any("Chronic Kidney Disease" in a.conflicting_factor for a in res.alerts))
        self.assertTrue(res.zero_cloud_verified)
        self.assertIsNotNone(res.audit_hash)

    def test_04_asthma_beta_blocker_contraindication(self):
        """Verify that prescribing Propranolol to an Asthma patient triggers a CRITICAL flag."""
        req = ReviewRequest(patient_id="PT-102", proposed_medication="Propranolol")
        res = review_prescription(req)

        self.assertEqual(res.overall_status, "CRITICAL")
        self.assertTrue(any("Asthma" in a.conflicting_factor for a in res.alerts))

    def test_05_warfarin_aspirin_interaction(self):
        """Verify that prescribing Aspirin to a Warfarin patient triggers a CRITICAL bleeding warning."""
        req = ReviewRequest(patient_id="PT-103", proposed_medication="Aspirin")
        res = review_prescription(req)

        self.assertEqual(res.overall_status, "CRITICAL")
        self.assertTrue(any("Warfarin" in a.conflicting_factor for a in res.alerts))

    def test_06_safe_prescription(self):
        """Verify that a safe, non-contraindicated antibiotic triggers a SAFE response."""
        req = ReviewRequest(patient_id="PT-101", proposed_medication="Amoxicillin")
        res = review_prescription(req)

        self.assertEqual(res.overall_status, "SAFE")
        self.assertEqual(res.total_alerts, 0)

    def test_07_cryptographic_audit_trail(self):
        """Verify SHA-256 hash chaining in the local audit log."""
        hash1 = record_audit_log("ANON_TEST1", "Ibuprofen", "CRITICAL", 1, 15.2)
        hash2 = record_audit_log("ANON_TEST2", "Amoxicillin", "SAFE", 0, 8.4)

        self.assertEqual(len(hash1), 64)
        self.assertEqual(len(hash2), 64)
        self.assertNotEqual(hash1, hash2)


if __name__ == "__main__":
    unittest.main()
