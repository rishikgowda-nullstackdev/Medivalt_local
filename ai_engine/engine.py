"""
MediVault Local - Clinical AI Engine Core (Person C)
Implements:
1. CONTRACTS.md analyze() endpoint interface.
2. Full multi-dimensional evaluation: Drug-Disease, Drug-Drug, Lab Thresholds, Polypharmacy, and Alternatives.
3. Zero-hallucination deterministic core with local SLM (llama3.2:3b via Ollama) clinical explanation bridge.
"""

import os
import sqlite3
from typing import Dict, List, Any, Optional, Tuple

from ai_engine.pharmacology import PharmacologyKnowledge, BRAND_TO_GENERIC
from ai_engine.polypharmacy import PolypharmacyEngine
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
from ai_engine.alternatives import SafeAlternativeRecommender
from ai_engine.geriatric_renal import GeriatricRenalEngine, calculate_cockcroft_gault
from backend.ai_bridge import ai_bridge

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    return conn


def evaluate_full_safety(
    proposed_med: str,
    conditions: List[str],
    medications: List[str],
    allergies: List[str],
    labs: Optional[Dict[str, Any]] = None,
    demographics: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """
    Comprehensive multi-dimensional clinical safety evaluation:
    1. Normalization (brand -> generic)
    2. Allergy cross-reactivity
    3. Quantitative lab biomarker guardrails
    4. Polypharmacy matrix ('Triple Whammy', QTc, Serotonin)
    5. Drug <-> Disease rules
    6. Drug <-> Drug rules
    7. Safe alternative recommendations

    Returns:
        overall_status: 'CRITICAL', 'WARNING', or 'SAFE'
        alerts: List of detailed alert dictionaries
        canonical_drug: Generic molecule name
        recommended_alternatives: List of safe formulary substitutes
    """
    conn = get_db()
    cursor = conn.cursor()

    canonical_drug, detected_brand = PharmacologyKnowledge.normalize_drug_name(proposed_med)
    search_drug = canonical_drug.lower()

    alerts: List[Dict[str, Any]] = []
    overall_status = "SAFE"

    # Step 1: Allergy Screening
    allergy_alerts = PharmacologyKnowledge.check_allergies(proposed_med, allergies)
    for a in allergy_alerts:
        overall_status = "CRITICAL"
        alerts.append(a)

    # Step 2: Quantitative Lab Biomarker Thresholds
    if labs:
        lab_alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs(canonical_drug, detected_brand, labs)
        for la in lab_alerts:
            if la["severity"] == "CRITICAL":
                overall_status = "CRITICAL"
            elif la["severity"] == "WARNING" and overall_status != "CRITICAL":
                overall_status = "WARNING"
            alerts.append(la)

    # Step 3: Polypharmacy & Multi-Drug Cascades ('Triple Whammy', etc.)
    poly_alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed_med, medications)
    for pa in poly_alerts:
        if pa["severity"] == "CRITICAL":
            overall_status = "CRITICAL"
        elif pa["severity"] == "WARNING" and overall_status != "CRITICAL":
            overall_status = "WARNING"
        alerts.append(pa)

    # Step 3b: Dynamic Renal Dosing & Cockcroft-Gault CrCl Titration
    if demographics and labs:
        age = demographics.get("age")
        weight = demographics.get("weight_kg")
        # Check weight in labs if not in demographics
        if weight is None and "weight" in labs:
            weight = labs["weight"].get("value")
        
        scr = None
        if "creatinine" in labs:
            scr = labs["creatinine"].get("value")

        is_female = str(demographics.get("gender", "")).lower().startswith("f")
        crcl = calculate_cockcroft_gault(age, weight, scr, is_female)
        if crcl is not None:
            renal_alerts = GeriatricRenalEngine.evaluate_renal_titration(canonical_drug, crcl)
            for ra in renal_alerts:
                if ra["severity"] == "CRITICAL":
                    overall_status = "CRITICAL"
                elif ra["severity"] == "WARNING" and overall_status != "CRITICAL":
                    overall_status = "WARNING"
                alerts.append(ra)

    # Step 3c: 2023 AGS Beers Criteria (Geriatric Inappropriate Medications)
    if demographics and demographics.get("age") is not None:
        age_val = demographics.get("age")
        if age_val >= 65:
            beers_alerts = GeriatricRenalEngine.evaluate_beers_criteria(canonical_drug, age_val, conditions)
            for ba in beers_alerts:
                if ba["severity"] == "CRITICAL":
                    overall_status = "CRITICAL"
                elif ba["severity"] == "WARNING" and overall_status != "CRITICAL":
                    overall_status = "WARNING"
                alerts.append(ba)

    # Step 4: Drug <-> Disease Contraindications
    for cond in conditions:
        cond_clean = cond.strip().lower()
        cursor.execute("""
            SELECT condition_name, severity, mechanism, recommendation
            FROM contraindications_disease
            WHERE (? LIKE '%' || drug_name || '%' OR drug_name = ?)
              AND (? LIKE '%' || condition_name || '%' OR condition_name LIKE '%' || ? || '%')
        """, (search_drug, search_drug, cond_clean, cond_clean))

        for row in cursor.fetchall():
            sev = row["severity"]
            if sev == "CRITICAL":
                overall_status = "CRITICAL"
            elif sev == "WARNING" and overall_status != "CRITICAL":
                overall_status = "WARNING"

            factor = f"Diagnosed Condition: {cond}"
            if detected_brand:
                factor += f" (prescribed as '{detected_brand}', generic '{canonical_drug}')"

            alerts.append({
                "severity": sev,
                "interaction_type": "DRUG_DISEASE",
                "conflicting_factor": factor,
                "clinical_mechanism": row["mechanism"],
                "recommendation": row["recommendation"]
            })

    # Step 5: Drug <-> Drug Pairwise Interactions
    for med in medications:
        med_clean = med.strip().lower()
        med_generic, _ = PharmacologyKnowledge.normalize_drug_name(med)
        med_search = med_generic.lower()

        cursor.execute("""
            SELECT drug_a, drug_b, severity, mechanism, recommendation
            FROM contraindications_drug
            WHERE (drug_a = ? AND (? LIKE '%' || drug_b || '%' OR drug_b = ?))
               OR (drug_b = ? AND (? LIKE '%' || drug_a || '%' OR drug_a = ?))
        """, (search_drug, med_search, med_search, search_drug, med_search, med_search))

        for row in cursor.fetchall():
            sev = row["severity"]
            if sev == "CRITICAL":
                overall_status = "CRITICAL"
            elif sev == "WARNING" and overall_status != "CRITICAL":
                overall_status = "WARNING"

            alerts.append({
                "severity": sev,
                "interaction_type": "DRUG_DRUG",
                "conflicting_factor": f"Active Prescription: {med}",
                "clinical_mechanism": row["mechanism"],
                "recommendation": row["recommendation"]
            })

    conn.close()

    # Step 6: Safe Alternative Formulary Recommendations
    recommended_alternatives: List[Dict[str, Any]] = []
    if overall_status in ("CRITICAL", "WARNING"):
        recommended_alternatives = SafeAlternativeRecommender.get_safe_alternatives(
            proposed_med, conditions, allergies
        )

    return overall_status, alerts, canonical_drug, recommended_alternatives


