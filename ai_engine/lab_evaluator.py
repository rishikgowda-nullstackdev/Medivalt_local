"""
MediVault Local - Quantitative Lab Biomarker Threshold Evaluator (Person C)
Deterministic evaluation of patient numerical lab values against SQLite clinical safety cutoffs.
Guarantees 0% hallucination by executing strict mathematical inequalities (<, <=, >, >=).
"""

import os
import sqlite3
from typing import Dict, List, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


class LabBiomarkerEvaluator:
    """Evaluates quantitative organ function and biomarker cutoffs against contraindications_lab table."""

    @staticmethod
    def get_db():
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def evaluate_drug_against_labs(
        cls,
        canonical_drug: str,
        detected_brand: Optional[str],
        labs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks proposed drug against patient numerical lab values.
        Supports eGFR, Creatinine, Potassium, INR, and Platelets.
        """
        if not labs:
            return []

        alerts = []
        conn = cls.get_db()
        cursor = conn.cursor()

        # Query all threshold rules for this drug, prioritizing CRITICAL over WARNING
        drug_search = canonical_drug.lower()
        cursor.execute("""
            SELECT biomarker_name, operator, threshold_value, unit, severity, mechanism, recommendation
            FROM contraindications_lab
            WHERE drug_name = ? OR ? LIKE '%' || drug_name || '%'
            ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END ASC, threshold_value ASC
        """, (drug_search, drug_search))

        rules = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not rules:
            return []

        # Normalize lab keys for case-insensitive matching
        normalized_labs: Dict[str, float] = {}
        for k, v in labs.items():
            key_clean = k.strip().lower()
            if isinstance(v, dict) and "value" in v:
                try:
                    normalized_labs[key_clean] = float(v["value"])
                except (ValueError, TypeError):
                    pass
            elif isinstance(v, (int, float)):
                normalized_labs[key_clean] = float(v)
            elif isinstance(v, str):
                # Try extracting leading number
                import re
                m = re.search(r"(\d+\.?\d*)", v)
                if m:
                    normalized_labs[key_clean] = float(m.group(1))

        # Evaluate each rule
        triggered_biomarkers = set()
        for rule in rules:
            bio_key = rule["biomarker_name"].strip().lower()
            if bio_key not in normalized_labs:
                continue

            # If a CRITICAL rule already fired for this biomarker, avoid duplicate lower WARNING
            if bio_key in triggered_biomarkers and rule["severity"] != "CRITICAL":
                continue

            patient_val = normalized_labs[bio_key]
            thresh_val = float(rule["threshold_value"])
            op = rule["operator"]

            violation = False
            if op == "<" and patient_val < thresh_val:
                violation = True
            elif op == "<=" and patient_val <= thresh_val:
                violation = True
            elif op == ">" and patient_val > thresh_val:
                violation = True
            elif op == ">=" and patient_val >= thresh_val:
                violation = True

            if violation:
                triggered_biomarkers.add(bio_key)
                bio_label = rule["biomarker_name"].upper()
                drug_label = detected_brand or canonical_drug.title()

                factor = f"Quantitative Lab Hazard: Patient {bio_label} = {patient_val} {rule['unit']} (Threshold: {op} {thresh_val} {rule['unit']})"

                alerts.append({
                    "severity": rule["severity"],
                    "interaction_type": "LAB_THRESHOLD",
                    "conflicting_factor": factor,
                    "clinical_mechanism": rule["mechanism"],
                    "recommendation": rule["recommendation"],
                    "measured_value": patient_val,
                    "threshold_value": thresh_val,
                    "biomarker": bio_label
                })

        return alerts
