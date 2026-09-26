"""
MediVault Local - Ingestion & De-Identification Module (Person B)
Zero-Cloud HIPAA Safe Harbor (§ 164.514(b)) and DPDP Act 2023 Compliance.
Performs in-memory document parsing, local PHI de-identification,
clinical entity extraction, quantitative lab biomarker analysis,
and sovereign hospital interoperability parsing (FHIR R4, HL7 v2, optical QR).
"""

from .pipeline import (
    process_file,
    extract_text,
    redact_phi,
    redact_pii,
    extract_lab_biomarkers,
    extract_entities,
    process_clinical_note,
    resolve_medical_ontology,
    parse_fhir_bundle,
    parse_hl7_v2,
    parse_optical_qr_payload,
    ingest_record,
)

__all__ = [
    "process_file",
    "extract_text",
    "redact_phi",
    "redact_pii",
    "extract_lab_biomarkers",
    "extract_entities",
    "process_clinical_note",
    "resolve_medical_ontology",
    "parse_fhir_bundle",
    "parse_hl7_v2",
    "parse_optical_qr_payload",
    "ingest_record",
]