# ---------------------------------------------------------------------------
# Frozen Contract Implementation (CONTRACTS.md - Person C)
# ---------------------------------------------------------------------------
def analyze(redacted_text: str) -> dict:
    """
    Person C AI Engine Frozen Contract:
    in: a redacted string
    out: JSON object { "flagged": bool, "reason": str, "drug": str|null, "severity": str|null }
    """
    from ingestion.pipeline import extract_entities

    entities = extract_entities(redacted_text)
    conditions = entities.get("diagnosed_conditions", [])
    medications = entities.get("current_medications", [])
    allergies = entities.get("allergies", [])
    labs = entities.get("biomarkers", {})

    flagged = False
    flagged_drug = None
    reason = "No adverse interactions detected."
    severity = "SAFE"

    # Evaluate each active medication in the document
    for med in medications:
        status, alerts, canonical, _ = evaluate_full_safety(
            med,
            conditions,
            [m for m in medications if m != med],
            allergies,
            labs
        )
        if status in ("CRITICAL", "WARNING"):
            flagged = True
            flagged_drug = med
            severity = status
            reason = alerts[0]["clinical_mechanism"] if alerts else "Contraindication detected."
            break

    return {
        "flagged": flagged,
        "reason": reason,
        "drug": flagged_drug,
        "severity": severity
    }


