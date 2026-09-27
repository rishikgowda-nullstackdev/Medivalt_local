"""
MediVault Local - Clinical Hazard Index & Patient Vulnerability Evaluator (Person C)
Deterministic, 100% sovereign multi-dimensional clinical safety scoring engine.
Computes an aggregate 0-100 hazard index evaluating:
  1. Quantitative organ derangements (eGFR, Creatinine, K+, INR, Platelets, BP)
  2. Drug-drug & drug-disease contraindication severity (CRITICAL vs WARNING)
  3. Polypharmacy burden & metabolic cascade risk
  4. Immunologic allergy cross-match risks
  5. Age-related pharmacokinetic vulnerability
"""

import math
from typing import Dict, List, Any, Optional, Tuple


def calculate_hazard_index(
    biomarkers: Optional[Dict[str, Any]] = None,
    alerts: Optional[List[Dict[str, Any]]] = None,
    active_medications: Optional[List[str]] = None,
    conditions: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    demographics: Optional[Dict[str, Any]] = None,
    overall_status: Optional[str] = "SAFE"
) -> Dict[str, Any]:
    """
    Computes a sovereign 0-100 Clinical Hazard Index.

    Args:
        biomarkers: Quantitative lab biomarkers (eGFR, Creatinine, Potassium, etc.).
        alerts: List of contraindication alerts triggered for the proposed therapy.
        active_medications: Current patient medication list.
        conditions: Diagnosed clinical conditions.
        allergies: Known patient allergies.
        demographics: Demographics dict with age, gender, weight.
        overall_status: Overall review status ("SAFE", "WARNING", "CRITICAL").

    Returns:
        Structured score dictionary with risk tier, needle angle, category breakdown,
        and primary clinical hazard drivers.
    """
    biomarkers = biomarkers or {}
    alerts = alerts or []
    active_meds = active_medications or []
    conditions = conditions or []
    allergies = allergies or []
    demographics = demographics or {}

    organ_stress_pts = 0
    organ_details: List[str] = []

    interaction_pts = 0
    interaction_details: List[str] = []

    polypharmacy_pts = 0
    polypharmacy_details: List[str] = []

    allergy_pts = 0
    allergy_details: List[str] = []

    vulnerability_pts = 0
    vulnerability_details: List[str] = []

    # -------------------------------------------------------------------------
    # 1. Organ Stress & Quantitative Biomarkers (Max 40 pts)
    # -------------------------------------------------------------------------
    # eGFR
    egfr_data = biomarkers.get("eGFR") or biomarkers.get("egfr")
    if egfr_data:
        val = egfr_data.get("value") if isinstance(egfr_data, dict) else float(egfr_data)
        if val is not None:
            if val < 30.0:
                organ_stress_pts += 35
                organ_details.append(f"Severe renal insufficiency (eGFR {val:.0f} mL/min/1.73m²)")
            elif val < 45.0:
                organ_stress_pts += 22
                organ_details.append(f"Stage 3b moderate-severe CKD (eGFR {val:.0f} mL/min/1.73m²)")
            elif val < 60.0:
                organ_stress_pts += 10
                organ_details.append(f"Stage 3a mild-moderate CKD (eGFR {val:.0f} mL/min/1.73m²)")

    # Serum Creatinine
    creat_data = biomarkers.get("Creatinine") or biomarkers.get("creatinine")
    if creat_data:
        val = creat_data.get("value") if isinstance(creat_data, dict) else float(creat_data)
        if val is not None:
            if val >= 2.0:
                organ_stress_pts += 18
                organ_details.append(f"Marked azotemia (Creatinine {val:.2f} mg/dL)")
            elif val > 1.4:
                organ_stress_pts += 10
                organ_details.append(f"Elevated serum creatinine ({val:.2f} mg/dL)")

    # Potassium
    k_data = biomarkers.get("Potassium") or biomarkers.get("potassium")
    if k_data:
        val = k_data.get("value") if isinstance(k_data, dict) else float(k_data)
        if val is not None:
            if val > 5.2:
                organ_stress_pts += 25
                organ_details.append(f"Acute hyperkalemia risk (K+ {val:.1f} mEq/L)")
            elif val > 5.0:
                organ_stress_pts += 15
                organ_details.append(f"Borderline hyperkalemia (K+ {val:.1f} mEq/L)")
            elif val < 3.5:
                organ_stress_pts += 15
                organ_details.append(f"Hypokalemia dysrhythmia risk (K+ {val:.1f} mEq/L)")

    # Coagulation (INR)
    inr_data = biomarkers.get("INR") or biomarkers.get("inr")
    if inr_data:
        val = inr_data.get("value") if isinstance(inr_data, dict) else float(inr_data)
        if val is not None:
            if val > 3.5:
                organ_stress_pts += 28
                organ_details.append(f"Supratherapeutic coagulopathy (INR {val:.2f})")
            elif val > 3.0:
                organ_stress_pts += 14
                organ_details.append(f"Elevated bleeding tendency (INR {val:.2f})")

    # Platelets
    plt_data = biomarkers.get("Platelets") or biomarkers.get("platelets")
    if plt_data:
        val = plt_data.get("value") if isinstance(plt_data, dict) else float(plt_data)
        if val is not None:
            if val < 50.0:
                organ_stress_pts += 28
                organ_details.append(f"Severe thrombocytopenia ({val:.0f}k/µL)")
            elif val < 100.0:
                organ_stress_pts += 14
                organ_details.append(f"Moderate thrombocytopenia ({val:.0f}k/µL)")

    # Blood Pressure
    bp_data = biomarkers.get("BloodPressure") or biomarkers.get("blood_pressure")
    if bp_data and isinstance(bp_data, dict):
        sys_bp = bp_data.get("systolic") or bp_data.get("value")
        dia_bp = bp_data.get("diastolic")
        if sys_bp and (sys_bp >= 180 or (dia_bp and dia_bp >= 120)):
            organ_stress_pts += 25
            organ_details.append(f"Hypertensive crisis range ({sys_bp}/{dia_bp} mmHg)")
        elif sys_bp and sys_bp >= 140:
            organ_stress_pts += 10
            organ_details.append(f"Stage 2 hypertension ({sys_bp}/{dia_bp or '-'} mmHg)")

    # Known chronic organ diagnoses
    conds_lower = [c.lower() for c in conditions]
    if any("kidney" in c or "renal" in c or "ckd" in c for c in conds_lower) and not egfr_data:
        organ_stress_pts += 15
        organ_details.append("Documented Chronic Kidney Disease diagnosis")
    if any("heart failure" in c or "chf" in c for c in conds_lower):
        organ_stress_pts += 12
        organ_details.append("Underlying Congestive Heart Failure")

    # Cap organ stress
    organ_stress_score = min(40, organ_stress_pts)

    # -------------------------------------------------------------------------
    # 2. Acute Drug Interactions & Contraindications (Max 35 pts)
    # -------------------------------------------------------------------------
    crit_alerts = [a for a in alerts if a.get("severity") == "CRITICAL"]
    warn_alerts = [a for a in alerts if a.get("severity") == "WARNING"]
    poly_alerts = [a for a in alerts if a.get("interaction_type") == "POLYPHARMACY"]

    if crit_alerts:
        interaction_pts += 30 + (min(len(crit_alerts) - 1, 2) * 5)
        for a in crit_alerts[:2]:
            desc = a.get("contraindicated_factor") or a.get("clinical_mechanism") or "Critical Contraindication"
            interaction_details.append(f"CRITICAL: {desc}")
    elif warn_alerts:
        interaction_pts += 15 + (min(len(warn_alerts) - 1, 2) * 5)
        for a in warn_alerts[:2]:
            desc = a.get("contraindicated_factor") or a.get("clinical_mechanism") or "Precautionary Warning"
            interaction_details.append(f"WARNING: {desc}")

    if poly_alerts and not any("Cascade" in d for d in interaction_details):
        interaction_pts += 10
        interaction_details.append("Hemodynamic cascade / multi-drug interaction mechanism")

    interaction_score = min(35, interaction_pts)

    # -------------------------------------------------------------------------
    # 3. Polypharmacy Burden & Regimen Complexity (Max 15 pts)
    # -------------------------------------------------------------------------
    med_count = len(active_meds)
    if med_count >= 9:
        polypharmacy_pts = 15
        polypharmacy_details.append(f"High polypharmacy load ({med_count} concurrent medications)")
    elif med_count >= 6:
        polypharmacy_pts = 10
        polypharmacy_details.append(f"Substantial polypharmacy ({med_count} concurrent medications)")
    elif med_count >= 4:
        polypharmacy_pts = 5
        polypharmacy_details.append(f"Moderate polypharmacy ({med_count} concurrent medications)")
    else:
        polypharmacy_pts = 0
        polypharmacy_details.append("Manageable baseline regimen (<4 drugs)")

    polypharmacy_score = min(15, polypharmacy_pts)

    # -------------------------------------------------------------------------
    # 4. Allergy Cross-Match Burden (Max 10 pts)
    # -------------------------------------------------------------------------
    allergy_matches = [a for a in alerts if "ALLERGY" in str(a.get("interaction_type", "")).upper()]
    if allergy_matches:
        allergy_pts = 10
        for am in allergy_matches:
            allergy_details.append(f"Active allergy cross-reactivity: {am.get('contraindicated_factor', 'Known Allergen')}")
    elif allergies and any(a.lower() != "no known drug allergies (nkda)" for a in allergies):
        allergy_pts = 3
        allergy_details.append(f"Documented atopic profile ({len(allergies)} allergy records)")
    else:
        allergy_pts = 0
        allergy_details.append("No active allergy conflicts detected")

    allergy_score = min(10, allergy_pts)

    # -------------------------------------------------------------------------
    # 5. Age & Vulnerability Factor (Max 10 pts)
    # -------------------------------------------------------------------------
    age = demographics.get("age")
    if age is not None:
        if age >= 85:
            vulnerability_pts += 8
            vulnerability_details.append(f"Advanced geriatric vulnerability (Age {age})")
        elif age >= 70:
            vulnerability_pts += 5
            vulnerability_details.append(f"Geriatric pharmacokinetic sensitivity (Age {age})")

    # Check for Beers criteria alert
    if any(a.get("interaction_type") == "BEERS_CRITERIA" for a in alerts):
        vulnerability_pts += 5
        vulnerability_details.append("AGS Beers Criteria high-risk medication in older adults")

    vulnerability_score = min(10, vulnerability_pts)

    # -------------------------------------------------------------------------
    # Final Aggregate Score Calculation
    # -------------------------------------------------------------------------
    total_raw = (
        organ_stress_score +
        interaction_score +
        polypharmacy_score +
        allergy_score +
        vulnerability_score
    )

    # Override floor for CRITICAL status
    if overall_status == "CRITICAL" and total_raw < 70:
        total_raw = 72

    final_score = max(0, min(100, int(round(total_raw))))

    # Determine risk tier & color
    if final_score >= 80:
        risk_tier = "CRITICAL"
        color = "#ef4444"         # Red-500
        badge_bg = "bg-rose-950/80"
        badge_border = "border-rose-500/50"
        badge_text = "text-rose-200"
    elif final_score >= 60:
        risk_tier = "HIGH"
        color = "#f97316"         # Orange-500
        badge_bg = "bg-orange-950/80"
        badge_border = "border-orange-500/50"
        badge_text = "text-orange-200"
    elif final_score >= 30:
        risk_tier = "MODERATE"
        color = "#f59e0b"         # Amber-500
        badge_bg = "bg-amber-950/80"
        badge_border = "border-amber-500/50"
        badge_text = "text-amber-200"
    else:
        risk_tier = "LOW"
        color = "#10b981"         # Emerald-500
        badge_bg = "bg-emerald-950/80"
        badge_border = "border-emerald-500/50"
        badge_text = "text-emerald-200"

    # Needle angle on 180-degree semi-circle gauge (0 deg = left, 90 deg = top, 180 deg = right)
    needle_degrees = round((final_score / 100.0) * 180.0, 1)

    # Determine primary driver
    all_drivers = (
        organ_details +
        interaction_details +
        polypharmacy_details +
        allergy_details +
        vulnerability_details
    )
    primary_driver = all_drivers[0] if all_drivers else "Normal baseline clearance with low pharmacological risk."

    # Synthesis of clinical recommendation
    if risk_tier == "CRITICAL":
        clinical_recommendation = (
            "CONTRAINDICATED: Immediate physician intervention required. "
            "Withhold proposed therapy and review renal/hemostatic clearance parameters."
        )
    elif risk_tier == "HIGH":
        clinical_recommendation = (
            "SIGNIFICANT CAUTION: Substantial organ impairment or polypharmacy risk detected. "
            "Consider renal dose titration, biomarker re-check, or safe alternative."
        )
    elif risk_tier == "MODERATE":
        clinical_recommendation = (
            "PRECAUTIONARY MONITORING: Low-to-moderate pharmacological friction. "
            "Proceed with routine therapeutic monitoring."
        )
    else:
        clinical_recommendation = (
            "THERAPY CLEARED: Clean safety profile. No acute organ contraindications or severe DDI detected."
        )

    return {
        "score": final_score,
        "risk_tier": risk_tier,
        "needle_degrees": needle_degrees,
        "color": color,
        "badge_classes": {
            "bg": badge_bg,
            "border": badge_border,
            "text": badge_text
        },
        "category_breakdown": {
            "organ_stress": {
                "score": organ_stress_score,
                "max": 40,
                "details": organ_details or ["Organ biomarkers within safe tolerance limits"]
            },
            "drug_interactions": {
                "score": interaction_score,
                "max": 35,
                "details": interaction_details or ["No acute contraindications triggered"]
            },
            "polypharmacy": {
                "score": polypharmacy_score,
                "max": 15,
                "details": polypharmacy_details or ["Concurrent medication burden is manageable"]
            },
            "allergy_risks": {
                "score": allergy_score,
                "max": 10,
                "details": allergy_details or ["No known allergen conflicts"]
            },
            "age_vulnerability": {
                "score": vulnerability_score,
                "max": 10,
                "details": vulnerability_details or ["Standard adult pharmacokinetic profile"]
            }
        },
        "primary_driver": primary_driver,
        "clinical_recommendation": clinical_recommendation
    }
