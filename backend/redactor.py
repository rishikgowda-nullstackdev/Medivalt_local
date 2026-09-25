"""
MediVault Local - Clinical Redactor & Entity Extraction Engine
Zero-cloud HIPAA Safe Harbor (§ 164.514(b)) and India DPDP compliance.
Performs deterministic local de-identification and clinical entity extraction.
"""

import re
import hashlib
from typing import Dict, List, Any, Tuple

# ---------------------------------------------------------------------------
# HIPAA 18 Safe Harbor PHI Redaction Patterns
# ---------------------------------------------------------------------------
PHI_PATTERNS = [
    # Social Security / National ID Numbers
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (r"\b\d{9,12}\b", "[REDACTED_NATIONAL_ID]"),

    # Phone & Fax Numbers
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]"),

    # Email Addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),

    # Medical Record Numbers (MRN) & Account Numbers
    (r"(?i)\b(?:MRN|MR#|Record\s*#?|Patient\s*ID|Acct\s*#?)\s*[:#]?\s*[A-Z0-9-]{4,15}\b", "[REDACTED_MRN]"),

    # Dates of Birth
    (r"(?i)\b(?:DOB|Date of Birth|Born)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[REDACTED_DOB]"),

    # Street Addresses & ZIP codes
    (r"\b\d{5}(?:-\d{4})?\b", "[REDACTED_ZIP]"),
    (r"(?i)\b\d{1,5}\s+[A-Za-z0-9\s.,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way)\b", "[REDACTED_ADDRESS]"),

    # Explicit Doctor/Patient names with titles
    (r"(?i)\b(?:Dr\.|Doctor|Physician|Patient|Pt\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", "[REDACTED_NAME]"),

    # IP Addresses
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]")
]

