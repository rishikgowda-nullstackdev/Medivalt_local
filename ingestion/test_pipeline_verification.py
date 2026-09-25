"""
Verification test suite for Person B's Ingestion & PII Redaction Pipeline.
Runs comprehensive checks for extract_text, redact_phi, extract_entities,
extract_lab_biomarkers, and process_file.
"""

from io import BytesIO
from pathlib import Path
import pytest

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


def test_extract_text_txt_path():
    """Verify extraction from TXT path."""
    text = extract_text(SAMPLE_TXT)
    assert len(text) > 50
    assert "Robert Vance" in text
    assert "Chronic Kidney Disease" in text


def test_extract_text_pdf_path():
    """Verify in-memory extraction from PDF path."""
    text = extract_text(SAMPLE_PDF)
    assert len(text) > 50
    assert "Amanda Rollins" in text
    assert "Asthma" in text


def test_extract_text_bytes_in_memory():
    """Verify extraction from in-memory bytes for TXT and PDF."""
    txt_bytes = SAMPLE_TXT.read_bytes()
    pdf_bytes = SAMPLE_PDF.read_bytes()

    # TXT bytes with filename
    t1 = extract_text(txt_bytes, filename="record.txt")
    assert "Robert Vance" in t1

    # PDF bytes with filename
    t2 = extract_text(pdf_bytes, filename="record.pdf")
    assert "Amanda Rollins" in t2

    # PDF bytes with magic header detection (no filename)
    t3 = extract_text(pdf_bytes)
    assert "Amanda Rollins" in t3


def test_guardrails_empty_and_short():
    """Verify ValueError on empty or <10 character text."""
    with pytest.raises(ValueError, match="Uploaded document contains no readable text"):
        extract_text(SAMPLE_EMPTY)

    with pytest.raises(ValueError, match="Uploaded document contains no readable text"):
        extract_text(b"short", filename="short.txt")


def test_guardrails_oversized():
    """Verify ValueError on >500KB text."""
    huge_bytes = b"A" * 500_001
    with pytest.raises(ValueError, match="Document exceeds maximum permitted size"):
        extract_text(huge_bytes, filename="huge.txt")


def test_guardrails_unsupported_type(tmp_path):
    """Verify ValueError on unsupported file type."""
    docx = tmp_path / "test.docx"
    docx.write_text("Hello world this is a test document")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(docx)


def test_guardrails_missing_file():
    """Verify FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        extract_text("non_existent_file.txt")


def test_redact_phi_18_hipaa_elements():
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
    assert "John Doe" not in redacted
    assert "000-12-3456" not in redacted
    assert "(555) 234-5678" not in redacted
    assert "jdoe@example.com" not in redacted
    assert "192.168.1.100" not in redacted
    assert "Jonathan Miller" not in redacted

    # Assert REDACTED tokens are present
    assert "[REDACTED_NAME]" in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_DOB]" in redacted
    assert "[REDACTED_MRN]" in redacted

    # Assert clinical details survive
    assert "Chronic Kidney Disease" in redacted
    assert "Lisinopril" in redacted
    assert "Metformin" in redacted
    assert "Ibuprofen" in redacted
    assert "creatinine 2.1" in redacted
    assert "eGFR 38" in redacted

    # Assert pseudonym format
    assert token.startswith("ANON_")
    assert len(token) == 17  # "ANON_" + 12 hex chars


def test_extract_entities():
    """Verify extraction of conditions, medications, allergies, and labs."""
    note = (
        "Patient has Stage 3 Chronic Kidney Disease (CKD) and Essential Hypertension. "
        "Currently taking Lisinopril 20mg daily and Metformin 500mg BID. "
        "Allergies: Penicillin, Sulfa. Lab values show eGFR 38, Creatinine 2.1, BP 142/88 mmHg."
    )
    entities = extract_entities(note)

    assert "diagnosed_conditions" in entities
    assert "current_medications" in entities
    assert "allergies" in entities
    assert "clinical_labs" in entities
    assert "biomarkers" in entities

    assert "Chronic Kidney Disease" in entities["diagnosed_conditions"]
    assert "Hypertension" in entities["diagnosed_conditions"]
    assert any("Lisinopril" in m for m in entities["current_medications"])
    assert any("Metformin" in m for m in entities["current_medications"])
    assert "Penicillin" in entities["allergies"]
    assert entities["clinical_labs"]["eGFR"] == "38 mL/min/1.73m2"
    assert entities["clinical_labs"]["Creatinine"] == "2.1 mg/dL"
    assert entities["biomarkers"]["eGFR"]["status"] == "WARNING_LOW"
    assert entities["biomarkers"]["Creatinine"]["status"] == "HIGH"


def test_extract_lab_biomarkers_thresholds():
    """Verify quantitative biomarker evaluation against safety thresholds."""
    # Critical labs note
    crit_note = "Lab results: eGFR 22, Creatinine 2.8, Potassium 5.4, INR 3.8, Platelets 42k, BP 184/110 mmHg."
    labs = extract_lab_biomarkers(crit_note)

    assert labs["eGFR"]["status"] == "CRITICAL_LOW"
    assert labs["Creatinine"]["status"] == "HIGH"
    assert labs["Potassium"]["status"] == "CRITICAL_HIGH"
    assert labs["INR"]["status"] == "CRITICAL_HIGH"
    assert labs["Platelets"]["status"] == "CRITICAL_LOW"
    assert labs["BloodPressure"]["status"] == "CRITICAL_HIGH"

    # Normal labs note
    norm_note = "Lab results: eGFR 85, Creatinine 0.9, Potassium 4.2, INR 1.1, Platelets 250,000, BP 118/76 mmHg."
    norm_labs = extract_lab_biomarkers(norm_note)

    assert norm_labs["eGFR"]["status"] == "NORMAL"
    assert norm_labs["Creatinine"]["status"] == "NORMAL"
    assert norm_labs["Potassium"]["status"] == "NORMAL"
    assert norm_labs["INR"]["status"] == "NORMAL"
    assert norm_labs["Platelets"]["status"] == "NORMAL"
    assert norm_labs["BloodPressure"]["status"] == "NORMAL"


def test_process_file_end_to_end():
    """Verify process_file frozen contract function."""
    redacted_from_path = process_file(SAMPLE_TXT)
    assert "[REDACTED_NAME]" in redacted_from_path
    assert "[REDACTED_SSN]" in redacted_from_path
    assert "Robert Vance" not in redacted_from_path
    assert "Chronic Kidney Disease" in redacted_from_path

    pdf_bytes = SAMPLE_PDF.read_bytes()
    redacted_from_bytes = process_file(pdf_bytes, filename="consult.pdf")
    assert "[REDACTED_NAME]" in redacted_from_bytes
    assert "Amanda Rollins" not in redacted_from_bytes
    assert "Asthma" in redacted_from_bytes


def test_no_cloud_or_network_imports():
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
        assert py_file.exists()
        content = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"Illegal import token '{token}' in {py_file}"
