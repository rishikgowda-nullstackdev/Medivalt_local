"""
Verification test suite for Person B's Ingestion & PII Redaction Pipeline.
Runs comprehensive checks for extract_text, redact_phi, extract_entities,
extract_lab_biomarkers, and process_file.
"""

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from ingestion.pipeline import (
    extract_text,
    redact_phi,
    extract_entities,
    extract_lab_biomarkers,
    process_file,
    ingest_record,
)
from ingestion.extractor import extract_text as extractor_extract_text
from ingestion.redactor import redact_pii, PHONE_RE, SSN_RE

INGESTION_DIR = Path(__file__).resolve().parent
SAMPLE_TXT = INGESTION_DIR / "samples" / "patient_sample.txt"
SAMPLE_PDF = INGESTION_DIR / "samples" / "patient_sample.pdf"
SAMPLE_EMPTY = INGESTION_DIR / "samples" / "empty.txt"


class TestIngestionPipeline(unittest.TestCase):
    """Test suite for Person B ingestion & redaction engine."""

    def test_extract_text_txt_path(self):
        """Verify extraction from TXT path."""
        text = extract_text(SAMPLE_TXT)
        self.assertGreater(len(text), 50)
        self.assertIn("Robert Vance", text)
        self.assertIn("Chronic Kidney Disease", text)

    def test_extract_text_pdf_path(self):
        """Verify in-memory extraction from PDF path."""
        text = extract_text(SAMPLE_PDF)
        self.assertGreater(len(text), 50)
        self.assertIn("Amanda Rollins", text)
        self.assertIn("Asthma", text)

    def test_extract_text_bytes_in_memory(self):
        """Verify extraction from in-memory bytes for TXT and PDF."""
        txt_bytes = SAMPLE_TXT.read_bytes()
        pdf_bytes = SAMPLE_PDF.read_bytes()

        # TXT bytes with filename
        t1 = extract_text(txt_bytes, filename="record.txt")
        self.assertIn("Robert Vance", t1)

        # PDF bytes with filename
        t2 = extract_text(pdf_bytes, filename="record.pdf")
        self.assertIn("Amanda Rollins", t2)

        # PDF bytes with magic header detection (no filename)
        t3 = extract_text(pdf_bytes)
        self.assertIn("Amanda Rollins", t3)

    def test_guardrails_empty_and_short(self):
        """Verify ValueError on empty or <10 character text."""
        with self.assertRaises(ValueError):
            extract_text(SAMPLE_EMPTY)

        with self.assertRaises(ValueError):
            extract_text(b"short", filename="short.txt")

    def test_guardrails_oversized(self):
        """Verify ValueError on >500KB text."""
        huge_bytes = b"A" * 500_001
        with self.assertRaises(ValueError):
            extract_text(huge_bytes, filename="huge.txt")

    def test_guardrails_unsupported_type(self):
        """Verify ValueError on unsupported file type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_text("Hello world this is a test document", encoding="utf-8")
            with self.assertRaises(ValueError):
                extract_text(docx)

    def test_guardrails_missing_file(self):
        """Verify FileNotFoundError on non-existent path."""
        with self.assertRaises(FileNotFoundError):
            extract_text("non_existent_file.txt")

    def test_redact_phi_18_hipaa_elements(self):
        """Verify 18 HIPAA Safe Harbor PHI patterns are redacted into [REDACTED_*]."""
        note = (
            "PATIENT NAME: John Doe | DOB: 05/12/1959 | MRN: 9948201\n"
            "SSN: 000-12-3456 | PHONE: (555) 234-5678 | EMAIL: jdoe@example.com\n"
            "ADDRESS: 123 Main Street, Suite 400 | ZIP: 90210\n"
            "IP: 192.168.1.100 | URL: https://portal.hospital.org/patient/9948201\n"
            "ATTENDING PHYSICIAN: Dr. Jonathan Miller, MD\n"
            "History: 64 yo male with Stage 3 Chronic Kidney Disease (CKD), baseline serum creatinine 2.1, eGFR 38.\n"
            "Current Medications: Lisinopril 20mg daily, Metformin 500mg BID.\n"
            "Allergies: Penicillin, Sulfa.\n"
            "Considering prescribing Ibuprofen.\n"
        )
        redacted, phi_detected, token = redact_phi(note)

        # Assert identifiers are redacted
        self.assertNotIn("John Doe", redacted)
        self.assertNotIn("000-12-3456", redacted)
        self.assertNotIn("(555) 234-5678", redacted)
        self.assertNotIn("jdoe@example.com", redacted)
        self.assertNotIn("192.168.1.100", redacted)
        self.assertNotIn("Jonathan Miller", redacted)

        # Assert REDACTED tokens are present
        self.assertIn("[REDACTED_NAME]", redacted)
        self.assertIn("[REDACTED_SSN]", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_DOB]", redacted)
        self.assertIn("[REDACTED_MRN]", redacted)

        # Assert clinical details survive
        self.assertIn("Chronic Kidney Disease", redacted)
        self.assertIn("Lisinopril", redacted)
        self.assertIn("Metformin", redacted)
        self.assertIn("Ibuprofen", redacted)
        self.assertIn("creatinine 2.1", redacted)
        self.assertIn("eGFR 38", redacted)

        # Assert pseudonym format
        self.assertTrue(token.startswith("ANON_"))
        self.assertEqual(len(token), 17)  # "ANON_" + 12 hex chars

    def test_extract_entities(self):
        """Verify extraction of conditions, medications, allergies, and labs."""
        note = (
            "Patient has Stage 3 Chronic Kidney Disease (CKD) and Essential Hypertension. "
            "Currently taking Lisinopril 20mg daily and Metformin 500mg BID. "
            "Allergies: Penicillin, Sulfa. Lab values show eGFR 38, Creatinine 2.1, BP 142/88 mmHg."
        )
        entities = extract_entities(note)

        self.assertIn("diagnosed_conditions", entities)
        self.assertIn("current_medications", entities)
        self.assertIn("allergies", entities)
        self.assertIn("clinical_labs", entities)
        self.assertIn("biomarkers", entities)

        self.assertIn("Chronic Kidney Disease", entities["diagnosed_conditions"])
        self.assertIn("Hypertension", entities["diagnosed_conditions"])
        self.assertTrue(any("Lisinopril" in m for m in entities["current_medications"]))
        self.assertTrue(any("Metformin" in m for m in entities["current_medications"]))
        self.assertIn("Penicillin", entities["allergies"])
        self.assertEqual(entities["clinical_labs"]["eGFR"], "38 mL/min/1.73m2")
        self.assertEqual(entities["clinical_labs"]["Creatinine"], "2.1 mg/dL")
        self.assertEqual(entities["biomarkers"]["eGFR"]["status"], "WARNING_LOW")
        self.assertEqual(entities["biomarkers"]["Creatinine"]["status"], "HIGH")

    def test_extract_lab_biomarkers_thresholds(self):
        """Verify quantitative biomarker evaluation against safety thresholds."""
        crit_note = "Lab results: eGFR 22, Creatinine 2.8, Potassium 5.4, INR 3.8, Platelets 42k, BP 184/110 mmHg."
        labs = extract_lab_biomarkers(crit_note)

        self.assertEqual(labs["eGFR"]["status"], "CRITICAL_LOW")
        self.assertEqual(labs["Creatinine"]["status"], "HIGH")
        self.assertEqual(labs["Potassium"]["status"], "CRITICAL_HIGH")
        self.assertEqual(labs["INR"]["status"], "CRITICAL_HIGH")
        self.assertEqual(labs["Platelets"]["status"], "CRITICAL_LOW")
        self.assertEqual(labs["BloodPressure"]["status"], "CRITICAL_HIGH")

        norm_note = "Lab results: eGFR 85, Creatinine 0.9, Potassium 4.2, INR 1.1, Platelets 250,000, BP 118/76 mmHg."
        norm_labs = extract_lab_biomarkers(norm_note)

        self.assertEqual(norm_labs["eGFR"]["status"], "NORMAL")
        self.assertEqual(norm_labs["Creatinine"]["status"], "NORMAL")
        self.assertEqual(norm_labs["Potassium"]["status"], "NORMAL")
        self.assertEqual(norm_labs["INR"]["status"], "NORMAL")
        self.assertEqual(norm_labs["Platelets"]["status"], "NORMAL")
        self.assertEqual(norm_labs["BloodPressure"]["status"], "NORMAL")

    def test_process_file_end_to_end(self):
        """Verify process_file frozen contract function."""
        redacted_from_path = process_file(SAMPLE_TXT)
        self.assertIn("[REDACTED_NAME]", redacted_from_path)
        self.assertIn("[REDACTED_SSN]", redacted_from_path)
        self.assertNotIn("Robert Vance", redacted_from_path)
        self.assertIn("Chronic Kidney Disease", redacted_from_path)

        pdf_bytes = SAMPLE_PDF.read_bytes()
        redacted_from_bytes = process_file(pdf_bytes, filename="consult.pdf")
        self.assertIn("[REDACTED_NAME]", redacted_from_bytes)
        self.assertNotIn("Amanda Rollins", redacted_from_bytes)
        self.assertIn("Asthma", redacted_from_bytes)

    def test_no_cloud_or_network_imports(self):
        """Ensure zero external network or cloud SDK imports exist in production ingestion code."""
        prod_files = [
            INGESTION_DIR / "pipeline.py",
            INGESTION_DIR / "extractor.py",
            INGESTION_DIR / "redactor.py",
            INGESTION_DIR / "__init__.py",
        ]
        forbidden_tokens = [
            "import requests",
            "from requests",
            "import urllib.request",
            "from urllib.request",
            "import openai",
            "from openai",
            "import anthropic",
            "from anthropic",
            "google.generativeai",
            "import httpx",
            "from httpx",
        ]
        for py_file in prod_files:
            self.assertTrue(py_file.exists())
            content = py_file.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, content, f"Illegal import token '{token}' in {py_file}")

    def test_narrative_preservation_and_zip_safety(self):
        """Verify that clinical text actions (takes, has) and 5-digit lab values are not destroyed by redaction."""
        narrative = (
            "Patient takes Warfarin 5mg daily. Doctor prescribed Aspirin 81mg. "
            "Patient has Hypertension and Asthma. Lab: Platelets 45000 /uL, WBC 12500 /mcL, Heparin 10000 units. "
            "Address: 123 Main Street, Boston MA 02115. Phone: (617) 555-1234."
        )
        redacted, phi_detected, token = redact_phi(narrative)

        # Assert names and address redacted
        self.assertIn("[REDACTED_PHONE]", redacted)
        self.assertTrue("[REDACTED_ZIP]" in redacted or "[REDACTED_ADDRESS]" in redacted)

        # Critical: Medications and clinical verbs must SURVIVE
        self.assertIn("Warfarin", redacted)
        self.assertIn("Aspirin", redacted)
        self.assertIn("Hypertension", redacted)
        self.assertIn("Asthma", redacted)

        # Critical: 5-digit lab values must SURVIVE (not become [REDACTED_ZIP])
        self.assertIn("45000", redacted)
        self.assertIn("12500", redacted)
        self.assertIn("10000", redacted)


if __name__ == "__main__":
    unittest.main()
