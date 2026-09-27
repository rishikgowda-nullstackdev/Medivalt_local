"""
MediVault Local - Offline OCR Engine & Sovereign Ingestion Tests
Tests sovereign optical character recognition from scanned paper prescriptions,
photographed clinical notes, and image-based PDF lab records.
Validates zero-cloud on-device extraction, HIPAA PII redaction, and API multipart endpoints.
"""

import os
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from ingestion.ocr import is_ocr_available, extract_text_from_image_bytes, extract_text_from_scanned_pdf
from ingestion.extractor import extract_text
from ingestion.pipeline import process_file, extract_prescription_bundle

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "samples"


class TestOfflineOCR(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.rx_img_path = SAMPLES_DIR / "scanned_prescription_slip.png"
        cls.lab_img_path = SAMPLES_DIR / "scanned_lab_slip.png"
        cls.scanned_pdf_path = SAMPLES_DIR / "scanned_paper_record.pdf"

        # Ensure sample fixtures exist
        if not cls.rx_img_path.exists() or not cls.lab_img_path.exists() or not cls.scanned_pdf_path.exists():
            from samples.make_scanned_images import generate_all_samples
            generate_all_samples()

    def test_01_ocr_engine_available(self):
        """Verifies that local ONNX OCR engine and dependencies are available."""
        self.assertTrue(is_ocr_available(), "RapidOCR engine should be installed and available.")

    def test_02_extract_text_from_prescription_image(self):
        """Tests sovereign text extraction from a scanned paper prescription PNG."""
        img_bytes = self.rx_img_path.read_bytes()
        text = extract_text_from_image_bytes(img_bytes)

        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 30)

        # Check for clinical terms
        text_lower = text.lower()
        self.assertTrue(
            any(w in text_lower for w in ["lisinopril", "furosemide", "ibuprofen"]),
            f"Expected medications in OCR text, got:\n{text}"
        )

    def test_03_extract_text_from_scanned_pdf(self):
        """Tests OCR fallback on a scanned image PDF containing no digital font layer."""
        pdf_bytes = self.scanned_pdf_path.read_bytes()
        text = extract_text_from_scanned_pdf(pdf_bytes)

        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 30)

        text_lower = text.lower()
        self.assertTrue(
            any(k in text_lower for k in ["egfr", "creatinine", "kidney", "warfarin", "potassium"]),
            f"Expected lab biomarkers in scanned PDF OCR text, got:\n{text}"
        )

    def test_04_extractor_pipeline_image_dispatch(self):
        """Verifies that extract_text() transparently routes image paths and bytes to OCR."""
        # A: File path
        text_from_path = extract_text(self.rx_img_path)
        self.assertIn("Lisinopril", text_from_path)

        # B: In-memory bytes with filename
        img_bytes = self.rx_img_path.read_bytes()
        text_from_bytes = extract_text(img_bytes, filename="paper_prescription.png")
        self.assertIn("Lisinopril", text_from_bytes)

        # C: Scanned PDF path
        text_from_scanned_pdf = extract_text(self.scanned_pdf_path)
        self.assertTrue("egfr" in text_from_scanned_pdf.lower() or "creatinine" in text_from_scanned_pdf.lower())

    def test_05_safe_harbor_redaction_on_ocr_text(self):
        """Verifies that HIPAA/DPDP PII redaction runs on OCR text, stripping names/phones while keeping clinical items."""
        redacted = process_file(self.rx_img_path)

        # Direct identifiers must be redacted
        self.assertNotIn("Jonathan Doe", redacted)
        self.assertNotIn("555-019-8234", redacted)

        # Clinical drugs must be preserved
        redacted_lower = redacted.lower()
        self.assertTrue("lisinopril" in redacted_lower)
        self.assertTrue("ibuprofen" in redacted_lower)

    def test_06_prescription_bundle_extraction_from_image(self):
        """Tests parsing structured multi-drug prescription orders directly from a paper scan."""
        bundle = extract_prescription_bundle(self.rx_img_path)

        self.assertIn("prescriptions", bundle)
        prescriptions = bundle["prescriptions"]
        self.assertGreaterEqual(len(prescriptions), 1)

        extracted_drugs = [p["medication"].lower() for p in prescriptions]
        self.assertTrue(
            any(d in extracted_drugs for d in ["lisinopril", "furosemide", "ibuprofen"]),
            f"Expected medications in parsed bundle: {extracted_drugs}"
        )

    def test_07_api_upload_record_image_endpoint(self):
        """Tests POST /api/upload-record with a scanned lab slip image."""
        with open(self.lab_img_path, "rb") as f:
            response = self.client.post(
                "/api/upload-record",
                files={"file": ("scanned_lab_slip.png", f, "image/png")}
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("redacted_text", data)
        self.assertTrue(data.get("ocr_performed"))
        self.assertEqual(data.get("extraction_mode"), "Sovereign On-Device OCR (RapidOCR)")

        # Verify clinical entities were extracted from image
        entities = data.get("entities", {})
        self.assertTrue(
            len(entities.get("diagnosed_conditions", [])) > 0 or len(entities.get("clinical_labs", {})) > 0,
            f"Expected entities extracted from image, got: {entities}"
        )

    def test_08_api_upload_prescription_image_endpoint(self):
        """Tests POST /api/upload-prescription with a scanned prescription slip."""
        with open(self.rx_img_path, "rb") as f:
            response = self.client.post(
                "/api/upload-prescription",
                files={"file": ("scanned_prescription_slip.png", f, "image/png")}
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ocr_performed"))
        self.assertIn("prescriptions", data)
        self.assertGreaterEqual(len(data["prescriptions"]), 1)

    def test_09_corrupted_image_handling(self):
        """Verifies that corrupted image bytes fail gracefully with a 400 error rather than crashing."""
        corrupt_bytes = b"\x89PNG\r\n\x1a\nNOT_A_REAL_IMAGE_DATA_CORRUPTED"
        response = self.client.post(
            "/api/upload-record",
            files={"file": ("corrupt.png", corrupt_bytes, "image/png")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Failed to extract text from scanned image", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
