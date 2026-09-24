"""
Main deterministic safety engine for MediVault Local.

This module coordinates all safety checks:

1. Drug normalization
2. Allergy checking
3. Laboratory checks
4. Polypharmacy checks
5. Drug-disease checks
6. Drug-drug checks
7. Safe alternatives

The deterministic layer decides whether a medication is unsafe.
The LLM is only used later to explain an already-detected alert.
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from ai_engine.pharmacology import PharmacologyKnowledge
from ai_engine.polypharmacy import PolypharmacyEngine
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
from ai_engine.alternatives import SafeAlternativeRecommender


# ------------------------------------------------------------
# DATABASE LOCATION
# ------------------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_PATH = os.path.join(
    BASE_DIR,
    "database",
    "medivault.db"
)


# ------------------------------------------------------------
# DATABASE HELPER
# ------------------------------------------------------------

def _get_connection():
    """
    Open the shared MediVault SQLite database.

    The backend handoff specifies a 5-second timeout and
    sqlite3.Row for database access.
    """

    connection = sqlite3.connect(
        DB_PATH,
        timeout=5
    )

    connection.row_factory = sqlite3.Row

    return connection


# ------------------------------------------------------------
# DRUG-DISEASE CHECK
# ------------------------------------------------------------

def _check_drug_disease(
    canonical_drug: str,
    conditions: List[str]
) -> List[Dict[str, Any]]:
    """
    Check the shared contraindications_disease table.
    """

    if not canonical_drug or not conditions:
        return []

    alerts = []

    try:
        connection = _get_connection()

        cursor = connection.cursor()

        for condition in conditions:

            if not condition:
                continue

            condition_clean = condition.strip()

            cursor.execute(
                """
                SELECT
                    condition_name,
                    severity,
                    mechanism,
                    recommendation
                FROM contraindications_disease
                WHERE
                    (? LIKE '%' || drug_name || '%'
                     OR drug_name = ?)
                    AND
                    (? LIKE '%' || condition_name || '%'
                     OR condition_name LIKE '%' || ? || '%')
                """,
                (
                    canonical_drug,
                    canonical_drug,
                    condition_clean,
                    condition_clean
                )
            )

            rows = cursor.fetchall()

            for row in rows:

                alerts.append({
                    "severity": row["severity"],
                    "interaction_type": "DRUG_DISEASE",
                    "conflicting_factor": (
                        f"Diagnosed Condition: "
                        f"{row['condition_name']}"
                    ),
                    "clinical_mechanism": row["mechanism"],
                    "recommendation": row["recommendation"],
                })

        connection.close()

    except sqlite3.Error:
        return []

    return alerts


# ------------------------------------------------------------
# DRUG-DRUG CHECK
# ------------------------------------------------------------

def _check_drug_drug(
    canonical_drug: str,
    medications: List[str]
) -> List[Dict[str, Any]]:
    """
    Check the shared contraindications_drug table.
    """

    if not canonical_drug or not medications:
        return []

    alerts = []

    try:
        connection = _get_connection()

        cursor = connection.cursor()

        for medication in medications:

            if not medication:
                continue

            medication_clean = medication.strip().lower()

            cursor.execute(
                """
                SELECT
                    drug_a,
                    drug_b,
                    severity,
                    mechanism,
                    recommendation
                FROM contraindications_drug
                WHERE
                    (
                        drug_a = ?
                        AND
                        (
                            ? LIKE '%' || drug_b || '%'
                            OR drug_b = ?
                        )
                    )
                    OR
                    (
                        drug_b = ?
                        AND
                        (
                            ? LIKE '%' || drug_a || '%'
                            OR drug_a = ?
                        )
                    )
                """,
                (
                    canonical_drug,
                    medication_clean,
                    medication_clean,
                    canonical_drug,
                    medication_clean,
                    medication_clean
                )
            )

            rows = cursor.fetchall()

            for row in rows:

                other_drug = (
                    row["drug_b"]
                    if row["drug_a"] == canonical_drug
                    else row["drug_a"]
                )

                alerts.append({
                    "severity": row["severity"],
                    "interaction_type": "DRUG_DRUG",
                    "conflicting_factor": (
                        f"Current Medication: {other_drug}"
                    ),
                    "clinical_mechanism": row["mechanism"],
                    "recommendation": row["recommendation"],
                })

        connection.close()

    except sqlite3.Error:
        return []

    return alerts


# ------------------------------------------------------------
# FULL SAFETY EVALUATION
# ------------------------------------------------------------

def evaluate_full_safety(
    proposed_med: str,
    conditions: List[str],
    medications: List[str],
    allergies: List[str],
    labs: Optional[Dict[str, Any]] = None
) -> Tuple[
    str,
    List[Dict[str, Any]],
    str,
    List[Dict[str, Any]]
]:
    """
    Run the complete deterministic safety evaluation.

    Returns:

        overall_status
        alerts
        canonical_drug
        recommended_alternatives
    """

    conditions = conditions or []
    medications = medications or []
    allergies = allergies or []

    # --------------------------------------------------------
    # 1. BRAND -> GENERIC NORMALIZATION
    # --------------------------------------------------------

    canonical_drug, detected_brand = (
    PharmacologyKnowledge.normalize_drug_name(
        proposed_med
    )
)

    # --------------------------------------------------------
    # 2. ALLERGY CHECK
    # --------------------------------------------------------

    allergy_alerts = (
        PharmacologyKnowledge.check_allergies(
            proposed_med,
            allergies
        )
    )

    # --------------------------------------------------------
    # 3. LAB CHECK
    # --------------------------------------------------------

    lab_alerts = (
        LabBiomarkerEvaluator.evaluate_drug_against_labs(
            canonical_drug,
            detected_brand,
            labs
        )
    )

    # --------------------------------------------------------
    # 4. POLYPHARMACY CHECK
    # --------------------------------------------------------

    poly_alerts = (
        PolypharmacyEngine.evaluate_polypharmacy(
            proposed_med,
            medications
        )
    )

    # --------------------------------------------------------
    # 5. DRUG -> DISEASE CHECK
    # --------------------------------------------------------

    disease_alerts = _check_drug_disease(
        canonical_drug,
        conditions
    )

    # --------------------------------------------------------
    # 6. DRUG -> DRUG CHECK
    # --------------------------------------------------------

    drug_alerts = _check_drug_drug(
        canonical_drug,
        medications
    )

    # --------------------------------------------------------
    # COMBINE ALL ALERTS
    # --------------------------------------------------------

    alerts = (
        allergy_alerts
        + lab_alerts
        + poly_alerts
        + disease_alerts
        + drug_alerts
    )

    # --------------------------------------------------------
    # DETERMINE OVERALL STATUS
    # --------------------------------------------------------

    if any(
        alert["severity"] == "CRITICAL"
        for alert in alerts
    ):
        overall_status = "CRITICAL"

    elif any(
        alert["severity"] == "WARNING"
        for alert in alerts
    ):
        overall_status = "WARNING"

    else:
        overall_status = "SAFE"

    # --------------------------------------------------------
    # SAFE ALTERNATIVES
    # --------------------------------------------------------

    if overall_status in ("CRITICAL", "WARNING"):
        recommended_alternatives = (
            SafeAlternativeRecommender.get_safe_alternatives(
                proposed_med,
                conditions,
                allergies
            )
        )
    else:
        recommended_alternatives = []

    return (
        overall_status,
        alerts,
        canonical_drug,
        recommended_alternatives
    )


# ------------------------------------------------------------
# SIMPLE ANALYZE FUNCTION
# ------------------------------------------------------------

def analyze(redacted_text: str) -> dict:
    """
    Frozen backend contract.

    Takes redacted clinical text and returns exactly:

    {
        "flagged": bool,
        "reason": str,
        "drug": str | None,
        "severity": str | None
    }

    Entity extraction will be connected to the ingestion
    module during integration.
    """

    if not redacted_text or not redacted_text.strip():
        return {
            "flagged": False,
            "reason": "No clinical information provided.",
            "drug": None,
            "severity": "SAFE",
        }

    # Temporary local extraction for basic testing.
    # The final integration will use ingestion.pipeline.extract_entities().
    text = redacted_text.lower()

    proposed_drug = None

    known_drugs = [
        "ibuprofen",
        "aspirin",
        "amoxicillin",
        "propranolol",
        "warfarin",
        "lisinopril",
        "naproxen",
        "diclofenac",
        "metformin",
    ]

    for drug in known_drugs:

        if drug in text:
            proposed_drug = drug
            break

    if proposed_drug is None:
        return {
            "flagged": False,
            "reason": "No supported medication detected.",
            "drug": None,
            "severity": "SAFE",
        }

    conditions = []

    if "chronic kidney disease" in text or "ckd" in text:
        conditions.append("Chronic Kidney Disease")

    if "asthma" in text:
        conditions.append("Asthma")

    medications = []

    if "warfarin" in text and proposed_drug != "warfarin":
        medications.append("warfarin")

    if "aspirin" in text and proposed_drug != "aspirin":
        medications.append("aspirin")

    allergies = []

    if "penicillin allergy" in text:
        allergies.append("Penicillin")

    status, alerts, canonical_drug, _ = (
        evaluate_full_safety(
            proposed_drug,
            conditions,
            medications,
            allergies,
            None
        )
    )

    if alerts:

        first_alert = alerts[0]

        reason = (
            f"{first_alert['conflicting_factor']}: "
            f"{first_alert['clinical_mechanism']} "
            f"{first_alert['recommendation']}"
        )

        return {
            "flagged": True,
            "reason": reason,
            "drug": canonical_drug,
            "severity": status,
        }

    return {
        "flagged": False,
        "reason": "No adverse interactions detected.",
        "drug": None,
        "severity": "SAFE",
    }