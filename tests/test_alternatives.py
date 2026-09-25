"""
MediVault Local - Clinical Safe Alternatives Recommender Test Suite
Verifies:
1. Formulary lookup for blocked NSAIDs in CKD / Peptic Ulcer.
2. Formulary lookup for blocked Beta-Blockers in Asthma.
3. Allergy-aware filtering (ensuring proposed alternative does not conflict with patient allergies).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine.alternatives import SafeAlternativeRecommender


class TestSafeAlternatives(unittest.TestCase):

    def test_01_ibuprofen_alternatives_in_ckd(self):
        """Blocked Ibuprofen in CKD must return Acetaminophen or Topical Lidocaine Patch."""
        alts = SafeAlternativeRecommender.get_safe_alternatives(
            "Ibuprofen",
            conditions=["Stage 3 Chronic Kidney Disease"],
            patient_allergies=[]
        )
        self.assertGreaterEqual(len(alts), 1)
        drug_names = [a["alternative_drug"] for a in alts]
        self.assertIn("Acetaminophen", drug_names)

    def test_02_propranolol_alternatives_in_asthma(self):
        """Blocked Propranolol in Asthma must return Cardioselective Metoprolol or Amlodipine."""
        alts = SafeAlternativeRecommender.get_safe_alternatives(
            "Propranolol",
            conditions=["Bronchial Asthma"],
            patient_allergies=[]
        )
        self.assertGreaterEqual(len(alts), 1)
        drug_names = [a["alternative_drug"] for a in alts]
        self.assertTrue("Metoprolol Succinate" in drug_names or "Amlodipine" in drug_names)

    def test_03_allergy_filtering_on_alternatives(self):
        """Alternatives must not suggest drugs that conflict with patient documented allergies."""
        # Suppose a patient has a documented allergy to Aspirin/NSAIDs
        alts = SafeAlternativeRecommender.get_safe_alternatives(
            "Naproxen",
            conditions=["Chronic Kidney Disease"],
            patient_allergies=["Aspirin", "NSAIDs"]
        )
        # Should return Acetaminophen, never another NSAID
        for a in alts:
            self.assertNotEqual(a["alternative_drug"].lower(), "aspirin")
            self.assertNotEqual(a["alternative_drug"].lower(), "ibuprofen")

    def test_04_metformin_alternatives_in_severe_ckd(self):
        """Blocked Metformin in severe CKD must suggest Linagliptin (0% renal elimination)."""
        alts = SafeAlternativeRecommender.get_safe_alternatives(
            "Metformin",
            conditions=["Chronic Kidney Disease"],
            patient_allergies=[]
        )
        drug_names = [a["alternative_drug"] for a in alts]
        self.assertIn("Linagliptin", drug_names)


if __name__ == "__main__":
    unittest.main()
