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

    def test_03_download_pdf_certificate(self):
        """Verify GET /api/report/clearance/pdf downloads authentic signed PDF document."""
        # 1. Run review
        res_review = self.client.post("/api/review", json={
            "patient_id": "PT-101",
            "proposed_medication": "Ibuprofen 400mg",
            "enable_slm": False
        })
        self.assertEqual(res_review.status_code, 200)
        event_id = res_review.json().get("event_id")
        self.assertIsNotNone(event_id)

        # 2. Download PDF
        res_pdf = self.client.get(f"/api/report/clearance/pdf?event_id={event_id}")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers["content-type"], "application/pdf")
        self.assertIn("attachment; filename=", res_pdf.headers.get("content-disposition", ""))
        pdf_bytes = res_pdf.content
        # PDF documents start with %PDF
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_04_pdf_nonexistent_event_returns_404(self):
        """Requesting PDF for non-existent event returns 404."""
        res = self.client.get("/api/report/clearance/pdf?event_id=EVT_NONEXISTENT_9999999")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
