"""
MediVault Local - Ingestion Package (Person B)
Zero-cloud HIPAA & DPDP compliant clinical record ingestion and PII redaction.
"""

from .pipeline import (
    process_file,
    extract_text,
    redact_phi,
    extract_entities,
    extract_lab_biomarkers,
    ingest_record,
)

__all__ = [
    "process_file",
    "extract_text",
    "redact_phi",
    "extract_entities",
    "extract_lab_biomarkers",
    "ingest_record",
]
