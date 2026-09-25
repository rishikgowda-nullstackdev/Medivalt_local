"""
MediVault Local - Clinical Safe Alternatives Recommender (Person C)
Retrieves non-contraindicated formulary substitutes when a proposed prescription is blocked.
"""

import os
import sqlite3
from typing import Dict, List, Any, Optional
from ai_engine.pharmacology import PharmacologyKnowledge

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


class SafeAlternativeRecommender:
    """Finds clinically safe alternative medications from the local formulary."""

    @staticmethod
    def get_db():
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def get_safe_alternatives(
        cls,
        blocked_drug: str,
        conditions: List[str],
        patient_allergies: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Retrieves recommended safe alternative medications from safe_alternatives table.
        Verifies that candidates do not conflict with patient's documented allergies.
        """
        canonical_blocked, _ = PharmacologyKnowledge.normalize_drug_name(blocked_drug)
        drug_search = canonical_blocked.lower()

        conn = cls.get_db()
        cursor = conn.cursor()

        # Query alternatives for this blocked drug
        cursor.execute("""
            SELECT suggested_alternative, clinical_condition, dosage_guide, clinical_rationale
            FROM safe_alternatives
            WHERE blocked_drug = ? OR ? LIKE '%' || blocked_drug || '%'
        """, (drug_search, drug_search))

        candidates = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not candidates:
            return []

        safe_list = []
        for cand in candidates:
            alt_name = cand["suggested_alternative"]

            # Filter out alternatives that conflict with patient allergies
            allergy_alerts = PharmacologyKnowledge.check_allergies(alt_name, patient_allergies)
            if allergy_alerts:
                continue

            safe_list.append({
                "alternative_drug": alt_name,
                "dosage_guide": cand["dosage_guide"],
                "rationale": cand["clinical_rationale"],
                "target_indication": cand["clinical_condition"].title()
            })

        return safe_list
