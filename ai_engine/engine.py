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

from ai_engine.pharmacology import PharmacologyKnowledge
from ai_engine.polypharmacy import PolypharmacyEngine
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
from ai_engine.alternatives import SafeAlternativeRecommender
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
    labs: Optional[Dict[str, Any]] = None
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
