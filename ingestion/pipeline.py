"""
MediVault Local - Clinical Ingestion Pipeline (Person B)
Zero-cloud HIPAA Safe Harbor (§ 164.514(b)) and India DPDP compliant.
Performs in-memory document parsing, local PHI de-identification,
clinical entity extraction, and quantitative lab biomarker analysis.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .extractor import extract_text
from .redactor import redact_phi, redact_pii

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
    "glipizide", "glucotrol", "insulin",
    # Anticoagulants & Antiplatelets
    "warfarin", "coumadin", "clopidogrel", "plavix", "apixaban", "eliquis",
    "rivaroxaban", "xarelto", "ticagrelor", "brilinta",
    # GI & Analgesics
    "omeprazole", "prilosec", "pantoprazole", "protonix", "acetaminophen", "tylenol",
    "paracetamol", "tramadol", "ultram", "codeine",
    # Psychotropics & Antimicrobials
    "fluoxetine", "prozac", "sertraline", "zoloft", "selegiline", "eldepryl",
    "clarithromycin", "biaxin", "amoxicillin", "amoxil", "ciprofloxacin", "cipro", "penicillin",
    # Respiratory Inhalers
    "albuterol", "salbutamol", "ventolin", "proair", "fluticasone", "flonase", "flovent",
    # Statins & Lipid Agents
    "simvastatin", "zocor", "atorvastatin", "lipitor", "gemfibrozil", "lopid"
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
    inr_match = re.search(r"(?i)\bINR\s*[:=]?\s*(\d+(?:\.\d+)?)\b", text)
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
            "unit": "",
            "display": f"{val}",
            "status": status,
        }

    # 5. Platelets
    plt_match = re.search(
        r"(?i)\bplatelets?\s*[:=]?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?k?)\b",
        text,
    )
    if plt_match:
        raw_str = plt_match.group(1).replace(",", "").lower()
        if raw_str.endswith("k"):
            actual_count = float(raw_str[:-1]) * 1000
        else:
            raw_num = float(raw_str)
            actual_count = raw_num * 1000 if raw_num < 1000 else raw_num

        count_k = actual_count / 1000.0
        if count_k < 50.0:
            status = "CRITICAL_LOW"
        elif count_k < 100.0:
            status = "LOW"
        else:
            status = "NORMAL"

        biomarkers["Platelets"] = {
            "value": actual_count,
            "unit": "/mcL",
            "display": f"{int(actual_count):,} /mcL",
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
            # Match word boundary
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
                    if cleaned and len(cleaned) < 50:
                        extracted_allergies.append(cleaned)

        # Check multiline bullet patterns under ALLERGIES:
        bullet_block_match = re.search(r"(?i)\ballergies\s*:\s*\n((?:\s*[-*•]\s*[^\n]+\n?)+)", text)
        if bullet_block_match:
            block = bullet_block_match.group(1)
            for line in block.splitlines():
                cleaned = re.sub(r"^[-\s*•]+", "", line).strip()
                # Split reaction if in parentheses e.g. "Penicillin (skin rash)" -> keep allergen
                if cleaned:
                    extracted_allergies.append(cleaned)

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