# ---------------------------------------------------------------------------
# Multi-Medicine Prescription Bundle Evaluator (Person C)
# ---------------------------------------------------------------------------
def evaluate_prescription_set(
    proposed_meds: List[Union[str, Dict[str, Any]]],
    conditions: List[str],
    existing_meds: List[str],
    allergies: List[str],
    labs: Optional[Dict[str, Any]] = None,
    demographics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Person C Multi-Medicine Evaluator:
    1. Evaluates each prescribed drug against patient conditions, allergies, labs, and active baseline meds.
    2. Evaluates intra-prescription drug-drug interactions between all newly prescribed items in the bundle.
    3. Triggers Tier 2 offline SLM reasoning for unlisted/novel medications.
    4. Provides safe alternatives and itemized triage status for each drug.
    """
    normalized_items: List[Dict[str, Any]] = []
    
    # Normalize input into uniform dicts
    for item in proposed_meds:
        if isinstance(item, str):
            clean_item = item.strip()
            if not clean_item:
                continue
            normalized_items.append({
                "medication": clean_item,
                "dosage": "Standard dose",
                "route": "PO",
                "frequency": "QD"
            })
        elif isinstance(item, dict):
            med_name = item.get("medication") or item.get("drug_name") or item.get("name", "")
            if not med_name:
                continue
            normalized_items.append({
                "medication": med_name,
                "dosage": item.get("dosage", "Standard dose"),
                "route": item.get("route", "PO"),
                "frequency": item.get("frequency", "QD"),
                "duration": item.get("duration", "")
            })

    if not normalized_items:
        return {
            "overall_status": "SAFE",
            "flagged": False,
            "total_alerts": 0,
            "medication_evaluations": [],
            "summary_explanation": "No proposed medications provided to evaluate."
        }

    all_prescribed_drug_names = [it["medication"] for it in normalized_items]
    evaluations: List[Dict[str, Any]] = []
    bundle_overall_status = "SAFE"
    total_alerts_count = 0

    for idx, item in enumerate(normalized_items):
        med_name = item["medication"]
        dosage = item["dosage"]
        route = item["route"]
        freq = item["frequency"]

        # Other proposed drugs in the SAME prescription bundle
        co_prescribed = [
            it["medication"] for j, it in enumerate(normalized_items) if j != idx
        ]
        
        # Combined active medications = baseline active meds + other new meds in this prescription
        combined_meds = list(set(existing_meds + co_prescribed))

        # Run Tier 1 Evaluation
        status, alerts, canonical_drug, alts = evaluate_full_safety(
            med_name,
            conditions,
            combined_meds,
            allergies,
            labs,
            demographics
        )

        # Distinguish intra-prescription alerts from baseline alerts
        for a in alerts:
            factor = a.get("conflicting_factor", "")
            for co_med in co_prescribed:
                if co_med.lower() in factor.lower() or PharmacologyKnowledge.normalize_drug_name(co_med)[0] in factor.lower():
                    a["is_intra_prescription"] = True
                    a["interaction_type"] = "INTRA_PRESCRIPTION_DDI"
                    a["conflicting_factor"] = f"Co-Prescribed in this Visit: {co_med}"

        # Tier 2 SLM Fallback for novel/unlisted drugs
        is_known_drug = (
            canonical_drug in BRAND_TO_GENERIC.values()
            or canonical_drug in [m.lower() for m in BRAND_TO_GENERIC.keys()]
            or status != "SAFE"
        )

        slm_assessment = None
        if not is_known_drug:
            # Query local SLM
            slm_assessment = ai_bridge.evaluate_unlisted_drug_contraindications(
                drug_name=med_name,
                dosage_route=f"{dosage} {route} {freq}".strip(),
                conditions=conditions,
                active_medications=combined_meds,
                allergies=allergies
            )
            if slm_assessment and slm_assessment.get("flagged"):
                slm_sev = slm_assessment.get("status", "WARNING").upper()
                if slm_sev not in ("CRITICAL", "WARNING"):
                    slm_sev = "WARNING"
                if slm_sev == "CRITICAL":
                    status = "CRITICAL"
                elif slm_sev == "WARNING" and status != "CRITICAL":
                    status = "WARNING"

                alerts.append({
                    "severity": slm_sev,
                    "interaction_type": "SLM_CLINICAL_REASONING",
                    "conflicting_factor": f"Unlisted Medication Analysis: {med_name}",
                    "clinical_mechanism": slm_assessment.get("mechanism", "Potential interaction detected by local SLM reasoning."),
                    "recommendation": slm_assessment.get("recommendation", "Review pharmacology carefully.")
                })

        # Update bundle overall status
        if status == "CRITICAL":
            bundle_overall_status = "CRITICAL"
        elif status == "WARNING" and bundle_overall_status != "CRITICAL":
            bundle_overall_status = "WARNING"

        total_alerts_count += len(alerts)

        # Build drug-specific explanation
        if status == "CRITICAL":
            expl = f"CRITICAL CONTRAINDICATION: High clinical hazard identified with '{med_name}'. Alternative required."
        elif status == "WARNING":
            expl = f"CLINICAL CAUTION: Moderate interaction or monitoring required for '{med_name}'."
        else:
            expl = f"CLEARED: No documented contraindications detected for '{med_name}'."

        evaluations.append({
            "medication": med_name,
            "canonical_drug": canonical_drug,
            "dosage": dosage,
            "route": route,
            "frequency": freq,
            "status": status,
            "alerts_count": len(alerts),
            "alerts": alerts,
            "polypharmacy_alerts": [a for a in alerts if a.get("interaction_type") == "POLYPHARMACY"],
            "intra_prescription_alerts": [a for a in alerts if a.get("interaction_type") == "INTRA_PRESCRIPTION_DDI"],
            "recommended_alternatives": alts,
            "explanation": expl,
            "slm_evaluated": slm_assessment is not None
        })

    flagged_count = sum(1 for e in evaluations if e["status"] in ("CRITICAL", "WARNING"))
    if bundle_overall_status == "CRITICAL":
        summary_msg = f"CRITICAL CONTRAINDICATION: {flagged_count} of {len(evaluations)} prescribed medication(s) carry severe clinical hazards."
    elif bundle_overall_status == "WARNING":
        summary_msg = f"CLINICAL CAUTION: {flagged_count} of {len(evaluations)} prescribed medication(s) require dosage adjustment or close monitoring."
    else:
        summary_msg = f"PRESCRIPTION CLEARED: All {len(evaluations)} prescribed medication(s) are safe to administer against patient profile."

    return {
        "overall_status": bundle_overall_status,
        "flagged": bundle_overall_status != "SAFE",
        "total_alerts": total_alerts_count,
        "total_prescribed": len(evaluations),
        "flagged_count": flagged_count,
        "medication_evaluations": evaluations,
        "summary_explanation": summary_msg
    }

