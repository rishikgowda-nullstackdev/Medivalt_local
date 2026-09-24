"""
Polypharmacy safety checks for MediVault Local.

This module performs deterministic checks for medication
combinations that may create clinically important syndromes.

The checks are:
1. Triple Whammy
2. QTc prolongation risk
3. Serotonin syndrome risk
"""


class PolypharmacyEngine:
    """Deterministic polypharmacy safety engine."""

    # Medicines/classes involved in Triple Whammy:
    # NSAID + ACE inhibitor/ARB + diuretic
    NSAIDS = {
        "ibuprofen",
        "aspirin",
        "naproxen",
        "diclofenac",
    }

    ACE_INHIBITORS = {
        "lisinopril",
        "enalapril",
        "ramipril",
    }

    ARBS = {
        "losartan",
        "valsartan",
        "telmisartan",
    }

    DIURETICS = {
        "furosemide",
        "hydrochlorothiazide",
        "spironolactone",
    }

    # Medicines associated with QT prolongation risk
    QT_DRUGS = {
        "amiodarone",
        "sotalol",
        "azithromycin",
        "clarithromycin",
        "ondansetron",
    }

    # Medicines associated with serotonergic activity
    SEROTONERGIC_DRUGS = {
        "sertraline",
        "fluoxetine",
        "escitalopram",
        "paroxetine",
        "venlafaxine",
        "duloxetine",
        "tramadol",
        "linezolid",
    }

    @classmethod
    def _normalize(cls, drug: str) -> str:
        """Normalize a medicine name for deterministic comparison."""

        if not drug:
            return ""

        return drug.strip().lower()

    @classmethod
    def evaluate_polypharmacy(
        cls,
        proposed_med: str,
        medications: list[str]
    ) -> list[dict]:
        """
        Evaluate the proposed medicine together with the
        patient's current medications.

        Returns a list of safety alerts.
        """

        proposed = cls._normalize(proposed_med)

        current_meds = {
            cls._normalize(med)
            for med in medications
            if med
        }

        # Include the proposed medication in the complete
        # medication list for combination checks.
        all_meds = current_meds | {proposed}

        alerts = []

        # --------------------------------------------------
        # 1. TRIPLE WHAMMY
        # --------------------------------------------------

        has_nsaid = bool(all_meds & cls.NSAIDS)
        has_ace_or_arb = bool(
            all_meds & (cls.ACE_INHIBITORS | cls.ARBS)
        )
        has_diuretic = bool(all_meds & cls.DIURETICS)

        if has_nsaid and has_ace_or_arb and has_diuretic:
            alerts.append({
                "severity": "CRITICAL",
                "interaction_type": "POLYPHARMACY",
                "conflicting_factor": "Triple Whammy medication combination",
                "clinical_mechanism": (
                    "Concurrent use of an NSAID, an ACE inhibitor or "
                    "ARB, and a diuretic can reduce renal perfusion "
                    "and increase the risk of acute kidney injury."
                ),
                "recommendation": (
                    "Review the combination and consider safer "
                    "alternatives where clinically appropriate."
                ),
            })

        # --------------------------------------------------
        # 2. QTc PROLONGATION
        # --------------------------------------------------

        qt_meds = all_meds & cls.QT_DRUGS

        if len(qt_meds) >= 2:
            alerts.append({
                "severity": "WARNING",
                "interaction_type": "POLYPHARMACY",
                "conflicting_factor": "Multiple QT-prolonging medications",
                "clinical_mechanism": (
                    "Concurrent use of multiple QT-prolonging medicines "
                    "may increase the risk of QT interval prolongation "
                    "and potentially serious cardiac arrhythmias."
                ),
                "recommendation": (
                    "Review the medication combination and consider "
                    "ECG monitoring or alternative therapy where appropriate."
                ),
            })

        # --------------------------------------------------
        # 3. SEROTONIN SYNDROME
        # --------------------------------------------------

        serotonergic_meds = all_meds & cls.SEROTONERGIC_DRUGS

        if len(serotonergic_meds) >= 2:
            alerts.append({
                "severity": "CRITICAL",
                "interaction_type": "POLYPHARMACY",
                "conflicting_factor": "Multiple serotonergic medications",
                "clinical_mechanism": (
                    "Concurrent use of multiple serotonergic medicines "
                    "may increase serotonergic activity and the risk "
                    "of serotonin syndrome."
                ),
                "recommendation": (
                    "Review the serotonergic medication combination "
                    "and consider safer alternatives where appropriate."
                ),
            })

        return alerts