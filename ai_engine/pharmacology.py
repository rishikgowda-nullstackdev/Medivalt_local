"""
Local pharmacology knowledge base for MediVault Local.

This module provides deterministic:
- Brand -> generic drug normalization
- Allergy checking

No external APIs or cloud services are used.
"""


class PharmacologyKnowledge:
    """Deterministic local pharmacology knowledge base."""

    # Brand name -> generic name
    DRUG_ALIASES = {
        "advil": "ibuprofen",
        "motrin": "ibuprofen",
        "brufen": "ibuprofen",

        "tylenol": "acetaminophen",
        "paracetamol": "acetaminophen",

        "coumadin": "warfarin",

        "amoxil": "amoxicillin",

        "inderal": "propranolol",

        "prinivil": "lisinopril",
        "zestril": "lisinopril",
    }

    # Generic drug -> relevant allergy classes
    DRUG_CLASSES = {
        "amoxicillin": ["penicillin", "beta-lactam"],
        "penicillin": ["penicillin", "beta-lactam"],
        "ibuprofen": ["nsaid"],
        "aspirin": ["nsaid"],
        "warfarin": ["anticoagulant"],
        "propranolol": ["beta-blocker"],
        "lisinopril": ["ace-inhibitor"],
        "acetaminophen": ["analgesic"],
    }

    @classmethod
    def normalize_drug_name(
        cls,
        drug_name: str
    ) -> tuple[str, str | None]:
        """
        Convert a brand/alternate name to its canonical
        generic drug name.

        Returns:
            (canonical_drug, detected_brand)

        Examples:
            Advil -> ("ibuprofen", "Advil")
            Ibuprofen -> ("ibuprofen", None)
        """

        if not drug_name:
            return "", None

        original = drug_name.strip()
        normalized = original.lower()

        if normalized in cls.DRUG_ALIASES:
            canonical = cls.DRUG_ALIASES[normalized]
            return canonical, original

        return normalized, None

    @classmethod
    def check_allergies(
        cls,
        drug_name: str,
        allergies: list[str]
    ) -> list[dict]:
        """
        Check the proposed drug against documented allergies.

        Returns alerts using the project's standard alert schema.
        """

        if not drug_name or not allergies:
            return []

        canonical_drug, _ = cls.normalize_drug_name(drug_name)

        drug_classes = cls.DRUG_CLASSES.get(
            canonical_drug,
            []
        )

        alerts = []

        for allergy in allergies:

            if not allergy:
                continue

            normalized_allergy = allergy.strip().lower()

            # Direct drug allergy
            if normalized_allergy == canonical_drug:

                alerts.append({
                    "severity": "CRITICAL",
                    "interaction_type": "ALLERGY",
                    "conflicting_factor": allergy,
                    "clinical_mechanism": (
                        f"Patient has a documented allergy "
                        f"to {canonical_drug}."
                    ),
                    "recommendation": (
                        f"Avoid {canonical_drug} and consider "
                        "a suitable alternative."
                    ),
                })

            # Drug-class allergy
            elif normalized_allergy in drug_classes:

                alerts.append({
                    "severity": "CRITICAL",
                    "interaction_type": "ALLERGY",
                    "conflicting_factor": allergy,
                    "clinical_mechanism": (
                        f"{canonical_drug} belongs to the "
                        f"{normalized_allergy} class."
                    ),
                    "recommendation": (
                        f"Avoid {canonical_drug} because of the "
                        f"documented {allergy} allergy."
                    ),
                })

        return alerts