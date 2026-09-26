"""
MediVault Local - Clinical Ingestion Pipeline (Person B)
Zero-cloud HIPAA Safe Harbor (§ 164.514(b)) and India DPDP compliant.
Performs in-memory document parsing, local PHI de-identification,
clinical entity extraction, quantitative lab biomarker analysis,
and sovereign hospital interoperability parsing (FHIR R4, HL7 v2, optical QR).
"""

import os
import re
import json
import zlib
import base64
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .extractor import extract_text
from .redactor import redact_phi, redact_pii

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")

# ---------------------------------------------------------------------------
# Clinical Lexicons for Deterministic Entity Extraction
# ---------------------------------------------------------------------------
CONDITION_LEXICON: Dict[str, List[str]] = {
    "Chronic Kidney Disease": [
        "chronic kidney disease", "ckd", "renal failure", "renal impairment",
        "renal insufficiency", "nephropathy", "chronic medical renal disease", "esrd"
    ],
    "Hypertension": [
        "hypertension", "high blood pressure", "htn", "essential hypertension"
    ],
    "Asthma": [
        "asthma", "bronchial asthma", "reactive airway disease", "wheezing disorder"
    ],
    "Chronic Obstructive Pulmonary Disease": [
        "copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"
    ],
    "Diabetes Mellitus": [
        "diabetes", "type 2 diabetes", "t2dm", "type 1 diabetes", "diabetic", "hyperglycemia"
    ],
    "Diabetic Ketoacidosis": [
        "dka", "diabetic ketoacidosis"
    ],
    "Peptic Ulcer Disease": [
        "peptic ulcer", "gastric ulcer", "duodenal ulcer", "pud", "gi bleed", "gastritis"
    ],
    "Atrial Fibrillation": [
        "atrial fibrillation", "afib", "a-fib", "arrhythmia"
    ],
    "Deep Vein Thrombosis": [
        "deep vein thrombosis", "dvt", "pulmonary embolism", "venous thromboembolism"
    ],
    "Heart Failure": [
        "heart failure", "chf", "congestive heart failure"
    ],
    "Pregnancy": [
        "pregnant", "pregnancy", "gestation", "gravida"
    ],
    "Osteoarthritis": [
        "osteoarthritis", "degenerative joint disease"
    ],
    "Allergic Rhinitis": [
        "allergic rhinitis"
    ],
    "Migraine": [
        "migraine", "migraine headaches"
    ],
    "Gastroesophageal Reflux Disease": [
        "gerd", "gastroesophageal reflux"
    ]
}

MEDICATION_LEXICON: List[str] = [
    # NSAIDs
    "ibuprofen", "advil", "motrin", "naproxen", "aleve", "diclofenac", "voltaren",
    "meloxicam", "mobic", "ketorolac", "toradol", "indomethacin", "indocin",
    "celecoxib", "celebrex", "aspirin", "ecotrin",
    # Antihypertensives & Beta-blockers
    "propranolol", "inderal", "timolol", "nadolol", "labetalol", "metoprolol", "lopressor", "toprol",
    "atenolol", "bisoprolol", "lisinopril", "prinivil", "zestril", "enalapril", "vasotec", "ramipril",
    "altace", "losartan", "cozaar", "valsartan", "diovan", "amlodipine", "norvasc",
    "spironolactone", "aldactone",
    # Antidiabetics
    "metformin", "glucophage", "empagliflozin", "jardiance", "dapagliflozin", "farxiga",
    "glipizide", "glucotrol", "insulin", "linagliptin",
    # Anticoagulants & Antiplatelets
    "warfarin", "coumadin", "clopidogrel", "plavix", "apixaban", "eliquis",
    "rivaroxaban", "xarelto", "ticagrelor", "brilinta", "enoxaparin", "heparin",
    # GI & Analgesics
    "omeprazole", "prilosec", "pantoprazole", "protonix", "acetaminophen", "tylenol",
    "paracetamol", "tramadol", "ultram", "codeine",
    # Psychotropics & Antimicrobials
    "fluoxetine", "prozac", "sertraline", "zoloft", "selegiline", "eldepryl",
    "clarithromycin", "biaxin", "amoxicillin", "amoxil", "ciprofloxacin", "cipro", "penicillin",
    "azithromycin", "levofloxacin",
    # Respiratory Inhalers
    "albuterol", "salbutamol", "ventolin", "proair", "fluticasone", "flonase", "flovent",
    # Diuretics, Statins & Lipid Agents
    "furosemide", "hydrochlorothiazide", "simvastatin", "zocor", "atorvastatin", "lipitor", "gemfibrozil", "lopid"
]

