"""
MediVault Local - Autonomous SLM Clinical Note Intelligence (Person B)
Autonomous parsing of unstructured physician discharge summaries, progress notes,
and OCR scans into structured clinical entities (conditions, ICD-10, meds, labs, allergies)
with intelligent clinical discrepancy and safety omission detection.
Runs 100% offline via local SLM with deterministic regex/ontology fallback.
"""

import re
import json
import sqlite3
import os
from typing import Dict, Any, List, Optional
import httpx

from ingestion.pipeline import extract_lab_biomarkers, resolve_medical_ontology

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"
NOTE_AI_TIMEOUT = 3.5

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")

# Standard clinical condition -> ICD-10 dictionary mapping
COMMON_ICD10_MAP = {
    "chronic kidney disease": "N18.9",
    "ckd": "N18.9",
    "stage 3 ckd": "N18.3",
    "stage 4 ckd": "N18.4",
    "end stage renal disease": "N18.6",
    "hypertension": "I10",
    "essential hypertension": "I10",
    "htn": "I10",
    "type 2 diabetes mellitus": "E11.9",
    "type 2 diabetes": "E11.9",
    "diabetes": "E11.9",
    "t2dm": "E11.9",
    "heart failure": "I50.9",
    "chf": "I50.9",
    "atrial fibrillation": "I48.91",
    "afib": "I48.91",
    "peptic ulcer disease": "K27.9",
    "gastrointestinal bleed": "K92.2",
    "gi bleed": "K92.2",
    "asthma": "J45.909",
    "copd": "J44.9",
    "coronary artery disease": "I25.10",
    "cad": "I25.10",
    "deep vein thrombosis": "I82.40",
    "dvt": "I82.40",
    "pulmonary embolism": "I26.99",
    "pe": "I26.99",
    "gout": "M10.9",
    "cirrhosis": "K74.60",
    "major depressive disorder": "F32.9",
    "depression": "F32.9"
}


def _get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


