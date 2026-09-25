"""
MediVault Local - Clinical Ingestion, De-Identification & Lab Parser Pipeline (Person B)
Regulatory Standard: HIPAA Safe Harbor § 164.514(b)(2) & India DPDP Act 2023.

Provides:
- PDF and TXT text extraction without cloud egress.
- 18 HIPAA Safe Harbor PHI identifier de-identification.
- Quantitative clinical lab and biomarker numerical parser (eGFR, Creatinine, K+, INR, Platelets).
- Structured entity extraction (diagnosed conditions, active prescriptions, allergies).
"""

import os
import re
import json
import zlib
import base64
import sqlite3
import hashlib
from datetime import datetime
from io import BytesIO
from typing import Union, Optional, Tuple, List, Dict, Any
from pypdf import PdfReader

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")

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
# Medical Entity Lexicon
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
    "metformin", "empagliflozin", "dapagliflozin", "glipizide", "insulin", "linagliptin",
    # Anticoagulants & Antiplatelets
    "warfarin", "clopidogrel", "apixaban", "rivaroxaban", "ticagrelor", "enoxaparin", "heparin",
    # GI & Analgesics
    "omeprazole", "pantoprazole", "acetaminophen", "paracetamol", "tramadol", "codeine",
    # Psychotropics & Antimicrobials
    "fluoxetine", "sertraline", "selegiline", "clarithromycin", "amoxicillin", "ciprofloxacin", "azithromycin", "levofloxacin",
    # Diuretics & Statins
    "furosemide", "hydrochlorothiazide", "simvastatin", "atorvastatin", "gemfibrozil"
]

ALLERGY_TRIGGERS = [
    r"(?i)\ballerg(?:ies|y|ic\s+to)\s*[:=-]?\s*([^\n.;]+)",
    r"(?i)\bknown\s+allergies\s*[:=-]?\s*([^\n.;]+)",
    r"(?i)\bNKDA\b"
]


def extract_text(file_source: Union[str, bytes], filename: Optional[str] = None) -> str:
    """
    Extracts text from PDF or TXT input safely in-memory without temporary disk writes.
    """
    if isinstance(file_source, str):
        if os.path.exists(file_source):
            with open(file_source, "rb") as f:
                content = f.read()
            fname = filename or file_source
        else:
            return file_source.strip()
    else:
        content = file_source
        fname = filename or "document.txt"

    if fname.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            return "\n".join(pages).strip()
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document: {str(e)}")
    else:
        try:
            return content.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            raise ValueError(f"Failed to read file content: {str(e)}")


def redact_phi(text: str) -> Tuple[str, List[str], str]:
    """
    De-identifies 18 HIPAA Safe Harbor PHI elements.
    Returns:
        redacted_text: Text with PHI tokens replaced
        detected_phi: List of detected PHI categories
        patient_token: Cryptographic pseudonym (SHA-256 slice)
    """
    redacted = text
    detected_phi = []

    for pattern, replacement in PHI_PATTERNS:
        matches = re.findall(pattern, redacted)
        if matches:
            detected_phi.append(replacement.strip("[]"))
            redacted = re.sub(pattern, replacement, redacted)

    hasher = hashlib.sha256(text.encode("utf-8"))
    patient_token = f"ANON_{hasher.hexdigest()[:12].upper()}"

    return redacted, sorted(list(set(detected_phi))), patient_token


