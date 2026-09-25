"""
MediVault Local - Clinical PII/PHI Redactor (Person B)
Deterministic 18 HIPAA Safe Harbor and India DPDP de-identification engine.
Replaces sensitive patient identifiers with [REDACTED_*] tokens while strictly
preserving clinical data, biomarkers, lab values, diagnoses, and medication regimens.
"""

import hashlib
import re
from typing import List, Tuple

REDACTED = "[REDACTED]"

# Value delimiters for labeled fields:
# Preserve trailing whitespace before separators like |, newline, or semicolon
_VAL_NO_COMMA = r"[^|,\n;]*[^|,\s;]"
_VAL_WITH_COMMA = r"[^|\n;]*[^|\s;]"

# Legacy Day-3 labeled patterns (replace with [REDACTED])
LABELED_PATTERNS_PII = [
    (re.compile(rf"(?i)(\bpatient(?:\s+name)?\s*:\s*){_VAL_NO_COMMA}"), r"\1[REDACTED]"),
    (re.compile(rf"(?i)(\b(?:attending|referring|consulting)?\s*(?:physician|cardiologist|doctor|dr\.?)\s*:\s*){_VAL_WITH_COMMA}"), r"\1[REDACTED]"),
    (re.compile(rf"(?i)(\b(?:dob|date\s+of\s+birth)\s*:\s*){_VAL_NO_COMMA}"), r"\1[REDACTED]"),
    (re.compile(rf"(?i)(\b(?:mrn|medical\s+record\s+(?:number|no\.?))\s*:\s*){_VAL_NO_COMMA}"), r"\1[REDACTED]"),
    (re.compile(rf"(?i)(\baddress\s*:\s*){_VAL_WITH_COMMA}"), r"\1[REDACTED]"),
]

# Legacy regexes exported for test_ingestion.py
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?(?:1|91)[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
)


def redact_pii(text: str) -> str:
    """
    Legacy Day 3 PII redaction function returning [REDACTED] tokens.
    Maintained for backward compatibility with test_ingestion.py.
    """
    if not text:
        return text or ""
    for pattern, repl in LABELED_PATTERNS_PII:
        text = pattern.sub(repl, text)
    text = SSN_RE.sub(REDACTED, text)
    text = PHONE_RE.sub(REDACTED, text)
    return text


# ---------------------------------------------------------------------------
# 18 HIPAA Safe Harbor Identifiers (§ 164.514(b)) Patterns
# ---------------------------------------------------------------------------
PHI_LABELED_RULES = [
    # 1. Patient and Provider Names
    (r"(?i)(\bpatient(?:\s+name)?\s*:\s*)" + _VAL_NO_COMMA, r"\1[REDACTED_NAME]", "REDACTED_NAME"),
    (r"(?i)(\b(?:attending|referring|consulting)?\s*(?:physician|cardiologist|doctor|dr\.?)\s*:\s*)" + _VAL_WITH_COMMA, r"\1[REDACTED_NAME]", "REDACTED_NAME"),

    # 2. Date of Birth
    (r"(?i)(\b(?:dob|date\s+of\s+birth|born)\s*[:#]?\s*)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", r"\1[REDACTED_DOB]", "REDACTED_DOB"),
    (r"(?i)(\b(?:dob|date\s+of\s+birth|born)\s*[:#]?\s*)\d{4}-\d{2}-\d{2}", r"\1[REDACTED_DOB]", "REDACTED_DOB"),

    # 3. Medical Record Number (MRN)
    (r"(?i)(\b(?:mrn|medical\s+record\s+(?:number|no\.?)|patient\s*id)\s*[:#]?\s*)[A-Z0-9-]{3,15}", r"\1[REDACTED_MRN]", "REDACTED_MRN"),

    # 4. Street Address
    (r"(?i)(\b(?:address|addr)\s*[:#]?\s*)" + _VAL_WITH_COMMA, r"\1[REDACTED_ADDRESS]", "REDACTED_ADDRESS"),

    # 5. Phone / Fax numbers
    (r"(?i)(\b(?:phone|telephone|tel|cell|mobile)\s*[:#]?\s*)" + _VAL_NO_COMMA, r"\1[REDACTED_PHONE]", "REDACTED_PHONE"),
    (r"(?i)(\b(?:fax|facsimile)\s*[:#]?\s*)" + _VAL_NO_COMMA, r"\1[REDACTED_FAX]", "REDACTED_FAX"),

    # 6. Social Security / National ID
    (r"(?i)(\bssn\s*[:#]?\s*)\d{3}-?\d{2}-?\d{4}", r"\1[REDACTED_SSN]", "REDACTED_SSN"),
    (r"(?i)(\b(?:national\s*id|aadhaar|gov\s*id)\s*[:#]?\s*)(?:[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}|[0-9]{9,12})", r"\1[REDACTED_NATIONAL_ID]", "REDACTED_NATIONAL_ID"),

    # 7. Health Plan Beneficiary / Insurance ID
    (r"(?i)(\b(?:health\s*plan|insurance|policy|beneficiary)\s*(?:id|#|no\.?)\s*[:#]?\s*)[A-Z0-9-]{6,16}", r"\1[REDACTED_HEALTH_PLAN]", "REDACTED_HEALTH_PLAN"),

    # 8. Account Numbers
    (r"(?i)(\b(?:account|acct|billing)\s*(?:#|no\.?|id)?\s*[:#]?\s*)[A-Z0-9-]{6,16}", r"\1[REDACTED_ACCOUNT]", "REDACTED_ACCOUNT"),

    # 9. Certificate / License Numbers (DEA, NPI)
    (r"(?i)(\b(?:certificate|license|dea|npi|reg)\s*(?:#|no\.?|id)?\s*[:#]?\s*)[A-Z0-9-]{6,16}", r"\1[REDACTED_LICENSE]", "REDACTED_LICENSE"),

    # 10. Vehicle Identifiers
    (r"(?i)(\b(?:vin|license\s*plate|plate\s*#?)\s*[:#]?\s*)[A-Z0-9-]{5,17}", r"\1[REDACTED_VEHICLE]", "REDACTED_VEHICLE"),

    # 11. Device Identifiers / Serial Numbers
    (r"(?i)(\b(?:device\s*id|serial\s*#?|device\s*s/n)\s*[:#]?\s*)[A-Z0-9-]{6,20}", r"\1[REDACTED_DEVICE]", "REDACTED_DEVICE"),

    # 12. Biometric Identifiers
    (r"(?i)(\b(?:biometric(?:\s*id)?|fingerprint|retinal\s*scan|iris\s*scan)\s*[:#]?\s*)[A-Za-z0-9+/=]{8,}", r"\1[REDACTED_BIOMETRIC]", "REDACTED_BIOMETRIC"),
]