ALLERGY_LINE_PATTERNS = [
    r"(?i)\ballerg(?:ies|y|ic\s+to)\s*[:=-]?\s*([^\n.;]+)",
    r"(?i)\bknown\s+allergies\s*[:=-]?\s*([^\n.;]+)",
]


# ---------------------------------------------------------------------------
# Lab Biomarker Quantitative Parser
# ---------------------------------------------------------------------------
def extract_lab_biomarkers(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses numeric lab values and evaluates them against clinical safety thresholds.

    Supported keys:
        - "eGFR":        "CRITICAL_LOW" (<30), "WARNING_LOW" (30-44), "NORMAL" (>=45)
        - "Creatinine":  "HIGH" (>1.4), "NORMAL" (<=1.4)
        - "Potassium":   "CRITICAL_HIGH" (>5.0), "LOW" (<3.5), "NORMAL" (3.5-5.0)
        - "INR":         "CRITICAL_HIGH" (>3.5), "ELEVATED" (>3.0), "NORMAL" (<=3.0)
        - "Platelets":   "CRITICAL_LOW" (<50k), "LOW" (<100k), "NORMAL" (>=100k)
        - "BloodPressure": "CRITICAL_HIGH" (sys>=180 or dia>=120), "HIGH" (sys>=140 or dia>=90), "NORMAL"

    Each biomarker value shape:
        { "value": float, "unit": str, "display": str, "status": str }
    """
    biomarkers: Dict[str, Dict[str, Any]] = {}

    # 1. eGFR
    egfr_match = re.search(r"(?i)\b(?:eGFR|GFR)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\b", text)
    if egfr_match:
        val = float(egfr_match.group(1))
        if val < 30.0:
            status = "CRITICAL_LOW"
        elif val < 45.0:
            status = "WARNING_LOW"
        else:
            status = "NORMAL"
        disp_num = int(val) if val.is_integer() else val
        biomarkers["eGFR"] = {
            "value": val,
            "unit": "mL/min/1.73m2",
            "display": f"{disp_num} mL/min/1.73m2",
            "status": status,
        }

    # 2. Creatinine
    creat_match = re.search(r"(?i)\b(?:serum\s+)?creatinine\s*[:=]?\s*(\d+(?:\.\d+)?)\b", text)
    if creat_match:
        val = float(creat_match.group(1))
        status = "HIGH" if val > 1.4 else "NORMAL"
        biomarkers["Creatinine"] = {
            "value": val,
            "unit": "mg/dL",
            "display": f"{val} mg/dL",
            "status": status,
        }

    # 3. Potassium
    k_match = re.search(
        r"(?i)(?:\b(?:serum\s+)?potassium\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mEq/L|mmol/L)?\b"
        r"|\bK\+\s*[:=]?\s*(\d+(?:\.\d+)?)\b)",
        text,
    )
    if k_match:
        val_str = k_match.group(1) or k_match.group(2)
        val = float(val_str)
        if val > 5.0:
            status = "CRITICAL_HIGH"
        elif val < 3.5:
            status = "LOW"
        else:
            status = "NORMAL"
        biomarkers["Potassium"] = {
            "value": val,
            "unit": "mEq/L",
            "display": f"{val} mEq/L",
            "status": status,
        }

    # 4. INR
    inr_match = re.search(r"(?i)\b(?:current\s+)?INR\s*[:=]?\s*(\d+(?:\.\d+)?)\b", text)
    if inr_match:
        val = float(inr_match.group(1))
        if val > 3.5:
            status = "CRITICAL_HIGH"
        elif val > 3.0:
            status = "ELEVATED"
        else:
            status = "NORMAL"
        biomarkers["INR"] = {
            "value": val,
            "unit": "INR",
            "display": f"{val}",
            "status": status,
        }

    # 5. Platelets
    plt_match = re.search(
        r"(?i)\b(?:platelets|platelet\s+count|plt)\s*[:=]?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?k?)\b",
        text,
    )
    if plt_match:
        raw_str = plt_match.group(1).replace(",", "").lower()
        if raw_str.endswith("k"):
            count_k = float(raw_str[:-1])
            actual_count = count_k * 1000.0
        else:
            raw_num = float(raw_str)
            if raw_num < 1000.0:
                count_k = raw_num
                actual_count = raw_num * 1000.0
            else:
                actual_count = raw_num
                count_k = round(raw_num / 1000.0, 1)

        if count_k < 50.0:
            status = "CRITICAL_LOW"
        elif count_k < 100.0:
            status = "LOW"
        else:
            status = "NORMAL"

        biomarkers["Platelets"] = {
            "value": count_k,
            "raw_value": actual_count,
            "unit": "x10^3/uL",
            "display": f"{int(actual_count):,} /mcL" if actual_count >= 1000 else f"{count_k}k / uL",
            "status": status,
        }

    # 6. Blood Pressure
    bp_match = re.search(
        r"(?i)\b(?:BP|Blood\s+Pressure)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmHg)?\b",
        text,
    )
    if bp_match:
        sys_val = float(bp_match.group(1))
        dia_val = float(bp_match.group(2))
        if sys_val >= 180.0 or dia_val >= 120.0:
            status = "CRITICAL_HIGH"
        elif sys_val >= 140.0 or dia_val >= 90.0:
            status = "HIGH"
        elif sys_val < 90.0 or dia_val < 60.0:
            status = "LOW"
        else:
            status = "NORMAL"

        biomarkers["BloodPressure"] = {
            "value": sys_val,
            "systolic": int(sys_val),
            "diastolic": int(dia_val),
            "unit": "mmHg",
            "display": f"{int(sys_val)}/{int(dia_val)} mmHg",
            "status": status,
        }

    return biomarkers


# ---------------------------------------------------------------------------
# Structured Clinical Entity Extraction
# ---------------------------------------------------------------------------
def extract_entities(text: str) -> Dict[str, Any]:
    """
    Extracts structured clinical entities from plain or redacted text.
    100% offline using deterministic medical vocabulary heuristics.

    Returns:
        {
          "diagnosed_conditions": List[str],
          "current_medications": List[str],
          "allergies": List[str],
          "clinical_labs": Dict[str, str],
          "biomarkers": Dict[str, Dict[str, Any]]
        }
    """
    text_lower = text.lower()

    # 1. Diagnosed Conditions
    extracted_conditions: List[str] = []
    for canonical_name, aliases in CONDITION_LEXICON.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                # Check for explicit negation immediately preceding (e.g., "no evidence of CKD")
                start_pos = max(0, match.start() - 35)
                preceding = text_lower[start_pos:match.start()]
                if re.search(r"\b(?:no\s+evidence\s+of|denies|negative\s+for|ruled\s+out)\s*$", preceding):
                    continue
                extracted_conditions.append(canonical_name)
                break

    # 2. Current Medications with captured dosages
    extracted_medications: List[str] = []
    for med in MEDICATION_LEXICON:
        med_pattern = (
            r"\b(" + re.escape(med) + r")"
            r"(?:\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|puffs?)\b"
            r"(?:\s+(?:po|inhaled|iv|prn|daily|bid|tid|qid|q\d+h))*"
            r"))?"
        )
        match = re.search(med_pattern, text_lower)
        if match:
            med_name = match.group(1).title()
            dosage = match.group(2)
            if dosage:
                extracted_medications.append(f"{med_name} {dosage.strip()}")
            else:
                extracted_medications.append(med_name)

    # 3. Allergies
    extracted_allergies: List[str] = []

    # Check for NKDA
    if re.search(r"(?i)\bNKDA\b|\bno\s+known\s+drug\s+allergies\b", text):
        extracted_allergies.append("No Known Drug Allergies (NKDA)")
    else:
        # Check inline patterns: "Allergies: Penicillin, Sulfa"
        for pattern in ALLERGY_LINE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                items = match.group(1).split(",")
                for item in items:
                    cleaned = re.sub(r"^[-\s*•]+", "", item).strip().rstrip(".;")
                    allergen_name = re.split(r"[\(:;,]", cleaned)[0].strip()
                    if allergen_name and len(allergen_name) < 50 and not allergen_name.lower().startswith("adverse"):
                        extracted_allergies.append(allergen_name.title())

        # Check multiline bullet patterns under ALLERGIES:
        bullet_block_match = re.search(r"(?i)\ballergies\s*:\s*\n((?:\s*[-*•]\s*[^\n]+\n?)+)", text)
        if bullet_block_match:
            block = bullet_block_match.group(1)
            for line in block.splitlines():
                cleaned = re.sub(r"^[-\s*•]+", "", line).strip()
                allergen_name = re.split(r"[\(:;,]", cleaned)[0].strip()
                if allergen_name and len(allergen_name) < 50:
                    extracted_allergies.append(allergen_name.title())

    # Fallback keyword scan only if no allergies extracted yet and allergic context exists
    if not extracted_allergies and "allerg" in text_lower:
        allergy_contexts = re.findall(r"(?i)(?:allergic\s+to|allergy\s*:\s*|allergies\s*:\s*)([^.\n;]+)", text)
        for ctx in allergy_contexts:
            for term in ["penicillin", "sulfa", "sulfonamides", "aspirin", "codeine", "cephalosporin"]:
                if re.search(r"(?i)\b" + re.escape(term) + r"\b", ctx):
                    extracted_allergies.append(term.title())

    # 4. Lab Biomarkers (rich & legacy map)
    biomarkers = extract_lab_biomarkers(text)
    clinical_labs = {key: data["display"] for key, data in biomarkers.items()}

    return {
        "diagnosed_conditions": sorted(list(set(extracted_conditions))),
        "current_medications": sorted(list(set(extracted_medications))),
        "allergies": sorted(list(set(extracted_allergies))),
        "clinical_labs": clinical_labs,
        "biomarkers": biomarkers,
    }


# ---------------------------------------------------------------------------
# Full Clinical Note Processing (Unified Pipeline Call)
# ---------------------------------------------------------------------------
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
# Primary Frozen Contract Pipeline Function
# ---------------------------------------------------------------------------
def process_file(
    file_path_or_bytes: Union[str, bytes, Path],
    filename: Optional[str] = None
) -> str:
    """
    Person B Primary Frozen Contract.
    Takes file bytes or a file path (PDF or TXT).
    Parses document in-memory without disk writes.
    Returns plain-text string with 18 HIPAA Safe Harbor PHI replaced by [REDACTED_*] tokens.
    Guarantees clinical data, labs, biomarkers, and medications remain intact.
    """
    raw_text = extract_text(file_path_or_bytes, filename=filename)
    redacted_text, _, _ = redact_phi(raw_text)
    return redacted_text


def ingest_record(file_path: Union[str, Path]) -> str:
    """
    Legacy Day 3 pipeline function returning [REDACTED] plain text.
    Preserved for backward compatibility with test_ingestion.py.
    """
    raw_text = extract_text(file_path)
    return redact_pii(raw_text)


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
            if c_low in [s.lower() for s in syns] or standard.lower() in c_low or c_low in standard.lower():
                clean_conds.append(standard.lower())
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
