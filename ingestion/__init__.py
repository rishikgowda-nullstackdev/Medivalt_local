"""
MediVault Local - Ingestion & De-Identification Module (Person B)
Zero-Cloud HIPAA Safe Harbor (§ 164.514(b)) and DPDP Act 2023 Compliance.
"""

from ingestion.pipeline import (
    process_file,
    extract_text,
    redact_phi,
    extract_lab_biomarkers,
    extract_entities,
    process_clinical_note
)

__all__ = [
    "process_file",
    "extract_text",
    "redact_phi",
    "extract_lab_biomarkers",
    "extract_entities",
    "process_clinical_note"
]
