"""
MediVault Local - Multi-Drug Polypharmacy Matrix Engine (Person C)
Detects lethal multi-drug combinations including 'The Triple Whammy',
Cumulative QTc Prolongation, and Additive Serotonin Syndrome.
"""

import os
import json
import sqlite3
from typing import Dict, List, Any, Optional
from ai_engine.pharmacology import PharmacologyKnowledge

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


class PolypharmacyEngine:
    """Evaluates multi-drug regimen synergies and cumulative pharmacological toxicity."""

    @staticmethod
    def get_db():
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def evaluate_polypharmacy(
        cls,
        proposed_drug: str,
        active_medications: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Analyzes the combined patient drug regimen (active meds + proposed med)
        for dangerous multi-drug class combinations.
        """
        all_drugs = list(active_medications) + [proposed_drug]
        if len(all_drugs) < 2:
            return []

        # Map each drug in regimen to its classes
        drug_to_classes: Dict[str, List[str]] = {}
        class_to_drugs: Dict[str, List[str]] = {}

        for d in all_drugs:
            classes = PharmacologyKnowledge.get_drug_classes(d)
            drug_to_classes[d] = classes
            for c in classes:
                if c not in class_to_drugs:
                    class_to_drugs[c] = []
                class_to_drugs[c].append(d)

        alerts = []

        # Query rules from polypharmacy_rules table
        conn = cls.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT rule_id, rule_name, required_classes, severity, mechanism, recommendation FROM polypharmacy_rules")
        rules = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Check each rule
        for rule in rules:
            try:
                req_classes = json.loads(rule["required_classes"])
            except Exception:
                continue

            # Check if all required classes are present in the combined regimen
            matching_drugs_cluster = []
            all_classes_matched = True

            for req_cls in req_classes:
                if req_cls in class_to_drugs and len(class_to_drugs[req_cls]) > 0:
                    matching_drugs_cluster.append(class_to_drugs[req_cls][0])
                else:
                    all_classes_matched = False
                    break

            if all_classes_matched and len(set(matching_drugs_cluster)) >= 2:
                # Make sure the proposed drug is actively contributing to the dangerous cluster
                proposed_classes = drug_to_classes.get(proposed_drug, [])
                if any(c in req_classes for c in proposed_classes):
                    cluster_str = " + ".join([d.title() for d in list(dict.fromkeys(matching_drugs_cluster))])

                    alerts.append({
                        "severity": rule["severity"],
                        "interaction_type": "POLYPHARMACY",
                        "rule_id": rule["rule_id"],
                        "rule_name": rule["rule_name"],
                        "conflicting_factor": f"Cumulative Polypharmacy Toxicity: [{cluster_str}]",
                        "interacting_drugs": list(dict.fromkeys(matching_drugs_cluster)),
                        "clinical_mechanism": rule["mechanism"],
                        "recommendation": rule["recommendation"]
                    })

        return alerts
