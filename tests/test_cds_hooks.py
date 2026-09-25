"""
MediVault Local - HL7 CDS Hooks v1.0 & Sovereign Optical QR Automated Test Suite
Tests:
- GET /cds-services discovery catalog
- POST /cds-services/medication-prescribe evaluation cards & 1-click suggestions
- GET /api/report/clearance-qr vector SVG QR generation
- POST /api/export/fhir-bundle cryptographic clearance bundle export
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.orchestrator import ClinicalOrchestrator


class TestCdsHooks(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Create a sample review event for QR and bundle tests
        self.review = ClinicalOrchestrator.run_review(
            proposed_med="Ibuprofen",
            patient_id="PT-101"
        )
        self.event_id = self.review["event_id"]

    def test_cds_discovery_endpoint(self):
        """Verify official HL7 CDS Hooks discovery endpoint."""
        res = self.client.get("/cds-services")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("services", data)
        self.assertGreater(len(data["services"]), 0)
        service = data["services"][0]
        self.assertEqual(service["hook"], "medication-prescribe")
        self.assertEqual(service["id"], "medication-prescribe")

    def test_cds_evaluate_medication_prescribe_critical(self):
        """Verify CDS evaluation generates cards with 1-click suggestions for contraindicated drug."""
        payload = {
            "hook": "medication-prescribe",
            "hookInstance": "550e8400-e29b-41d4-a716-446655440000",
            "context": {
                "patientId": "EHR-9988",
                "draftOrders": {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "MedicationRequest",
                                "medicationCodeableConcept": {
                                    "coding": [{"code": "5640", "system": "http://www.nlm.nih.gov/research/umls/rxnorm"}]
                                }
                            }
                        }
                    ]
                }
            },
            "prefetch": {
                "patient": {
                    "resourceType": "Patient",
                    "id": "EHR-9988",
                    "gender": "male",
                    "birthDate": "1960-01-01"
                },
                "conditions": {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Condition",
                                "code": {"coding": [{"code": "N18.3", "system": "http://hl7.org/fhir/sid/icd-10"}]}
                            }
                        }
                    ]
                }
            }
        }
        res = self.client.post("/cds-services/medication-prescribe", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cards", data)
        self.assertGreater(len(data["cards"]), 0)
        card = data["cards"][0]
        self.assertEqual(card["indicator"], "critical")
        self.assertIn("suggestions", card)
        self.assertGreater(len(card["suggestions"]), 0)
        suggestion = card["suggestions"][0]
        self.assertIn("actions", suggestion)
        self.assertEqual(suggestion["actions"][0]["type"], "delete")

    def test_cds_evaluate_medication_prescribe_cleared(self):
        """Verify CDS evaluation returns info card when medication is cleared."""
        payload = {
            "hook": "medication-prescribe",
            "context": {
                "patientId": "EHR-1234",
                "draftOrders": {
                    "resourceType": "MedicationRequest",
                    "medicationCodeableConcept": {
                        "text": "Acetaminophen"
                    }
                }
            },
            "prefetch": {}
        }
        res = self.client.post("/cds-services/medication-prescribe", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cards", data)
        card = data["cards"][0]
        self.assertEqual(card["indicator"], "info")

    def test_get_clearance_qr(self):
        """Verify vector SVG QR code generation for wireless optical air-gap transfer."""
        res = self.client.get(f"/api/report/clearance-qr?event_id={self.event_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "image/svg+xml")
        svg_content = res.text
        self.assertTrue("<svg" in svg_content)
        self.assertTrue("</svg>" in svg_content)

    def test_export_fhir_bundle(self):
        """Verify cryptographic FHIR R4 Bundle export."""
        res = self.client.post(f"/api/export/fhir-bundle?event_id={self.event_id}")
        self.assertEqual(res.status_code, 200)
        bundle = res.json()
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "document")
        self.assertGreater(len(bundle["entry"]), 0)
        self.assertEqual(bundle["entry"][0]["resource"]["resourceType"], "Composition")


if __name__ == "__main__":
    unittest.main()