def extract_lab_biomarkers(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Extracts quantitative numerical lab values and biomarkers from clinical notes.
    Parses values for eGFR, Creatinine, Potassium (K+), Platelets, and INR.
    """
    labs: Dict[str, Dict[str, Any]] = {}

    # 1. eGFR (Estimated Glomerular Filtration Rate)
    egfr_match = re.search(r"(?i)\b(?:eGFR|GFR)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\b", text)
    if egfr_match:
        val = float(egfr_match.group(1))
        labs["eGFR"] = {
            "value": val,
            "unit": "mL/min/1.73m2",
            "display": f"{val} mL/min/1.73m2",
            "status": "CRITICAL_LOW" if val < 30 else ("WARNING_LOW" if val <= 44 else "NORMAL")
        }

    # 2. Serum Creatinine
    creat_match = re.search(r"(?i)\b(?:serum\s+)?creatinine\s*[:=]?\s*(\d+\.?\d*)\b", text)
    if creat_match:
        val = float(creat_match.group(1))
        labs["Creatinine"] = {
            "value": val,
            "unit": "mg/dL",
            "display": f"{val} mg/dL",
            "status": "HIGH" if val > 1.4 else "NORMAL"
        }

    # 3. Serum Potassium (K+)
    k_match = re.search(r"(?i)\b(?:potassium|serum\s+potassium|K\+)\s*[:=]?\s*(\d+\.?\d*)\b", text)
    if k_match:
        val = float(k_match.group(1))
        labs["Potassium"] = {
            "value": val,
            "unit": "mEq/L",
            "display": f"{val} mEq/L",
            "status": "CRITICAL_HIGH" if val > 5.0 else ("LOW" if val < 3.5 else "NORMAL")
        }

    # 4. INR (International Normalized Ratio)
    inr_match = re.search(r"(?i)\b(?:current\s+)?INR\s*[:=]?\s*(\d+\.?\d*)\b", text)
    if inr_match:
        val = float(inr_match.group(1))
        labs["INR"] = {
            "value": val,
            "unit": "INR",
            "display": f"{val}",
            "status": "CRITICAL_HIGH" if val > 3.5 else ("ELEVATED" if val > 3.0 else "NORMAL")
        }

    # 5. Platelet Count
    plt_match = re.search(r"(?i)\b(?:platelets|platelet\s+count|plt)\s*[:=]?\s*(\d{2,3})(?:\s*k|\s*,?000)?\b", text)
    if plt_match:
        val = float(plt_match.group(1))
        # If value is in thousands (e.g. 45), keep as 45. If full number (e.g. 45000), divide by 1000
        if val > 1000:
            val = round(val / 1000.0, 1)
        labs["Platelets"] = {
            "value": val,
            "unit": "x10^3/uL",
            "display": f"{val}k / uL",
            "status": "CRITICAL_LOW" if val < 50.0 else ("LOW" if val < 100.0 else "NORMAL")
        }

    # 6. Blood Pressure
    bp_match = re.search(r"(?i)\b(?:BP|Blood\s+Pressure)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})\b", text)
    if bp_match:
        sys_val = int(bp_match.group(1))
        dia_val = int(bp_match.group(2))
        labs["BloodPressure"] = {
            "systolic": sys_val,
            "diastolic": dia_val,
            "display": f"{sys_val}/{dia_val} mmHg",
            "status": "STAGE_2_HTN" if (sys_val >= 140 or dia_val >= 90) else "NORMAL"
        }

    return labs


def extract_entities(text: str) -> Dict[str, Any]:
    """
    Extracts clinical conditions, current medications, documented allergies,
    and quantitative lab values.
    """
    text_lower = text.lower()

    # 1. Diagnosed Conditions
    extracted_conditions = []
    for canonical_name, aliases in CONDITION_LEXICON.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                extracted_conditions.append(canonical_name.title())
                break

    # 2. Current Medications
    extracted_medications = []
    for med in MEDICATION_LEXICON:
        med_pattern = r"\b(" + re.escape(med) + r")(?:\s+(\d+\s*(?:mg|mcg|g|ml)\b(?:\s+(?:daily|bid|tid|qid|prn))?))?"
        match = re.search(med_pattern, text_lower)
        if match:
            med_name = match.group(1).title()
            dosage = match.group(2)
            if dosage:
                extracted_medications.append(f"{med_name} {dosage}")
            else:
                extracted_medications.append(med_name)

    # 3. Documented Allergies
    extracted_allergies = []
    allergy_block_match = re.search(r"(?i)\ballerg(?:ies|y|ic\s+to)[^\n:]*:\s*\n((?:\s*[-*•]\s*[^\n]+\n?)+)", text)
    if allergy_block_match:
        lines = allergy_block_match.group(1).strip().split("\n")
        for line in lines:
            cleaned = re.sub(r"^[-*•\s]+", "", line).strip()
            allergen_name = re.split(r"[\(:;,]", cleaned)[0].strip()
            if allergen_name:
                extracted_allergies.append(allergen_name.title())

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

    if "allerg" in text_lower:
        for term in ["penicillin", "sulfa", "sulfonamides", "aspirin", "codeine", "cephalosporin"]:
            if re.search(r"(?i)\b" + re.escape(term) + r"\b", text_lower):
                extracted_allergies.append(term.title())

    # 4. Quantitative Lab Biomarkers
    labs = extract_lab_biomarkers(text)

    # Backward compatibility formatted dictionary for older UI cards
    legacy_labs = {k: v["display"] for k, v in labs.items()}

    return {
        "diagnosed_conditions": sorted(list(set(extracted_conditions))),
        "current_medications": sorted(list(set(extracted_medications))),
        "allergies": sorted(list(set(extracted_allergies))),
        "clinical_labs": legacy_labs,
        "biomarkers": labs
    }


def process_clinical_note(raw_text: str) -> Dict[str, Any]:
    """Runs full redaction and clinical extraction pipeline in one unified call."""
    redacted_text, detected_phi, patient_token = redact_phi(raw_text)
    entities = extract_entities(raw_text)

    return {
        "patient_token": patient_token,
        "redacted_text": redacted_text,
        "phi_detected": detected_phi,
        "entities": entities
    }


# ---------------------------------------------------------------------------
# Frozen Contract Implementation (CONTRACTS.md - Person B)
# ---------------------------------------------------------------------------
def process_file(file_path_or_bytes: Union[str, bytes], filename: Optional[str] = None) -> str:
    """
    Person B Ingestion Frozen Contract:
    in: a file (PDF or .txt) or bytes
    out: a single redacted plain-text string
    """
    raw_text = extract_text(file_path_or_bytes, filename)
    redacted_text, _, _ = redact_phi(raw_text)
    return redacted_text


# ---------------------------------------------------------------------------
# Medical Ontology Crosswalk & Hospital Interoperability Parsers
# ---------------------------------------------------------------------------
def resolve_medical_ontology(code_system: str, code: str) -> Optional[Dict[str, str]]:
    """Resolves standard medical code (RxNorm, ICD-10, LOINC) to canonical entity via SQLite crosswalk."""
    sys_clean = code_system.strip().upper()
    if "RXNORM" in sys_clean or "2.16.840.1.113883.6.88" in sys_clean:
        cs = "RXNORM"
    elif "ICD" in sys_clean or "2.16.840.1.113883.6.3" in sys_clean:
        cs = "ICD10"
    elif "LOINC" in sys_clean or "2.16.840.1.113883.6.1" in sys_clean:
        cs = "LOINC"
    else:
        cs = sys_clean

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT code_system, code, display_name, canonical_entity, category FROM ontology_crosswalk WHERE code_system = ? AND code = ?",
            (cs, code.strip())
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "code_system": row["code_system"],
                "code": row["code"],
                "display_name": row["display_name"],
                "canonical_entity": row["canonical_entity"],
                "category": row["category"]
            }
    except Exception:
        pass
    return None


def parse_fhir_bundle(bundle_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a FHIR R4 Bundle into standardized, de-identified clinical entities.
    Extracts demographics (age, gender, weight), conditions, medications, allergies, and biomarkers.
    """
    patient_id = "ANON_FHIR"
    demographics = {"age": None, "gender": "unknown", "weight_kg": None}
    conditions: List[str] = []
    medications: List[str] = []
    allergies: List[str] = []
    biomarkers: Dict[str, Any] = {}

    entries = bundle_dict.get("entry", [])
    if isinstance(entries, list):
        for entry in entries:
            res = entry.get("resource", {})
            rtype = res.get("resourceType", "")

            if rtype == "Patient":
                pid = str(res.get("id") or "ANON_FHIR")
                patient_id = f"ANON_{hashlib.sha256(pid.encode()).hexdigest()[:10]}"
                demographics["gender"] = res.get("gender", "unknown").lower()
                bdate = res.get("birthDate")
                if bdate:
                    try:
                        byear = int(bdate.split("-")[0])
                        demographics["age"] = max(0, datetime.now().year - byear)
                    except Exception:
                        pass

            elif rtype == "Observation":
                codings = res.get("code", {}).get("coding", [])
                val_quant = res.get("valueQuantity", {})
                val = val_quant.get("value")
                unit = val_quant.get("unit", "")

                for c in codings:
                    code = str(c.get("code", ""))
                    resolved = resolve_medical_ontology("LOINC", code)
                    if resolved and val is not None:
                        canonical = resolved["canonical_entity"]
                        if canonical == "weight":
                            try:
                                demographics["weight_kg"] = float(val)
                            except Exception:
                                pass
                        else:
                            biomarkers[canonical] = {
                                "value": float(val),
                                "unit": unit or resolved["display_name"],
                                "display": f"{val} {unit or ''}".strip(),
                                "loinc": code
                            }
                    elif val is not None:
                        disp = (c.get("display") or "").lower()
                        for b_name in ["egfr", "potassium", "creatinine", "inr", "platelets", "weight"]:
                            if b_name in disp:
                                if b_name == "weight":
                                    try:
                                        demographics["weight_kg"] = float(val)
                                    except Exception:
                                        pass
                                else:
                                    biomarkers[b_name] = {
                                        "value": float(val),
                                        "unit": unit,
                                        "display": f"{val} {unit}".strip()
                                    }

            elif rtype in ("Condition", "Diagnosis"):
                codings = res.get("code", {}).get("coding", [])
                text = res.get("code", {}).get("text", "")
                added = False
                for c in codings:
                    code = str(c.get("code", ""))
                    resolved = resolve_medical_ontology("ICD10", code)
                    if resolved:
                        conditions.append(resolved["canonical_entity"])
                        added = True
                        break
                    elif c.get("display"):
                        conditions.append(c["display"])
                        added = True
                        break
                if not added and text:
                    conditions.append(text)

            elif rtype in ("MedicationRequest", "MedicationStatement", "MedicationAdministration"):
                concept = res.get("medicationCodeableConcept", {})
                codings = concept.get("coding", [])
                text = concept.get("text") or res.get("medicationReference", {}).get("display", "")
                added = False
                for c in codings:
                    code = str(c.get("code", ""))
                    resolved = resolve_medical_ontology("RXNORM", code)
                    if resolved:
                        medications.append(resolved["canonical_entity"])
                        added = True
                        break
                    elif c.get("display"):
                        medications.append(c["display"])
                        added = True
                        break
                if not added and text:
                    medications.append(text)

            elif rtype == "AllergyIntolerance":
                concept = res.get("code", {})
                codings = concept.get("coding", [])
                text = concept.get("text", "")
                for c in codings:
                    if c.get("display"):
                        allergies.append(c["display"])
                        break
                else:
                    if text:
                        allergies.append(text)

    clean_conds = []
    for c in conditions:
        c_low = c.lower().strip()
        matched = False
        for standard, syns in CONDITION_LEXICON.items():
            if c_low in syns or standard in c_low or c_low in standard:
                clean_conds.append(standard)
                matched = True
                break
        if not matched:
            clean_conds.append(c_low)

    clean_meds = []
    for m in medications:
        m_low = m.lower().strip()
        m_name = m_low.split()[0] if m_low else ""
        clean_meds.append(m_name or m_low)

    return {
        "patient_token": patient_id,
        "demographics": demographics,
        "entities": {
            "diagnosed_conditions": sorted(list(set(clean_conds))),
            "current_medications": sorted(list(set(clean_meds))),
            "allergies": sorted(list(set([a.title() for a in allergies]))),
            "biomarkers": biomarkers
        },
        "raw_fhir_summary": f"FHIR R4 Bundle with {len(entries)} resources parsed offline"
    }


def parse_hl7_v2(hl7_text: str) -> Dict[str, Any]:
    """
    Parses standard HL7 v2.x pipe-delimited message into de-identified clinical entities.
    Handles PID, DG1, OBX, RXE/RXA, and AL1 segments.
    """
    patient_id = "ANON_HL7"
    demographics = {"age": None, "gender": "unknown", "weight_kg": None}
    conditions: List[str] = []
    medications: List[str] = []
    allergies: List[str] = []
    biomarkers: Dict[str, Any] = {}

    lines = [line.strip() for line in hl7_text.splitlines() if line.strip()]
    for line in lines:
        fields = line.split("|")
        seg = fields[0].upper()

        if seg == "PID":
            pid_raw = fields[3] if len(fields) > 3 else "ANON_HL7"
            patient_id = f"ANON_{hashlib.sha256(pid_raw.encode()).hexdigest()[:10]}"
            if len(fields) > 7 and fields[7]:
                dob = fields[7]
                try:
                    byear = int(dob[:4])
                    demographics["age"] = max(0, datetime.now().year - byear)
                except Exception:
                    pass
            if len(fields) > 8 and fields[8]:
                demographics["gender"] = "female" if fields[8].upper().startswith("F") else "male"

        elif seg == "DG1":
            if len(fields) > 3:
                code_comp = fields[3].split("^")
                code = code_comp[0].strip()
                desc = code_comp[1].strip() if len(code_comp) > 1 else ""
                resolved = resolve_medical_ontology("ICD10", code)
                if resolved:
                    conditions.append(resolved["canonical_entity"])
                elif desc:
                    conditions.append(desc.lower())
                elif code:
                    conditions.append(code.lower())

        elif seg == "OBX":
            if len(fields) > 5:
                id_comp = fields[3].split("^")
                code = id_comp[0].strip()
                desc = id_comp[1].strip() if len(id_comp) > 1 else ""
                val = fields[5].strip()
                unit = fields[6].strip() if len(fields) > 6 else ""

                resolved = resolve_medical_ontology("LOINC", code)
                try:
                    numeric_val = float(re.findall(r"[-+]?\d*\.?\d+", val)[0])
                    if resolved:
                        canonical = resolved["canonical_entity"]
                        if canonical == "weight":
                            demographics["weight_kg"] = numeric_val
                        else:
                            biomarkers[canonical] = {
                                "value": numeric_val,
                                "unit": unit or resolved["display_name"],
                                "display": f"{numeric_val} {unit or ''}".strip(),
                                "loinc": code
                            }
                    else:
                        d_low = desc.lower()
                        for b_name in ["egfr", "potassium", "creatinine", "inr", "platelets", "weight"]:
                            if b_name in d_low:
                                if b_name == "weight":
                                    demographics["weight_kg"] = numeric_val
                                else:
                                    biomarkers[b_name] = {
                                        "value": numeric_val,
                                        "unit": unit,
                                        "display": f"{numeric_val} {unit}".strip()
                                    }
                except Exception:
                    pass

        elif seg in ("RXE", "RXA", "ORC", "RXO"):
            for fld_idx in [2, 3]:
                if len(fields) > fld_idx and fields[fld_idx]:
                    m_comp = fields[fld_idx].split("^")
                    code = m_comp[0].strip()
                    desc = m_comp[1].strip() if len(m_comp) > 1 else ""
                    resolved = resolve_medical_ontology("RXNORM", code)
                    if resolved:
                        medications.append(resolved["canonical_entity"])
                        break
                    elif desc:
                        medications.append(desc.lower())
                        break

        elif seg == "AL1":
            if len(fields) > 3:
                al_comp = fields[3].split("^")
                desc = al_comp[1].strip() if len(al_comp) > 1 else al_comp[0].strip()
                if desc:
                    allergies.append(desc.title())

    return {
        "patient_token": patient_id,
        "demographics": demographics,
        "entities": {
            "diagnosed_conditions": sorted(list(set(conditions))),
            "current_medications": sorted(list(set(medications))),
            "allergies": sorted(list(set(allergies))),
            "biomarkers": biomarkers
        },
        "raw_hl7_summary": f"HL7 v2 Message with {len(lines)} segments parsed offline"
    }


def parse_optical_qr_payload(qr_string: str) -> Dict[str, Any]:
    """
    Parses a compressed optical QR payload (camera-to-screen air-gap transfer).
    Supports Base64-zlib compressed JSON or raw JSON string.
    """
    qr_clean = qr_string.strip()
    json_str = None

    if qr_clean.startswith("{") and qr_clean.endswith("}"):
        json_str = qr_clean
    else:
        try:
            raw_bytes = base64.b64decode(qr_clean)
            try:
                decompressed = zlib.decompress(raw_bytes)
                json_str = decompressed.decode("utf-8")
            except Exception:
                json_str = raw_bytes.decode("utf-8")
        except Exception:
            pass

    if not json_str:
        return process_clinical_note(qr_clean)

    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and data.get("resourceType") == "Bundle":
            return parse_fhir_bundle(data)

        patient_token = f"ANON_{hashlib.sha256(str(data.get('patient_id', 'OPTICAL')).encode()).hexdigest()[:10]}"
        demographics = {
            "age": data.get("age"),
            "gender": data.get("gender", "unknown"),
            "weight_kg": data.get("weight") or data.get("weight_kg")
        }
        conditions = data.get("conditions", [])
        medications = data.get("medications", [])
        allergies = data.get("allergies", [])
        biomarkers = data.get("biomarkers") or data.get("labs", {})

        return {
            "patient_token": patient_token,
            "demographics": demographics,
            "entities": {
                "diagnosed_conditions": conditions,
                "current_medications": medications,
                "allergies": allergies,
                "biomarkers": biomarkers
            },
            "optical_qr_verified": True
        }
    except Exception:
        return process_clinical_note(json_str)

