"""
MediVault Local - Clinical Pharmacology & Drug Lexicon (Person C)
Normalizes brand names to canonical molecules and maps pharmacological classes.
"""

import re
from typing import Dict, List, Tuple, Optional, Any

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
    "lovenox": "enoxaparin",

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
    "avapro": "irbesartan",

    # Diuretics
    "lasix": "furosemide",
    "aldactone": "spironolactone",
    "microzide": "hydrochlorothiazide",

    # Antidiabetics
    "glucophage": "metformin",
    "jardiance": "empagliflozin",
    "farxiga": "dapagliflozin",
    "invokana": "canagliflozin",
    "glucotrol": "glipizide",
    "tradjenta": "linagliptin",

    # Antimicrobials
    "augmentin": "amoxicillin",
    "amoxil": "amoxicillin",
    "cipro": "ciprofloxacin",
    "levaquin": "levofloxacin",
    "biaxin": "clarithromycin",
    "zithromax": "azithromycin",
    "bactrim": "sulfamethoxazole",
    "septra": "sulfamethoxazole",
    "zyvox": "linezolid",

    # Psychotropics & Cardiac
    "prozac": "fluoxetine",
    "zoloft": "sertraline",
    "paxil": "paroxetine",
    "celexa": "citalopram",
    "lexapro": "escitalopram",
    "haldol": "haloperidol",
    "zofran": "ondansetron",
    "pacerone": "amiodarone",
    "cordarone": "amiodarone",
    "eldepryl": "selegiline"
}

# Chemical & Mechanistic Drug Classes for Polypharmacy Checking
DRUG_CLASSES = {
    "ace_inhibitor_or_arb": [
        "lisinopril", "enalapril", "ramipril", "benazepril", "fosinopril",
        "losartan", "valsartan", "candesartan", "irbesartan", "olmesartan"
    ],
    "diuretic": [
        "furosemide", "hydrochlorothiazide", "spironolactone", "bumetanide",
        "torsemide", "chlorthalidone", "metolazone", "indapamide"
    ],
    "nsaid": [
        "ibuprofen", "naproxen", "diclofenac", "meloxicam", "ketorolac",
        "indomethacin", "celecoxib", "aspirin", "piroxicam", "sulindac"
    ],
    "qt_prolonging_cardiac": [
        "amiodarone", "sotalol", "dronedarone", "dofetilide", "ibutilide", "quinidine", "procainamide"
    ],
    "qt_prolonging_antimicrobial": [
        "azithromycin", "clarithromycin", "erythromycin", "ciprofloxacin",
        "levofloxacin", "moxifloxacin", "fluconazole", "ketoconazole"
    ],
    "qt_prolonging_psych_or_antiemetic": [
        "haloperidol", "ondansetron", "citalopram", "escitalopram",
        "chlorpromazine", "quetiapine", "ziprasidone", "droperidol"
    ],
    "ssri_or_snri": [
        "fluoxetine", "sertraline", "paroxetine", "citalopram", "escitalopram",
        "fluvoxamine", "venlafaxine", "duloxetine", "desvenlafaxine"
    ],
    "serotonergic_analgesic": [
        "tramadol", "meperidine", "methadone", "tapentadol", "fentanyl"
    ],
    "maoi_or_triptan": [
        "selegiline", "phenelzine", "tranylcypromine", "rasagiline", "linezolid",
        "sumatriptan", "zolmitriptan", "rizatriptan"
    ],
    "penicillin": [
        "penicillin", "amoxicillin", "ampicillin", "piperacillin", "augmentin", "nafcillin"
    ],
    "sulfa": [
        "sulfamethoxazole", "bactrim", "sulfasalazine", "celecoxib", "sulfadiazine"
    ],
    "opioid": [
        "codeine", "morphine", "oxycodone", "hydrocodone", "tramadol", "fentanyl", "hydromorphone"
    ]
}


class PharmacologyKnowledge:
    """Pharmacology utility for brand normalization, classification, and allergy screening."""

    @classmethod
    def normalize_drug_name(cls, raw_input: str) -> Tuple[str, Optional[str]]:
        """
        Normalizes brand names or raw prescription strings to canonical generic names.
        Example: 'Advil 400mg PO' -> ('ibuprofen', 'Advil')
        """
        clean_input = raw_input.strip().lower()
        words = re.findall(r"\b[a-zA-Z-]+\b", clean_input)

        detected_brand = None
        generic_name = clean_input

        for word in words:
            if word in BRAND_TO_GENERIC:
                detected_brand = word.title()
                generic_name = BRAND_TO_GENERIC[word]
                break

        if not detected_brand:
            for word in words:
                if word in BRAND_TO_GENERIC.values():
                    generic_name = word
                    break

        return generic_name, detected_brand

    @classmethod
    def get_drug_classes(cls, drug_name: str) -> List[str]:
        """Returns all pharmacological classes associated with a given molecule."""
        canonical, _ = cls.normalize_drug_name(drug_name)
        search_drug = canonical.lower()

        matched_classes = []
        for class_name, drugs in DRUG_CLASSES.items():
            if search_drug in drugs or any(d in search_drug for d in drugs):
                matched_classes.append(class_name)

        return matched_classes

    @classmethod
    def check_allergies(cls, proposed_drug: str, patient_allergies: List[str]) -> List[Dict[str, Any]]:
        """Cross-checks proposed drug against patient allergies including class cross-reactivity."""
        alerts = []
        canonical_drug, brand = cls.normalize_drug_name(proposed_drug)
        drug_search = canonical_drug.lower()

        for allergy in patient_allergies:
            allergy_clean = allergy.strip().lower()
            if not allergy_clean or "nkda" in allergy_clean or "none" in allergy_clean:
                continue

            matched = False
            mechanism = ""

            # Direct drug match
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
                mechanism = f"Cross-reactivity: '{proposed_drug}' contains sulfonamide moieties; high risk of cutaneous adverse reactions (Stevens-Johnson syndrome)."

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
