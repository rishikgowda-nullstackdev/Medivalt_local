"""
Lab biomarker safety checks for MediVault Local.

This module checks quantitative laboratory values against
simple medication-specific safety thresholds.

The result is a list of deterministic safety alerts.
"""


class LabBiomarkerEvaluator:
    """Deterministic laboratory safety evaluator."""

    @staticmethod
    def evaluate_drug_against_labs(
        canonical_drug: str,
        detected_brand: str | None,
        labs: dict | None
    ) -> list[dict]:
        """
        Evaluate a proposed drug against available laboratory values.

        Returns a list of alerts using the project's standard
        alert schema.
        """

        if not canonical_drug or not labs:
            return []

        drug = canonical_drug.strip().lower()

        alerts = []

        # --------------------------------------------------
        # 1. IBUPROFEN / NSAID + LOW eGFR
        # --------------------------------------------------

        if drug in {
            "ibuprofen",
            "naproxen",
            "diclofenac",
            "aspirin",
        }:
            egfr = LabBiomarkerEvaluator._get_lab(
                labs,
                "egfr"
            )

            if egfr is not None and egfr < 30:
                alerts.append({
                    "severity": "CRITICAL",
                    "interaction_type": "LAB_THRESHOLD",
                    "conflicting_factor": (
                        f"eGFR: {egfr} mL/min/1.73m²"
                    ),
                    "clinical_mechanism": (
                        "Reduced kidney function increases the risk "
                        "of renal complications from NSAID therapy."
                    ),
                    "recommendation": (
                        "Avoid or reconsider NSAID therapy and "
                        "review a safer alternative."
                    ),
                })

        # --------------------------------------------------
        # 2. METFORMIN + LOW eGFR
        # --------------------------------------------------

        if drug == "metformin":
            egfr = LabBiomarkerEvaluator._get_lab(
                labs,
                "egfr"
            )

            if egfr is not None and egfr < 30:
                alerts.append({
                    "severity": "CRITICAL",
                    "interaction_type": "LAB_THRESHOLD",
                    "conflicting_factor": (
                        f"eGFR: {egfr} mL/min/1.73m²"
                    ),
                    "clinical_mechanism": (
                        "Severely reduced kidney function can increase "
                        "the risk associated with metformin therapy."
                    ),
                    "recommendation": (
                        "Do not use metformin at this level of kidney "
                        "function; review alternative treatment."
                    ),
                })

        # --------------------------------------------------
        # 3. WARFARIN + HIGH INR
        # --------------------------------------------------

        if drug == "warfarin":
            inr = LabBiomarkerEvaluator._get_lab(
                labs,
                "inr"
            )

            if inr is not None and inr > 4:
                alerts.append({
                    "severity": "WARNING",
                    "interaction_type": "LAB_THRESHOLD",
                    "conflicting_factor": f"INR: {inr}",
                    "clinical_mechanism": (
                        "A markedly elevated INR indicates increased "
                        "anticoagulation and may increase bleeding risk."
                    ),
                    "recommendation": (
                        "Review anticoagulation status and current "
                        "warfarin therapy."
                    ),
                })

        return alerts

    @staticmethod
    def _get_lab(labs: dict, name: str):
        """
        Retrieve a laboratory value from the supplied dictionary.

        Supports both:
            {"egfr": 28}

        and:
            {"eGFR": 28}
        """

        if name in labs:
            return LabBiomarkerEvaluator._to_number(labs[name])

        # Case-insensitive lookup
        for key, value in labs.items():
            if str(key).lower() == name.lower():
                return LabBiomarkerEvaluator._to_number(value)

        return None

    @staticmethod
    def _to_number(value):
        """Convert a laboratory value to a number when possible."""

        try:
            return float(value)
        except (TypeError, ValueError):
            return None