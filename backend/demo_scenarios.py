"""
MediVault Local - Interactive Judge Demo & Clinical Crisis Simulator
Provides 4 pre-staged, high-impact clinical disaster scenarios for hackathon presentations,
including doctor talking points, real-time multi-factor evaluations, and instant 1-click execution.
100% offline, zero-cloud sovereign execution.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from backend.orchestrator import ClinicalOrchestrator

demo_router = APIRouter(prefix="/api/demo", tags=["Judge Demo Simulator"])

CLINICAL_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "renal_collapse": {
        "id": "renal_collapse",
        "title": "The Silent Renal Collapse",
        "subtitle": "Severe Diabetic Nephropathy + Ketorolac (NSAID)",
        "badge": "CRITICAL LAB CONTRAINDICATION",
        "badge_color": "red",
        "icon": "🫘",
        "category": "Quantitative Lab Guardrail",
        "patient_id": "PT-101",
        "patient_name": "Marcus Vance",
        "demographics": {"age": 67, "gender": "Male"},
        "conditions": ["Chronic Kidney Disease Stage 3b", "Type 2 Diabetes Mellitus", "Essential Hypertension"],
        "active_medications": ["Lisinopril 20mg daily", "Metformin 500mg BID", "Amlodipine 5mg daily"],
        "allergies": ["Sulfonamides (Maculopapular rash)"],
        "labs": {
            "eGFR": {"value": 38.0, "unit": "mL/min/1.73m2", "status": "CRITICAL_LOW", "display": "38 mL/min/1.73m2 (Cutoff <45)"},
            "Creatinine": {"value": 2.1, "unit": "mg/dL", "status": "HIGH", "display": "2.1 mg/dL"},
            "Potassium": {"value": 4.6, "unit": "mEq/L", "status": "NORMAL", "display": "4.6 mEq/L"}
        },
        "proposed_medication": "Ketorolac",
        "dosage": "30mg IV Q6H",
        "clinical_note": (
            "PATIENT: Marcus Vance | AGE: 67 | SEX: Male | MRN: MGH-901-44\n"
            "DIAGNOSES: Chronic Kidney Disease Stage 3b (eGFR 38), Type 2 Diabetes Mellitus, Essential Hypertension\n"
            "ACTIVE MEDICATIONS:\n"
            "  - Lisinopril 20mg PO QD\n"
            "  - Metformin 500mg PO BID\n"
            "  - Amlodipine 5mg PO QD\n"
            "KNOWN ALLERGIES: Sulfonamides\n"
            "LABS: eGFR: 38 mL/min/1.73m2 | Creatinine: 2.1 mg/dL | K+: 4.6 mEq/L\n"
            "CLINICAL NOTE: Patient admitted for acute post-operative pain following orthopedic fixation. "
            "Attending orders Ketorolac 30mg IV Q6H for severe pain control."
        ),
        "hazard_summary": "Potent non-selective NSAID inhibits renal vasodilating prostaglandins (PGE2/PGI2), causing severe afferent arteriolar vasoconstriction and acute renal failure in baseline CKD.",
        "talking_points": [
            "Observe how MediVault checks the quantitative eGFR lab threshold (38 mL/min) before running inference.",
            "Ketorolac carries an absolute contraindication in renal impairment, but is frequently ordered by junior residents under pressure.",
            "1-Click Alternative Swap instantly recommends Acetaminophen 500mg (max 2g/day) with renal dosing."
        ],
        "safe_alternative": {
            "drug": "Acetaminophen",
            "dosage": "500mg PO TID (Max 2g/day)",
            "rationale": "Non-nephrotoxic centrally acting analgesic safe in moderate renal impairment."
        }
    },

    "triple_whammy": {
        "id": "triple_whammy",
        "title": "The Lethal 'Triple Whammy'",
        "subtitle": "ACE-Inhibitor + Loop Diuretic + High-Dose Ibuprofen",
        "badge": "POLYPHARMACY EMERGENCY",
        "badge_color": "red",
        "icon": "💔",
        "category": "Cumulative Polypharmacy Matrix",
        "patient_id": "PT-101",
        "patient_name": "Eleanor Rigby",
        "demographics": {"age": 72, "gender": "Female"},
        "conditions": ["Congestive Heart Failure", "Essential Hypertension", "Osteoarthritis"],
        "active_medications": ["Lisinopril 20mg daily", "Furosemide 40mg daily"],
        "allergies": ["Penicillin (Severe hives)"],
        "labs": {
            "eGFR": {"value": 52.0, "unit": "mL/min/1.73m2", "status": "NORMAL", "display": "52 mL/min/1.73m2"},
            "Creatinine": {"value": 1.3, "unit": "mg/dL", "status": "NORMAL", "display": "1.3 mg/dL"},
            "Potassium": {"value": 4.8, "unit": "mEq/L", "status": "NORMAL", "display": "4.8 mEq/L"}
        },
        "proposed_medication": "Ibuprofen",
        "dosage": "600mg PO TID",
        "clinical_note": (
            "PATIENT: Eleanor Rigby | AGE: 72 | SEX: Female | MRN: SJM-402-88\n"
            "DIAGNOSES: Congestive Heart Failure (NYHA Class II), Essential Hypertension, Knee Osteoarthritis\n"
            "ACTIVE MEDICATIONS:\n"
            "  - Lisinopril 20mg PO QD\n"
            "  - Furosemide 40mg PO QD\n"
            "ALLERGIES: Penicillin\n"
            "LABS: eGFR: 52 mL/min/1.73m2 | Creatinine: 1.3 mg/dL | K+: 4.8 mEq/L\n"
            "CHIEF COMPLAINT: Severe acute flare of bilateral knee osteoarthritis. "
            "Patient requests anti-inflammatory pain relief. Prescribing Ibuprofen 600mg TID."
        ),
        "hazard_summary": "Simultaneous afferent arteriolar constriction (Ibuprofen), efferent arteriolar dilation (Lisinopril), and volume depletion (Furosemide) collapses glomerular filtration pressure, precipitating acute dialysis-dependent renal failure.",
        "talking_points": [
            "Standard single-pair checkers often miss the 'Triple Whammy' because neither Lisinopril+Ibuprofen nor Furosemide+Ibuprofen alone triggers an absolute contraindication.",
            "MediVault's Multi-Drug Polypharmacy Matrix evaluates the multi-drug combination and catches the acute renal crisis.",
            "Demonstrates hospital-grade clinical decision support running entirely on local CPU."
        ],
        "safe_alternative": {
            "drug": "Celecoxib",
            "dosage": "100mg PO daily with renal monitoring",
            "rationale": "Or topical Diclofenac gel 1% to bypass systemic renal hemodynamic collapse."
        }
    },

    "hidden_anaphylaxis": {
        "id": "hidden_anaphylaxis",
        "title": "Hidden Beta-Lactam Cross-Allergy",
        "subtitle": "Severe Penicillin Allergy + Brand Name Augmentin",
        "badge": "ALLERGY CROSS-REACTIVITY",
        "badge_color": "red",
        "icon": "⚠️",
        "category": "Brand Normalization & Allergy Cross-Check",
        "patient_id": "PT-102",
        "patient_name": "David Miller",
        "demographics": {"age": 45, "gender": "Male"},
        "conditions": ["Acute Bacterial Sinusitis", "Moderate Persistent Asthma"],
        "active_medications": ["Albuterol HFA Inhaler 90mcg PRN", "Fluticasone Propionate 110mcg BID"],
        "allergies": ["Penicillin (Severe anaphylactic shock, ICU intubation)", "Aspirin (Bronchospasm)"],
        "labs": {
            "eGFR": {"value": 94.0, "unit": "mL/min/1.73m2", "status": "NORMAL", "display": "94 mL/min/1.73m2"},
            "Potassium": {"value": 4.1, "unit": "mEq/L", "status": "NORMAL", "display": "4.1 mEq/L"}
        },
        "proposed_medication": "Augmentin",
        "dosage": "875/125mg PO BID",
        "clinical_note": (
            "PATIENT: David Miller | AGE: 45 | SEX: Male | MRN: PPTH-108-19\n"
            "DIAGNOSES: Acute Bacterial Sinusitis, Moderate Persistent Asthma\n"
            "CURRENT MEDICATIONS:\n"
            "  - Albuterol HFA 90mcg PRN\n"
            "  - Fluticasone Propionate BID\n"
            "KNOWN ALLERGIES: Penicillin (severe anaphylaxis with laryngeal edema), Aspirin\n"
            "LABS: eGFR: 94 mL/min/1.73m2 | Potassium: 4.1 mEq/L\n"
            "ASSESSMENT: Purulent rhinorrhea and facial maxillary pressure x 12 days. "
            "Prescribe Augmentin 875/125mg PO BID x 10 days."
        ),
        "hazard_summary": "Augmentin is a trade brand containing Amoxicillin (a beta-lactam penicillin class antibiotic). Administration to a penicillin-allergic patient carries high risk of IgE-mediated anaphylactic shock and death.",
        "talking_points": [
            "In fast-paced ERs, doctors often forget that brand names like Augmentin conceal core beta-lactam structures.",
            "MediVault normalizes the brand name to Amoxicillin and cross-checks the chemical classification against the allergy profile.",
            "Instantly suggests safe non-beta-lactam options: Doxycycline 100mg BID or Azithromycin."
        ],
        "safe_alternative": {
            "drug": "Doxycycline",
            "dosage": "100mg PO BID x 7 days",
            "rationale": "Non-beta-lactam tetracycline antibiotic completely safe in penicillin-allergic individuals."
        }
    },

    "cumulative_qtc": {
        "id": "cumulative_qtc",
        "title": "Cumulative QTc Arrhythmia Risk",
        "subtitle": "Amiodarone + Azithromycin Synergy (Torsades de Pointes)",
        "badge": "TORSADES DE POINTES HAZARD",
        "badge_color": "orange",
        "icon": "⚡",
        "category": "Cardiac Electrophysiology Guardrail",
        "patient_id": "PT-103",
        "patient_name": "Robert Hayes",
        "demographics": {"age": 61, "gender": "Male"},
        "conditions": ["Atrial Fibrillation", "Community-Acquired Pneumonia"],
        "active_medications": ["Amiodarone 200mg daily", "Warfarin 5mg daily"],
        "allergies": ["Codeine (Severe nausea)"],
        "labs": {
            "INR": {"value": 2.4, "unit": "INR", "status": "NORMAL", "display": "2.4 (Target 2.0-3.0)"},
            "Platelets": {"value": 185.0, "unit": "x10^3/uL", "status": "NORMAL", "display": "185 x10^3/uL"}
        },
        "proposed_medication": "Azithromycin",
        "dosage": "500mg IV QD",
        "clinical_note": (
            "PATIENT: Robert Hayes | AGE: 61 | SEX: Male | MRN: MGH-901-72\n"
            "DIAGNOSES: Atrial Fibrillation, Community-Acquired Pneumonia, History of Ventricular Ectopy\n"
            "ACTIVE MEDICATIONS:\n"
            "  - Amiodarone 200mg PO QD\n"
            "  - Warfarin 5mg PO QD\n"
            "ALLERGIES: Codeine\n"
            "LABS: INR: 2.4 | Platelets: 185 x10^3/uL\n"
            "CLINICAL NOTE: Patient with baseline atrial fibrillation on chronic Amiodarone presents with fever, productive cough, and right lower lobe consolidation. "
            "Prescribe Azithromycin 500mg IV QD for atypical coverage."
        ),
        "hazard_summary": "Both Amiodarone and Azithromycin inhibit the cardiac hERG potassium channel, delaying myocardial ventricular repolarization. Concurrent use causes additive QTc prolongation (>500ms), precipitating polymorphic ventricular tachycardia (Torsades de Pointes) and sudden cardiac arrest.",
        "talking_points": [
            "Amiodarone has a massive half-life (over 50 days) and potent baseline QT prolongation.",
            "Adding a macrolide like Azithromycin or antiemetic like Ondansetron creates lethal synergistic cardiac repolarization delay.",
            "MediVault highlights the cumulative cardiac hazard and suggests non-QTc prolonging options like Doxycycline or Cefuroxime."
        ],
        "safe_alternative": {
            "drug": "Doxycycline",
            "dosage": "100mg IV Q12H",
            "rationale": "Atypical coverage for pneumonia with zero cardiac hERG potassium channel affinity."
        }
    }
}


@demo_router.get("/scenarios")
def list_demo_scenarios():
    """
    Returns the catalogue of 4 pre-staged high-impact clinical disaster scenarios
    for hackathon judging presentations.
    """
    scenarios_summary = []
    for s_id, s in CLINICAL_SCENARIOS.items():
        scenarios_summary.append({
            "id": s["id"],
            "title": s["title"],
            "subtitle": s["subtitle"],
            "badge": s["badge"],
            "badge_color": s["badge_color"],
            "icon": s["icon"],
            "category": s["category"],
            "patient_name": s["patient_name"],
            "proposed_medication": s["proposed_medication"],
            "dosage": s["dosage"],
            "hazard_summary": s["hazard_summary"]
        })
    return {"scenarios": scenarios_summary}


@demo_router.get("/scenarios/{scenario_id}")
def get_demo_scenario(scenario_id: str):
    """
    Returns full details, clinical note, and presenter talking points for a scenario.
    """
    scenario = CLINICAL_SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    return scenario


@demo_router.post("/run/{scenario_id}")
def execute_demo_scenario(scenario_id: str, request: Request):
    """
    Executes a 1-click simulation of the selected scenario through the full
    orchestration pipeline, returning both the clinical review and the presenter cheatsheet.
    """
    scenario = CLINICAL_SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    # Run review via ClinicalOrchestrator
    review_result = ClinicalOrchestrator.process_review(
        proposed_med=scenario["proposed_medication"],
        patient_id=scenario.get("patient_id"),
        raw_notes=scenario["clinical_note"],
        demographics=scenario.get("demographics")
    )

    return {
        "scenario": scenario,
        "review": review_result,
        "presenter_cheatsheet": {
            "title": scenario["title"],
            "subtitle": scenario["subtitle"],
            "talking_points": scenario["talking_points"],
            "recommended_alternative": scenario["safe_alternative"]
        }
    }