class NoteIntelligenceEngine:
    """
    Autonomous clinical note intelligence engine.
    Extracts structured clinical data and highlights discrepancies
    between physician notes and safe pharmacology practices.
    """

    @classmethod
    def extract_intelligence(
        cls,
        raw_text: str,
        existing_chart: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parses unstructured clinical note using local SLM with deterministic fallback.
        """
        if not raw_text or not raw_text.strip():
            return {
                "conditions": [],
                "medications": [],
                "labs": {},
                "allergies": [],
                "discrepancies": [],
                "model": "None (Empty Input)"
            }

        # 1. Deterministic baseline extraction (always fast & accurate)
        det_labs = extract_lab_biomarkers(raw_text)
        det_data = cls._deterministic_note_extract(raw_text)

        # Merge extracted lab biomarkers
        merged_labs = det_data.get("labs", {})
        for k, v in det_labs.items():
            if k not in merged_labs:
                merged_labs[k] = v
        det_data["labs"] = merged_labs

        # 2. Try Local SLM Extraction
        slm_result = None
        model_used = "Deterministic Clinical Entity Engine"

        slm_prompt = (
            "You are a clinical NLP specialist extracting structured medical entities from an unformatted doctor note.\n"
            "Analyze the following note and output ONLY a valid JSON object with the exact keys:\n"
            '{\n'
            '  "conditions": ["list of clinical diagnoses/conditions"],\n'
            '  "medications": [\n'
            '     {"name": "drug name", "dose": "e.g. 500mg", "route": "oral/IV", "frequency": "BID/daily"}\n'
            '  ],\n'
            '  "allergies": [\n'
            '     {"allergen": "substance", "reaction": "e.g. rash/anaphylaxis"}\n'
            '  ],\n'
            '  "clinical_concerns": ["any alarming clinical observations or medication risks noticed in note"]\n'
            '}\n\n'
            f"Clinical Note:\n{raw_text[:2000]}\n"
        )

        try:
            with httpx.Client(timeout=NOTE_AI_TIMEOUT) as client:
                res = client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": DEFAULT_MODEL,
                        "prompt": slm_prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 350}
                    }
                )
                if res.status_code == 200:
                    raw_resp = res.json().get("response", "").strip()
                    json_match = re.search(r"\{.*\}", raw_resp, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        if isinstance(parsed, dict) and "conditions" in parsed:
                            slm_result = parsed
                            model_used = f"Ollama Local ({DEFAULT_MODEL})"
        except Exception:
            pass

        # 3. Combine SLM & Deterministic findings
        final_conditions = cls._merge_conditions(det_data.get("conditions", []), slm_result.get("conditions", []) if slm_result else [])
        final_medications = cls._merge_medications(det_data.get("medications", []), slm_result.get("medications", []) if slm_result else [])
        final_allergies = cls._merge_allergies(det_data.get("allergies", []), slm_result.get("allergies", []) if slm_result else [])

        # 4. Clinical Discrepancy & Omission Detection
        discrepancies = cls._detect_discrepancies(
            conditions=final_conditions,
            medications=final_medications,
            allergies=final_allergies,
            labs=merged_labs,
            raw_text=raw_text,
            existing_chart=existing_chart
        )

        return {
            "conditions": final_conditions,
            "medications": final_medications,
            "labs": merged_labs,
            "allergies": final_allergies,
            "discrepancies": discrepancies,
            "model": model_used
        }

    @classmethod
    def _deterministic_note_extract(cls, text: str) -> Dict[str, Any]:
        """Deterministic regex-based entity and ICD-10 extraction."""
        text_lower = text.lower()
        extracted_conditions = []
        for cond_name, icd_code in COMMON_ICD10_MAP.items():
            pattern = r"\b" + re.escape(cond_name) + r"\b"
            if re.search(pattern, text_lower):
                title_name = cond_name.title()
                extracted_conditions.append({
                    "name": title_name,
                    "icd10": icd_code,
                    "confidence": "high"
                })

        # Medication regex
        med_patterns = [
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|units|ml))\s*(?:po|iv|subq|prn|daily|bid|tid|qid)?\b",
            r"(?i)\b(lisinopril|metformin|ketorolac|furosemide|warfarin|apixaban|spironolactone|digoxin|tramadol|acetaminophen|ibuprofen|ciprofloxacin|amoxicillin|sertraline|omeprazole|atorvastatin|metoprolol|aspirin)\b"
        ]
        
        extracted_meds = []
        seen_meds = set()
        
        # Match with dose
        lab_words = {"creatinine", "egfr", "potassium", "sodium", "inr", "platelets", "glucose", "bun", "hemoglobin", "wbc", "bp"}
        for m in re.finditer(med_patterns[0], text):
            drug_name = m.group(1).strip()
            dose = m.group(2).strip()
            if drug_name.lower() not in lab_words and drug_name.lower() not in seen_meds:
                seen_meds.add(drug_name.lower())
                extracted_meds.append({
                    "name": drug_name,
                    "dose": dose,
                    "route": "Oral" if "po" in text_lower else "Not specified",
                    "frequency": "Daily"
                })

        # Match standalone known drugs
        for m in re.finditer(med_patterns[1], text):
            drug_name = m.group(1).strip().capitalize()
            if drug_name.lower() not in seen_meds:
                seen_meds.add(drug_name.lower())
                extracted_meds.append({
                    "name": drug_name,
                    "dose": "Standard",
                    "route": "Oral",
                    "frequency": "Active"
                })

        # Allergy regex
        extracted_allergies = []
        allergy_match = re.search(r"(?i)(?:allergies|allergic\s+to|allergy)\s*[:=]?\s*([^\n\.\;]+)", text)
        if allergy_match:
            raw_allergy_str = allergy_match.group(1).strip()
            if "nkda" not in raw_allergy_str.lower() and "none" not in raw_allergy_str.lower():
                parts = re.split(r"[,;]", raw_allergy_str)
                for p in parts:
                    clean_p = p.strip()
                    if clean_p:
                        extracted_allergies.append({
                            "allergen": clean_p.title(),
                            "reaction": "Documented in note"
                        })

        return {
            "conditions": extracted_conditions,
            "medications": extracted_meds,
            "allergies": extracted_allergies,
            "labs": {}
        }

    @classmethod
    def _merge_conditions(cls, det_conds: List[Dict[str, Any]], slm_conds: List[Any]) -> List[Dict[str, Any]]:
        """Combine and de-duplicate condition lists, assigning ICD-10 codes."""
        out = list(det_conds)
        seen_names = {c["name"].lower() for c in out}

        for sc in slm_conds:
            c_name = sc if isinstance(sc, str) else sc.get("name", "")
            if c_name and c_name.lower() not in seen_names:
                seen_names.add(c_name.lower())
                icd = COMMON_ICD10_MAP.get(c_name.lower(), "Unspecified (R69)")
                out.append({
                    "name": c_name.title(),
                    "icd10": icd,
                    "confidence": "slm-inferred"
                })
        return out

    @classmethod
    def _merge_medications(cls, det_meds: List[Dict[str, Any]], slm_meds: List[Any]) -> List[Dict[str, Any]]:
        """Combine and standardize medication items."""
        out = list(det_meds)
        seen = {m["name"].lower() for m in out}

        for sm in slm_meds:
            if isinstance(sm, dict):
                m_name = sm.get("name", "").strip()
                if m_name and m_name.lower() not in seen:
                    seen.add(m_name.lower())
                    out.append({
                        "name": m_name.capitalize(),
                        "dose": sm.get("dose", "Not specified"),
                        "route": sm.get("route", "Oral"),
                        "frequency": sm.get("frequency", "Daily")
                    })
            elif isinstance(sm, str) and sm.strip().lower() not in seen:
                seen.add(sm.strip().lower())
                out.append({
                    "name": sm.strip().capitalize(),
                    "dose": "Standard",
                    "route": "Oral",
                    "frequency": "Active"
                })
        return out

    @classmethod
    def _merge_allergies(cls, det_allergies: List[Dict[str, Any]], slm_allergies: List[Any]) -> List[Dict[str, Any]]:
        """Combine and de-duplicate allergy records."""
        out = list(det_allergies)
        seen = {a["allergen"].lower() for a in out}

        for sa in slm_allergies:
            if isinstance(sa, dict):
                a_name = sa.get("allergen", "").strip()
                if a_name and a_name.lower() not in seen:
                    seen.add(a_name.lower())
                    out.append({
                        "allergen": a_name.title(),
                        "reaction": sa.get("reaction", "Hypersensitivity")
                    })
            elif isinstance(sa, str) and sa.strip().lower() not in seen:
                seen.add(sa.strip().lower())
                out.append({
                    "allergen": sa.strip().title(),
                    "reaction": "Documented in note"
                })
        return out

    @classmethod
    def _detect_discrepancies(
        cls,
        conditions: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        allergies: List[Dict[str, Any]],
        labs: Dict[str, Any],
        raw_text: str,
        existing_chart: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detects diagnostic discrepancies, silent omissions, and high-risk safety hazards.
        """
        discrepancies = []
        cond_names = [c["name"].lower() for c in conditions]
        med_names = [m["name"].lower() for m in medications]
        allergy_names = [a["allergen"].lower() for a in allergies]

        # 1. Renal Safety Discrepancy (eGFR vs NSAID/Metformin)
        egfr_val = None
        if "egfr" in labs and isinstance(labs["egfr"], dict):
            egfr_val = labs["egfr"].get("value")
        elif "eGFR" in labs and isinstance(labs["eGFR"], dict):
            egfr_val = labs["eGFR"].get("value")

        if egfr_val is not None:
            try:
                e_num = float(egfr_val)
                if e_num < 45.0:
                    for m in med_names:
                        if any(nsaid in m for nsaid in ["ketorolac", "ibuprofen", "naproxen", "meloxicam", "diclofenac"]):
                            discrepancies.append({
                                "type": "RENAL_NEPHROTOXIC_HAZARD",
                                "severity": "CRITICAL",
                                "finding": f"Severe renal impairment (eGFR {e_num} mL/min) concurrent with nephrotoxic NSAID prescription '{m.capitalize()}'.",
                                "action": "Discontinue NSAID immediately; replace with renal-sparing analgesic."
                            })
                        if "metformin" in m and e_num < 30.0:
                            discrepancies.append({
                                "type": "METFORMIN_LACTIC_ACIDOSIS",
                                "severity": "CRITICAL",
                                "finding": f"Metformin active despite eGFR {e_num} mL/min (< 30 mL/min absolute cutoff).",
                                "action": "Hold Metformin to avoid fatal lactic acidosis."
                            })
            except Exception:
                pass

        # 2. Triple Whammy Omission Check
        has_ace_arb = any(a in " ".join(med_names) for a in ["lisinopril", "losartan", "ramipril", "enalapril", "valsartan"])
        has_diuretic = any(d in " ".join(med_names) for d in ["furosemide", "hydrochlorothiazide", "lasix", "torsemide", "hctz"])
        has_nsaid = any(n in " ".join(med_names) for n in ["ketorolac", "ibuprofen", "naproxen", "toradol", "advil"])

        if has_ace_arb and has_diuretic and has_nsaid:
            discrepancies.append({
                "type": "TRIPLE_WHAMMY_HEMODYNAMIC_COLLAPSE",
                "severity": "CRITICAL",
                "finding": "Triple Whammy combination detected: ACE-I/ARB + Diuretic + NSAID.",
                "action": "Immediate acute kidney failure risk. Discontinue the NSAID."
            })

        # 3. Chart vs Note Allergy Conflict
        if existing_chart and "allergies" in existing_chart:
            chart_allergies = [a.lower() for a in existing_chart["allergies"]]
            for n_allergy in allergy_names:
                if n_allergy not in chart_allergies and n_allergy not in ["nkda", "none"]:
                    discrepancies.append({
                        "type": "CHART_ALLERGY_OMISSION",
                        "severity": "WARNING",
                        "finding": f"Note documents allergy to '{n_allergy.title()}', but it is missing from patient's electronic medical chart.",
                        "action": "Update patient allergy profile in EHR immediately."
                    })

        # 4. GI Bleed History with Anticoagulation / Antiplatelet
        has_bleed_history = any(b in " ".join(cond_names) or b in raw_text.lower() for b in ["peptic ulcer", "gi bleed", "gastric ulcer", "melena"])
        has_blood_thinner = any(bt in " ".join(med_names) for bt in ["warfarin", "apixaban", "clopidogrel", "aspirin", "plavix", "eliquis"])
        if has_bleed_history and has_blood_thinner:
            discrepancies.append({
                "type": "HEMORRHAGIC_GI_RISK",
                "severity": "WARNING",
                "finding": "Patient has active or recent GI bleeding history while prescribed antithrombotic therapy.",
                "action": "Ensure gastroprotective PPI co-prescribing and monitor hemoglobin."
            })

        return discrepancies


def extract_clinical_intelligence_from_note(
    raw_text: str,
    existing_chart: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Global interface to parse unstructured clinical notes."""
    return NoteIntelligenceEngine.extract_intelligence(raw_text, existing_chart=existing_chart)
