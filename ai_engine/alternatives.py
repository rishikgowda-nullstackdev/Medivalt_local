"""
Safe medication alternatives for MediVault Local.

This module provides a small local formulary of alternatives
for common safety scenarios.

It does not make the safety decision.
It is only used after the deterministic safety engine
has identified a CRITICAL or WARNING finding.
"""


class SafeAlternativeRecommender:
    """Deterministic safe-alternative recommender."""

    ALTERNATIVES = {
        "ibuprofen": [
            {
                "alternative_drug": "Acetaminophen",
                "dosage_guide": "500mg PO Q6H; follow appropriate daily maximum",
                "rationale": (
                    "Provides analgesic and antipyretic effects without "
                    "the same NSAID-related renal prostaglandin effects."
                ),
                "target_indication": "Pain Management",
            }
        ],

        "naproxen": [
            {
                "alternative_drug": "Acetaminophen",
                "dosage_guide": "500mg PO Q6H; follow appropriate daily maximum",
                "rationale": (
                    "Provides analgesic and antipyretic effects without "
                    "NSAID-related renal effects."
                ),
                "target_indication": "Pain Management",
            }
        ],

        "diclofenac": [
            {
                "alternative_drug": "Acetaminophen",
                "dosage_guide": "500mg PO Q6H; follow appropriate daily maximum",
                "rationale": (
                    "Provides pain relief without the same NSAID "
                    "mechanism."
                ),
                "target_indication": "Pain Management",
            }
        ],

        "amoxicillin": [
            {
                "alternative_drug": "Azithromycin",
                "dosage_guide": "Use according to the diagnosed infection and clinical guidance",
                "rationale": (
                    "May provide an alternative antibiotic option when "
                    "a penicillin-class allergy is present."
                ),
                "target_indication": "Bacterial Infection",
            }
        ],

        "propranolol": [
            {
                "alternative_drug": "Alternative non-beta-blocking therapy",
                "dosage_guide": "Determine according to the clinical indication",
                "rationale": (
                    "Avoids the non-selective beta-blocking mechanism "
                    "when that mechanism is clinically inappropriate."
                ),
                "target_indication": "Condition-specific",
            }
        ],
    }

    @classmethod
    def get_safe_alternatives(
        cls,
        proposed_med: str,
        conditions: list[str],
        allergies: list[str]
    ) -> list[dict]:
        """
        Return locally defined alternatives for the proposed medicine.

        The safety engine calls this only when a CRITICAL or WARNING
        finding has already been identified.
        """

        if not proposed_med:
            return []

        drug = proposed_med.strip().lower()

        # Normalize a few common brand names locally.
        aliases = {
            "advil": "ibuprofen",
            "motrin": "ibuprofen",
            "brufen": "ibuprofen",
            "amoxil": "amoxicillin",
            "inderal": "propranolol",
        }

        drug = aliases.get(drug, drug)

        alternatives = cls.ALTERNATIVES.get(drug, [])

        # Return copies so callers cannot accidentally modify
        # the underlying formulary.
        return [alternative.copy() for alternative in alternatives]