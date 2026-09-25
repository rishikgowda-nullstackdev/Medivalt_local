"""
MediVault Local - Interoperability & Medical Ontology Automated Test Suite
Tests:
- FHIR R4 Bundle parsing
- HL7 v2.x pipe-delimited parsing
- Optical QR compressed payload decompression
- Medical Ontology Crosswalk (RxNorm, ICD-10-CM, LOINC)
- POST /api/ingest/interop endpoint
"""

import json
import zlib
import base64
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from ingestion.pipeline import (
    parse_fhir_bundle,
    parse_hl7_v2,
    parse_optical_qr_payload,
    resolve_medical_ontology
)


class TestInteroperability(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_ontology_crosswalk_rxnorm(self):
        """Verify RxNorm CUI code resolution to canonical generic drug."""
        res = resolve_medical_ontology("RXNORM", "5640")
        self.assertIsNotNone(res)
        self.assertEqual(res["canonical_entity"], "ibuprofen")
        self.assertEqual(res["category"], "DRUG")

        res_gab = resolve_medical_ontology("RXNORM", "25480")
        self.assertIsNotNone(res_gab)
        self.assertEqual(res_gab["canonical_entity"], "gabapentin")

    def test_ontology_crosswalk_icd10(self):
        """Verify ICD-10-CM disease code resolution."""
        res = resolve_medical_ontology("ICD10", "N18.3")
        self.assertIsNotNone(res)
        self.assertEqual(res["canonical_entity"], "chronic kidney disease")
        self.assertEqual(res["category"], "DISEASE")

    def test_ontology_crosswalk_loinc(self):
        """Verify LOINC lab biomarker code resolution."""
        res_egfr = resolve_medical_ontology("LOINC", "33914-3")
        self.assertIsNotNone(res_egfr)
        self.assertEqual(res_egfr["canonical_entity"], "egfr")

        res_cr = resolve_medical_ontology("LOINC", "2160-0")
        self.assertIsNotNone(res_cr)
        self.assertEqual(res_cr["canonical_entity"], "creatinine")

    def test_parse_fhir_bundle(self):
        """Verify offline parsing of FHIR R4 Bundle."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "FHIR-PAT-001",
                        "gender": "female",
                        "birthDate": "1948-05-12"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"coding": [{"code": "2160-0", "system": "http://loinc.org"}]},
                        "valueQuantity": {"value": 1.9, "unit": "mg/dL"}
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"coding": [{"code": "29463-7", "system": "http://loinc.org"}]},
                        "valueQuantity": {"value": 52.0, "unit": "kg"}
                    }
                },
                {
                    "resource": {
                        "resourceType": "Condition",
                        "code": {"coding": [{"code": "N18.3", "system": "http://hl7.org/fhir/sid/icd-10"}]}
                    }
                },
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "medicationCodeableConcept": {"coding": [{"code": "29046", "system": "http://www.nlm.nih.gov/research/umls/rxnorm"}]}
                    }
                }
            ]
        }
        parsed = parse_fhir_bundle(bundle)
        self.assertTrue(parsed["patient_token"].startswith("ANON_"))
        self.assertEqual(parsed["demographics"]["gender"], "female")
        self.assertGreater(parsed["demographics"]["age"], 65)
        self.assertEqual(parsed["demographics"]["weight_kg"], 52.0)
        self.assertIn("chronic kidney disease", parsed["entities"]["diagnosed_conditions"])
        self.assertIn("lisinopril", parsed["entities"]["current_medications"])
        self.assertIn("creatinine", parsed["entities"]["biomarkers"])
        self.assertEqual(parsed["entities"]["biomarkers"]["creatinine"]["value"], 1.9)

    def test_parse_hl7_v2(self):
        """Verify offline parsing of HL7 v2.x pipe-delimited message."""
        hl7_msg = (
            "MSH|^~\\&|EPIC|HOSPITAL|MEDIVAULT|LOCAL|20260925120000||ORM^O01|MSG001|P|2.5\n"
            "PID|1||MRN98765^^^HOSP||DOE^JANE||19500315|F\n"
            "DG1|1||N18.3^Chronic kidney disease stage 3^I10\n"
            "OBX|1|NM|2160-0^Creatinine^LN||1.7|mg/dL|||||F\n"
            "OBX|2|NM|29463-7^Weight^LN||55.0|kg|||||F\n"
            "RXE|1|29046^Lisinopril^RXNORM||20|mg||QD\n"
            "AL1|1|DA|^Penicillin\n"
        )
        parsed = parse_hl7_v2(hl7_msg)
        self.assertTrue(parsed["patient_token"].startswith("ANON_"))
        self.assertEqual(parsed["demographics"]["gender"], "female")
        self.assertGreater(parsed["demographics"]["age"], 65)
        self.assertEqual(parsed["demographics"]["weight_kg"], 55.0)
        self.assertIn("chronic kidney disease", parsed["entities"]["diagnosed_conditions"])
        self.assertIn("lisinopril", parsed["entities"]["current_medications"])
        self.assertIn("Penicillin", parsed["entities"]["allergies"])
        self.assertIn("creatinine", parsed["entities"]["biomarkers"])

    def test_parse_optical_qr_compressed(self):
        """Verify decompression and parsing of Base64+zlib optical QR payload."""
        payload = {
            "patient_id": "QR-9901",
            "age": 75,
            "gender": "male",
            "weight": 70.0,
            "conditions": ["chronic kidney disease"],
            "medications": ["metformin"],
            "labs": {"creatinine": {"value": 2.2, "unit": "mg/dL"}}
        }
        compressed_b64 = base64.b64encode(zlib.compress(json.dumps(payload).encode())).decode()
        parsed = parse_optical_qr_payload(compressed_b64)
        self.assertTrue(parsed.get("optical_qr_verified"))
        self.assertEqual(parsed["demographics"]["age"], 75)
        self.assertIn("chronic kidney disease", parsed["entities"]["diagnosed_conditions"])

    def test_api_ingest_interop_endpoint(self):
        """Test POST /api/ingest/interop endpoint."""
        hl7_msg = (
            "MSH|^~\\&|TEST\n"
            "PID|1||MRN123||TEST^PATIENT||19600101|M\n"
            "DG1|1||I10^Hypertension^I10\n"
            "RXE|1|5640^Ibuprofen^RXNORM||400|mg\n"
        )
        res = self.client.post("/api/ingest/interop", data={"raw_payload": hl7_msg})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["format"], "HL7_V2")
        self.assertIn("hypertension", data["entities"]["diagnosed_conditions"])
        self.assertIn("ibuprofen", data["entities"]["current_medications"])


if __name__ == "__main__":
    unittest.main()