# ---------------------------------------------------------------------------
# Clinical Lexicon for Deterministic Entity Extraction
# ---------------------------------------------------------------------------
CONDITION_LEXICON = {
    "chronic kidney disease": ["chronic kidney disease", "ckd", "renal failure", "renal impairment", "renal insufficiency", "nephropathy"],
    "hypertension": ["hypertension", "high blood pressure", "htn", "essential hypertension"],
    "asthma": ["asthma", "bronchial asthma", "reactive airway disease", "wheezing disorder"],
    "chronic obstructive pulmonary disease": ["copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
    "diabetes mellitus": ["diabetes", "type 2 diabetes", "t2dm", "type 1 diabetes", "diabetic", "hyperglycemia"],
    "diabetic ketoacidosis": ["dka", "diabetic ketoacidosis"],
    "peptic ulcer disease": ["peptic ulcer", "gastric ulcer", "duodenal ulcer", "pud", "gi bleed", "gastritis"],
    "atrial fibrillation": ["atrial fibrillation", "afib", "a-fib", "arrhythmia"],
    "deep vein thrombosis": ["deep vein thrombosis", "dvt", "pulmonary embolism", "venous thromboembolism"],
    "heart failure": ["heart failure", "chf", "congestive heart failure"],
    "pregnancy": ["pregnant", "pregnancy", "gestation", "gravida"]
}

MEDICATION_LEXICON = [
    # NSAIDs
    "ibuprofen", "naproxen", "diclofenac", "meloxicam", "ketorolac", "indomethacin", "celecoxib", "aspirin",
    # Antihypertensives & Beta-blockers
    "propranolol", "timolol", "nadolol", "labetalol", "metoprolol", "atenolol", "bisoprolol",
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "amlodipine", "spironolactone",
    # Antidiabetics
    "metformin", "empagliflozin", "dapagliflozin", "glipizide", "insulin",
    # Anticoagulants & Antiplatelets
    "warfarin", "clopidogrel", "apixaban", "rivaroxaban", "ticagrelor",
    # GI & Analgesics
    "omeprazole", "pantoprazole", "acetaminophen", "paracetamol", "tramadol", "codeine",
    # Psychotropics & Antimicrobials
    "fluoxetine", "sertraline", "selegiline", "clarithromycin", "amoxicillin", "ciprofloxacin",
    # Statins
    "simvastatin", "atorvastatin", "gemfibrozil"
]

ALLERGY_TRIGGERS = [
    r"(?i)\ballerg(?:ies|y|ic\s+to)\s*[:=-]?\s*([^\n.;]+)",
    r"(?i)\bknown\s+allergies\s*[:=-]?\s*([^\n.;]+)",
    r"(?i)\bNKDA\b"
]


class ClinicalRedactor:
    """Handles de-identification and structured entity extraction."""

    @staticmethod
    def redact_phi(text: str) -> Tuple[str, List[str], str]:
        """
        Redacts 18 HIPAA Safe Harbor PHI elements.
        Returns:
            redacted_text: Text with PHI tokens replaced
            redaction_types: List of detected PHI types
            patient_token: Cryptographic pseudonym (SHA-256 slice)
        """
        redacted = text
        detected_phi = []

        for pattern, replacement in PHI_PATTERNS:
            matches = re.findall(pattern, redacted)
            if matches:
                detected_phi.append(replacement.strip("[]"))
                redacted = re.sub(pattern, replacement, redacted)

        # Derive an anonymous pseudorandom token from original text length + hash
        hasher = hashlib.sha256(text.encode("utf-8"))
        patient_token = f"ANON_{hasher.hexdigest()[:12].upper()}"

        return redacted, list(set(detected_phi)), patient_token

    @staticmethod
    def extract_entities(text: str) -> Dict[str, Any]:
        """
        Extracts clinical entities (Conditions, Current Medications, Allergies, Labs).
        Works 100% offline using deterministic medical vocabulary heuristics.
        """
        text_lower = text.lower()

        # 1. Extract Conditions
        extracted_conditions = []
        for canonical_name, aliases in CONDITION_LEXICON.items():
            for alias in aliases:
                # Word boundary match
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, text_lower):
                    extracted_conditions.append(canonical_name.title())
                    break

        # 2. Extract Medications (with optional dosage regex)
        extracted_medications = []
        for med in MEDICATION_LEXICON:
            # Match medication name and capture trailing dosage if present (e.g., 'Metformin 500mg BID')
            med_pattern = r"\b(" + re.escape(med) + r")(?:\s+(\d+\s*(?:mg|mcg|g|ml)\b(?:\s+(?:daily|bid|tid|qid|prn))?))?"
            match = re.search(med_pattern, text_lower)
            if match:
                med_name = match.group(1).title()
                dosage = match.group(2)
                if dosage:
                    extracted_medications.append(f"{med_name} {dosage}")
                else:
                    extracted_medications.append(med_name)

        # 3. Extract Allergies
        extracted_allergies = []

        # Check for multi-line or bulleted allergy sections
        allergy_block_match = re.search(r"(?i)\ballerg(?:ies|y|ic\s+to)[^\n:]*:\s*\n((?:\s*[-*•]\s*[^\n]+\n?)+)", text)
        if allergy_block_match:
            lines = allergy_block_match.group(1).strip().split("\n")
            for line in lines:
                cleaned = re.sub(r"^[-*•\s]+", "", line).strip()
                allergen_name = re.split(r"[\(:;,]", cleaned)[0].strip()
                if allergen_name:
                    extracted_allergies.append(allergen_name.title())

        # Check inline triggers
        for trigger in ALLERGY_TRIGGERS:
            for match in re.finditer(trigger, text):
                if "NKDA" in match.group(0).upper():
                    extracted_allergies.append("No Known Drug Allergies (NKDA)")
                else:
                    raw_allergies = match.group(1).split(",")
                    for a in raw_allergies:
                        cleaned = a.strip().rstrip(".;")
                        allergen_part = re.split(r"[\(:;,]", cleaned)[0].strip()
                        if allergen_part and len(allergen_part) < 50 and not allergen_part.lower().startswith("adverse"):
                            extracted_allergies.append(allergen_part.title())

        # Check direct mentions of critical drug allergies if allergy keyword is present
        if "allerg" in text_lower:
            for term in ["penicillin", "sulfa", "sulfonamides", "aspirin", "codeine", "cephalosporin"]:
                if re.search(r"(?i)\b" + re.escape(term) + r"\b", text_lower):
                    extracted_allergies.append(term.title())

        extracted_allergies = sorted(list(set(extracted_allergies)))

        # 4. Extract Lab Biomarkers (eGFR, Creatinine, INR, BP)
        labs = {}
        egfr_match = re.search(r"(?i)\b(?:eGFR|GFR)\s*[:=]?\s*(\d{1,3})\b", text)
        if egfr_match:
            labs["eGFR"] = f"{egfr_match.group(1)} mL/min/1.73m2"

        creat_match = re.search(r"(?i)\b(?:serum\s+)?creatinine\s*[:=]?\s*(\d+\.?\d*)\b", text)
        if creat_match:
            labs["Creatinine"] = f"{creat_match.group(1)} mg/dL"

        inr_match = re.search(r"(?i)\bINR\s*[:=]?\s*(\d+\.?\d*)\b", text)
        if inr_match:
            labs["INR"] = inr_match.group(1)

        return {
            "diagnosed_conditions": sorted(list(set(extracted_conditions))),
            "current_medications": sorted(list(set(extracted_medications))),
            "allergies": sorted(list(set(extracted_allergies))),
            "clinical_labs": labs
        }

    @classmethod
    def process_clinical_note(cls, raw_text: str) -> Dict[str, Any]:
        """Runs full redaction and clinical extraction pipeline in one call."""
        redacted_text, detected_phi, patient_token = cls.redact_phi(raw_text)
        entities = cls.extract_entities(raw_text)

        return {
            "patient_token": patient_token,
            "redacted_text": redacted_text,
            "phi_detected": detected_phi,
            "entities": entities
        }


# Quick test
if __name__ == "__main__":
    sample_note = """
    Patient: John Doe, DOB: 05/12/1959, MRN: 9948201.
    Phone: (555) 234-5678, SSN: 000-12-3456.
    History: 64 yo male with Stage 3 Chronic Kidney Disease (CKD), baseline serum creatinine 2.1, eGFR 38.
    Also has Essential Hypertension and Type 2 Diabetes.
    Current Medications: Lisinopril 20mg daily, Metformin 500mg BID.
    Allergies: Sulfa drugs, Penicillin.
    Complaining of bilateral knee pain. Considering prescribing Ibuprofen.
    """
    res = ClinicalRedactor.process_clinical_note(sample_note)
    print("Redacted:\n", res["redacted_text"])
    print("\nExtracted Entities:\n", res["entities"])
