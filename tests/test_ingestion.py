import re
from pathlib import Path

import pytest

from ingestion.extractor import extract_text
from ingestion.pipeline import ingest_record
from ingestion.redactor import PHONE_RE, SSN_RE, redact_pii

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
TXT_FILES = sorted(SAMPLES.glob("*.txt"))


def test_samples_exist():
    assert TXT_FILES, "no .txt files found in /samples"


def test_patient_1_known_pii_removed():
    out = ingest_record(SAMPLES / "patient_1_ckd_discharge.txt")
    for leaked in ["Robert Vance", "08/14/1958", "111-22-3333", "(555) 432-8765", "Jonathan Miller"]:
        assert leaked not in out, f"LEAK: {leaked}"


def test_patient_1_medical_content_survives():
    out = ingest_record(SAMPLES / "patient_1_ckd_discharge.txt")
    for kept in ["Chronic Kidney Disease", "Metformin", "Lisinopril", "66-year-old"]:
        assert kept in out, f"over-redacted: {kept}"


@pytest.mark.parametrize("f", TXT_FILES, ids=lambda p: p.name)
def test_no_ssn_or_phone_left_in_any_sample(f):
    out = ingest_record(f)
    assert not SSN_RE.search(out)
    assert not PHONE_RE.search(out)
    assert "[REDACTED]" in out


def test_no_pii_unchanged():
    t = "Stage 3 CKD, Metformin 500mg PO BID, creatinine 2.1 mg/dL"
    assert redact_pii(t) == t


def test_empty():
    assert redact_pii("") == ""


def test_labels_preserved():
    out = redact_pii("PATIENT NAME: Robert Vance | DOB: 08/14/1958 | MRN: 4892014")
    assert out == "PATIENT NAME: [REDACTED] | DOB: [REDACTED] | MRN: [REDACTED]"


def test_address_with_commas():
    out = redact_pii("ADDRESS: 742 Evergreen Terrace, Springfield, IL 62704 | X: 1")
    assert out == "ADDRESS: [REDACTED] | X: 1"


def test_unsupported_type(tmp_path):
    f = tmp_path / "x.docx"
    f.write_text("hi")
    with pytest.raises(ValueError):
        extract_text(f)


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text("nope.txt")
