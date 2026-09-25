"""
MediVault Local - Clinical Clearance Certificate Test Suite
Verifies:
1. Prescription review creates valid audit log entry with event_id.
2. GET /api/report/clearance?event_id=... generates HTML certificate.
3. Certificate includes physician NPI, hospital name, patient pseudonym, and SHA-256 seal.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app


class TestClinicalCertificate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_generate_and_fetch_certificate(self):
        """Execute review, retrieve event_id, and generate printable certificate."""
        res_review = self.client.post("/api/review", json={
            "patient_id": "PT-101",
            "proposed_medication": "Ibuprofen 400mg"
        })
        self.assertEqual(res_review.status_code, 200)
        review_data = res_review.json()

        event_id = review_data.get("event_id")
        self.assertIsNotNone(event_id)
        self.assertTrue(event_id.startswith("EVT_"))

        # Fetch certificate
        res_cert = self.client.get(f"/api/report/clearance?event_id={event_id}")
        self.assertEqual(res_cert.status_code, 200)
        self.assertIn("text/html", res_cert.headers["content-type"])

        html_text = res_cert.text
        self.assertIn("Clinical Clearance Certificate", html_text)
        self.assertIn(event_id, html_text)
        self.assertIn("Dr. Gregory House, MD", html_text)
        self.assertIn("Princeton Plainsboro Teaching Hospital", html_text)
        self.assertIn("HIPAA SAFE HARBOR § 164.514(b)", html_text)
        self.assertIn("RECORD SHA-256 SEAL", html_text)
        self.assertIn(review_data["audit_hash"], html_text)

    def test_02_nonexistent_event_id_returns_404(self):
        """Requesting certificate for non-existent event returns 404."""
        res = self.client.get("/api/report/clearance?event_id=EVT_NONEXISTENT_9999999")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
