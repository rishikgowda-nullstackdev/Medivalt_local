"""
MediVault Local - 5-Scenario Verification Runner (Person B)
Validates the 5 key clinical scenarios against Person B's ingestion pipeline.
"""

from ingestion.pipeline import extract_entities, process_file

SCENARIOS = [
    {
        "id": 1,
        "name": "CKD Stage 3 + Ibuprofen (Drug-Disease Contraindication)",
        "note": (
            "PATIENT NAME: John Doe | DOB: 05/12/1959 | MRN: 9948201\n"
            "SSN: 000-12-3456 | PHONE: (555) 234-5678\n"
            "Patient has Stage 3 Chronic Kidney Disease (CKD), baseline serum creatinine 2.1 mg/dL, eGFR 28 mL/min/1.73m2. "
            "Currently taking Lisinopril 20mg daily. Considering prescribing Ibuprofen 400mg TID for knee pain."
        ),
        "expected_conditions": ["Chronic Kidney Disease"],
        "expected_medications": ["Ibuprofen", "Lisinopril"],
        "expected_lab_biomarkers": {"eGFR": "CRITICAL_LOW", "Creatinine": "HIGH"},
    },
    {
        "id": 2,
        "name": "Asthma + Propranolol (Drug-Disease Contraindication)",
        "note": (
            "PATIENT NAME: Amanda Rollins | DOB: 03/22/1982 | MRN: 7729103\n"
            "PHONE: (555) 876-1234 | EMAIL: arollins@example.com\n"
            "Patient with Moderate Persistent Bronchial Asthma. "
            "Active medications: Albuterol 90mcg PRN. Proposing Propranolol 40mg for migraine prophylaxis."
        ),
        "expected_conditions": ["Asthma"],
        "expected_medications": ["Albuterol", "Propranolol"],
    },
    {
        "id": 3,
        "name": "Atrial Fibrillation / Warfarin + Aspirin (Drug-Drug Interaction)",
        "note": (
            "PATIENT NAME: Arthur Pendelton | DOB: 11/05/1953 | MRN: 3341908\n"
            "SSN: 999-88-7777 | PHONE: (555) 987-6543\n"
            "History of Atrial Fibrillation and Deep Vein Thrombosis. "
            "Active prescriptions: Warfarin 5mg daily. Lab INR 2.4. Inquiring regarding over-the-counter Aspirin."
        ),
        "expected_conditions": ["Atrial Fibrillation", "Deep Vein Thrombosis"],
        "expected_medications": ["Aspirin", "Warfarin"],
        "expected_lab_biomarkers": {"INR": "NORMAL"},
    },
    {
        "id": 4,
        "name": "Penicillin Allergy + Amoxicillin (Allergy Cross-Reactivity)",
        "note": (
            "PATIENT NAME: Priya Nair | DOB: 07/09/1985 | MRN: 6620318\n"
            "SSN: 444-55-6666 | PHONE: 98765 43210\n"
            "Diagnosed with Essential Hypertension. Documented Allergies: Penicillin (anaphylaxis). "
            "Considering Amoxicillin 500mg for acute sinusitis."
        ),
        "expected_conditions": ["Hypertension"],
        "expected_medications": ["Amoxicillin"],
        "expected_allergies": ["Penicillin"],
    },
    {
        "id": 5,
        "name": "Safe Case: Hypertension + Lisinopril (Cleared)",
        "note": (
            "PATIENT NAME: David Miller | DOB: 01/14/1975 | MRN: 1102948\n"
            "SSN: 333-22-1111 | PHONE: (555) 321-7654\n"
            "Routine follow-up for Essential Hypertension. BP 128/82 mmHg, eGFR 92 mL/min/1.73m2. "
            "No known drug allergies. Prescribing Lisinopril 10mg daily."
        ),
        "expected_conditions": ["Hypertension"],
        "expected_medications": ["Lisinopril"],
        "expected_lab_biomarkers": {"eGFR": "NORMAL", "BloodPressure": "NORMAL"},
    },
]


def run_benchmark():
    print("=" * 70)
    print("MediVault Local — Ingestion Benchmark (5 Clinical Scenarios)")
    print("=" * 70)

    all_passed = True
    for sc in SCENARIOS:
        print(f"\nScenario {sc['id']}: {sc['name']}")

        # 1. Test Redaction
        redacted = process_file(sc["note"].encode("utf-8"), filename="note.txt")
        assert "[REDACTED_NAME]" in redacted, f"Failed name redaction in scenario {sc['id']}"
        assert "[REDACTED_PHONE]" in redacted, f"Failed phone redaction in scenario {sc['id']}"

        # 2. Test Clinical Extraction
        entities = extract_entities(redacted)

        # Check conditions
        for cond in sc.get("expected_conditions", []):
            if cond not in entities["diagnosed_conditions"]:
                print(f"  ❌ Missing expected condition: {cond}")
                all_passed = False
            else:
                print(f"  ✅ Condition identified: {cond}")

        # Check medications
        for med in sc.get("expected_medications", []):
            if not any(med.lower() in m.lower() for m in entities["current_medications"]):
                print(f"  ❌ Missing expected medication: {med}")
                all_passed = False
            else:
                print(f"  ✅ Medication identified: {med}")

        # Check allergies
        for allergy in sc.get("expected_allergies", []):
            if not any(allergy.lower() in a.lower() for a in entities["allergies"]):
                print(f"  ❌ Missing expected allergy: {allergy}")
                all_passed = False
            else:
                print(f"  ✅ Allergy identified: {allergy}")

        # Check biomarkers
        for bio, status in sc.get("expected_lab_biomarkers", {}).items():
            actual = entities["biomarkers"].get(bio, {}).get("status")
            if actual != status:
                print(f"  ❌ Biomarker {bio} status mismatch: expected {status}, got {actual}")
                all_passed = False
            else:
                print(f"  ✅ Biomarker {bio} evaluated correctly: {status}")

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL 5 CLINICAL BENCHMARK SCENARIOS: ✅ PASS")
    else:
        print("SOME BENCHMARK SCENARIOS: ❌ FAIL")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = run_benchmark()
    exit(0 if success else 1)