# Pattern-based matching across unstructured text
PHI_PATTERNS = [
    # Social Security / National ID Numbers
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (r"(?<![.\d])\d{9,12}(?![.\d])", "[REDACTED_NATIONAL_ID]"),

    # Phone Numbers (US & International)
    (r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)", "[REDACTED_PHONE]"),
    (r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)", "[REDACTED_PHONE]"),
    (r"\b\d{3}\.\d{3}\.\d{4}\b", "[REDACTED_PHONE]"),

    # Email Addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),

    # Medical Record Numbers (MRN) & Account Numbers
    (r"(?i)\b(?:MRN|MR#|Record\s*#?|Patient\s*ID|Acct\s*#?)\s*[:#]?\s*[A-Z0-9-]{4,15}\b", "[REDACTED_MRN]"),

    # Dates of Birth
    (r"(?i)\b(?:DOB|Date of Birth|Born)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[REDACTED_DOB]"),
    (r"(?i)\b(?:DOB|Date of Birth|Born)\s*[:#]?\s*\d{4}-\d{2}-\d{2}\b", "[REDACTED_DOB]"),

    # Street Addresses & ZIP codes
    (r"\b\d{5}(?:-\d{4})?\b", "[REDACTED_ZIP]"),
    (r"(?i)\b\d{1,5}\s+[A-Za-z0-9\s.,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way)\b", "[REDACTED_ADDRESS]"),

    # Explicit Doctor/Patient names with titles
    (r"(?i)\b(Dr\.|Doctor|Physician|Patient|Pt\.?)\s+(?!name\b|id\b|mrn\b|dob\b)[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", r"\1 [REDACTED_NAME]"),

    # IP Addresses
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]"),

    # Web URLs
    (r"\bhttps?://[^\s<>\"]+|www\.[^\s<>\"]+\b", "[REDACTED_URL]"),
]


def redact_phi(text: str) -> Tuple[str, List[str], str]:
    """
    Redacts 18 HIPAA Safe Harbor PHI identifiers into [REDACTED_*] tokens.

    Returns:
        redacted_text: Text with PHI replaced by [REDACTED_*] tokens
        detected_phi: List of detected PHI category strings
        patient_token: Pseudonym derived from SHA-256 hash (e.g. ANON_4A9B1C2D3E4F)
    """
    if not text:
        return "", [], "ANON_EMPTY"

    redacted = text
    detected_phi = []

    # 1. Apply labeled PHI rules (highest precision)
    for pattern, repl, token_name in PHI_LABELED_RULES:
        if re.search(pattern, redacted):
            detected_phi.append(token_name)
            redacted = re.sub(pattern, repl, redacted)

    # 2. Apply pattern-based rules (for unstructured identifiers)
    for pattern, replacement in PHI_PATTERNS:
        matches = re.findall(pattern, redacted)
        if matches:
            token_clean = replacement.strip("[]")
            if token_clean.startswith(r"\1 "):
                token_clean = token_clean.split(" ")[-1].strip("[]")
            detected_phi.append(token_clean)
            redacted = re.sub(pattern, replacement, redacted)

    # 3. Derive cryptographic pseudonym
    hasher = hashlib.sha256(text.encode("utf-8"))
    patient_token = f"ANON_{hasher.hexdigest()[:12].upper()}"

    return redacted, sorted(list(set(detected_phi))), patient_token
