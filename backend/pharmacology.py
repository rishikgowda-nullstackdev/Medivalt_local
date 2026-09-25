"""
MediVault Local - Clinical Pharmacology & Drug Synonym Engine
Provides brand-to-generic drug normalization, class classification,
and drug-allergy cross-reactivity checking.
"""

import re
from typing import Dict, List, Tuple, Optional, Any

# ---------------------------------------------------------------------------
# Brand Name to Generic Drug Mapping Lexicon
# ---------------------------------------------------------------------------
BRAND_TO_GENERIC = {
    # NSAIDs
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "nurofen": "ibuprofen",
    "midol": "ibuprofen",
    "aleve": "naproxen",
    "naprosyn": "naproxen",
    "anaprox": "naproxen",
    "voltaren": "diclofenac",
    "cataflam": "diclofenac",
    "mobic": "meloxicam",
    "toradol": "ketorolac",
    "celebrex": "celecoxib",
    "bayer": "aspirin",
    "ecotrin": "aspirin",

    # Analgesics & Antipyretics
    "tylenol": "acetaminophen",
    "panadol": "acetaminophen",
    "calpol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "ultram": "tramadol",

    # Anticoagulants & Antiplatelets
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "plavix": "clopidogrel",
    "eliquis": "apixaban",
    "xarelto": "rivaroxaban",
    "brilinta": "ticagrelor",

    # Beta-Blockers
    "inderal": "propranolol",
    "tenormin": "atenolol",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "toprol-xl": "metoprolol",
    "zebeta": "bisoprolol",
    "coreg": "carvedilol",
    "trandate": "labetalol",
    "timoptic": "timolol",
    "corgard": "nadolol",

    # ACE Inhibitors & ARBs
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "vasotec": "enalapril",
    "altace": "ramipril",
    "cozaar": "losartan",
    "diovan": "valsartan",

    # Calcium Channel Blockers
    "norvasc": "amlodipine",
    "procardia": "nifedipine",
    "cardizem": "diltiazem",

    # Antidiabetics
    "glucophage": "metformin",
    "jardiance": "empagliflozin",
    "farxiga": "dapagliflozin",
    "invokana": "canagliflozin",
    "glucotrol": "glipizide",

    # Statins
    "zocor": "simvastatin",
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "pravachol": "pravastatin",
    "lopid": "gemfibrozil",

    # Acid Suppressants
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "protonix": "pantoprazole",
    "prevacid": "lansoprazole",

    # Psychotropics & SSRIs
    "prozac": "fluoxetine",
    "zoloft": "sertraline",
    "paxil": "paroxetine",
    "celexa": "citalopram",
    "lexapro": "escitalopram",
    "eldepryl": "selegiline",

    # Antimicrobials
    "augmentin": "amoxicillin",
    "amoxil": "amoxicillin",
    "cipro": "ciprofloxacin",
    "levaquin": "levofloxacin",
    "biaxin": "clarithromycin",
    "zithromax": "azithromycin",
    "bactrim": "sulfamethoxazole",
    "septra": "sulfamethoxazole",

    # Diuretics
    "aldactone": "spironolactone",
    "lasix": "furosemide"
}

# ---------------------------------------------------------------------------
# Drug Class & Allergy Cross-Reactivity Mapping
# ---------------------------------------------------------------------------
DRUG_CLASSES = {
    "penicillin": ["amoxicillin", "ampicillin", "piperacillin", "penicillin", "augmentin"],
    "sulfa": ["sulfamethoxazole", "bactrim", "sulfasalazine", "celecoxib"],
    "nsaid": ["ibuprofen", "naproxen", "diclofenac", "meloxicam", "ketorolac", "aspirin", "indomethacin"],
    "opioid": ["codeine", "morphine", "oxycodone", "hydrocodone", "tramadol", "fentanyl"],
    "beta_blocker": ["propranolol", "atenolol", "metoprolol", "bisoprolol", "carvedilol", "timolol", "nadolol"]
}


class PharmacologyEngine:
    """Pharmacology utility for brand normalization and allergy screening."""

    @classmethod
    def normalize_drug_name(cls, raw_input: str) -> Tuple[str, Optional[str]]:
        """
        Normalizes brand names or raw prescription text to canonical generic name.
        Example: 'Advil 400mg PO' -> ('ibuprofen', 'Advil')
        """
        clean_input = raw_input.strip().lower()

        # Extract words from input
        words = re.findall(r"\b[a-zA-Z-]+\b", clean_input)

        detected_brand = None
        generic_name = clean_input

        for word in words:
            if word in BRAND_TO_GENERIC:
                detected_brand = word.title()
                generic_name = BRAND_TO_GENERIC[word]
                break

        # If no brand found, check if a known generic word exists
        if not detected_brand:
            for word in words:
                if word in BRAND_TO_GENERIC.values():
                    generic_name = word
                    break

        return generic_name, detected_brand

    @classmethod
    def check_drug_allergies(cls, proposed_drug: str, patient_allergies: List[str]) -> List[Dict[str, Any]]:
        """
        Cross-checks proposed drug against patient documented allergies.
        Detects class cross-reactions (e.g., Penicillin allergy vs Amoxicillin).
        """
        alerts = []
        canonical_drug, brand = cls.normalize_drug_name(proposed_drug)
        drug_search = canonical_drug.lower()

        for allergy in patient_allergies:
            allergy_clean = allergy.strip().lower()
            if not allergy_clean or "nkda" in allergy_clean or "none" in allergy_clean:
                continue

            matched = False
            mechanism = ""

            # Direct drug allergy match
            if drug_search in allergy_clean or allergy_clean in drug_search:
                matched = True
                mechanism = f"Direct documented allergy to '{allergy}'. Immediate risk of acute allergic hypersensitivity."

            # Cross-reaction: Penicillin allergy
            elif "penicillin" in allergy_clean and drug_search in DRUG_CLASSES["penicillin"]:
                matched = True
                mechanism = f"Cross-reactivity: '{proposed_drug}' is a beta-lactam antibiotic. Severe risk of anaphylaxis in penicillin-allergic patients."

            # Cross-reaction: Sulfa allergy
            elif ("sulfa" in allergy_clean or "sulfonamide" in allergy_clean) and drug_search in DRUG_CLASSES["sulfa"]:
                matched = True
                mechanism = f"Cross-reactivity: '{proposed_drug}' contains sulfonamide moieties; high risk of cutaneous adverse reactions."

            # Cross-reaction: Aspirin / NSAID allergy (Samter's Triad)
            elif ("aspirin" in allergy_clean or "nsaid" in allergy_clean) and drug_search in DRUG_CLASSES["nsaid"]:
                matched = True
                mechanism = f"Aspirin/NSAID cross-reactivity: Risk of severe bronchospasm, urticaria, or anaphylactoid reaction."

            # Cross-reaction: Opioid allergy
            elif ("codeine" in allergy_clean or "morphine" in allergy_clean or "opioid" in allergy_clean) and drug_search in DRUG_CLASSES["opioid"]:
                matched = True
                mechanism = f"Opioid cross-reactivity: Risk of severe adverse histamine release or allergic reaction."

            if matched:
                alerts.append({
                    "severity": "CRITICAL",
                    "interaction_type": "ALLERGY",
                    "conflicting_factor": f"Documented Allergy: {allergy}",
                    "clinical_mechanism": mechanism,
                    "recommendation": f"Absolute contraindication. Avoid '{proposed_drug}'. Select an alternative from an unrelated chemical class."
                })

        return alerts
