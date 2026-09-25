"""
MediVault Local - Geriatric & Renal Decision Support Engine (Person C)
Standards: 2023 American Geriatrics Society (AGS) Beers Criteria & Cockcroft-Gault CrCl Titration.
Provides zero-cloud calculation of:
- Cockcroft-Gault Creatinine Clearance (CrCl) from structured demographics & serum creatinine.
- Dynamic narrow-therapeutic drug dose adjustment and interval extensions.
- Geriatric inappropriate medication screening for anticholinergic delirium, ataxia, and fall hazards.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


def calculate_cockcroft_gault(
    age: int,
    weight_kg: float,
    serum_creatinine: float,
    is_female: bool
) -> Optional[float]:
    """
    Computes Cockcroft-Gault Creatinine Clearance (CrCl in mL/min).
    Formula: CrCl = [((140 - Age) * Weight_kg) / (72 * Serum_Cr_mg_dL)] * (0.85 if female)
    """
    if age is None or weight_kg is None or serum_creatinine is None:
        return None
    if age <= 0 or weight_kg <= 0 or serum_creatinine <= 0:
        return None

    # Base calculation
    crcl = ((140.0 - float(age)) * float(weight_kg)) / (72.0 * float(serum_creatinine))
    if is_female:
        crcl *= 0.85

    return round(crcl, 1)


class GeriatricRenalEngine:
    """Evaluates narrow-therapeutic renal titration and 2023 AGS Beers Criteria rules."""

    @staticmethod
    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def evaluate_renal_titration(
        cls,
        drug_name: str,
        crcl: Optional[float],
        dose_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks proposed medication against renal clearance thresholds.
        """
        if crcl is None or not drug_name:
            return []

        clean_drug = drug_name.strip().lower()
        alerts = []

        try:
            conn = cls.get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT drug_name, crcl_threshold, operator, severity, titration_instruction, mechanism
                FROM renal_dosing_rules
                WHERE drug_name = ?
                ORDER BY crcl_threshold ASC
                """,
                (clean_drug,)
            )
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                thresh = float(row["crcl_threshold"])
                op = row["operator"]
                triggered = False

                if op == "<" and crcl < thresh:
                    triggered = True
                elif op == "<=" and crcl <= thresh:
                    triggered = True

                if triggered:
                    alerts.append({
                        "severity": row["severity"],
                        "interaction_type": "RENAL_TITRATION",
                        "conflicting_factor": f"CrCl {crcl} mL/min (Threshold: {op} {thresh} mL/min)",
                        "clinical_mechanism": row["mechanism"],
                        "recommendation": row["titration_instruction"],
                        "crcl": crcl
                    })
                    # Report most severe threshold match
                    break
        except Exception:
            pass

        return alerts

    @classmethod
    def evaluate_beers_criteria(
        cls,
        drug_name: str,
        age: Optional[int],
        conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Screens medication against 2023 AGS Beers Criteria for elderly patients (age >= 65).
        """
        if age is None or age < 65 or not drug_name:
            return []

        clean_drug = drug_name.strip().lower()
        alerts = []

        try:
            conn = cls.get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT drug_name, drug_class, min_age, severity, clinical_rationale, adverse_consequence, safe_alternative
                FROM beers_criteria_rules
                WHERE drug_name = ? AND min_age <= ?
                """,
                (clean_drug, age)
            )
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                alerts.append({
                    "severity": row["severity"],
                    "interaction_type": "BEERS_CRITERIA",
                    "conflicting_factor": f"Geriatric Age {age} (2023 AGS Beers Criteria: {row['drug_class']})",
                    "clinical_mechanism": f"{row['clinical_rationale']} Major risk of: {row['adverse_consequence']}.",
                    "recommendation": f"Avoid in older adults. Suggested Alternative: {row['safe_alternative']}.",
                    "safe_alternative": row["safe_alternative"]
                })
        except Exception:
            pass

        return alerts
