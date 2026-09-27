"""
MediVault Local - Clinical Pharmacokinetic (PK) Curve Engine (Person C)
Deterministic One-Compartment Open Model with Glomerular Filtration Scaling.
Simulates multi-dose plasma drug concentration time curves over 72 hours,
highlighting pathological drug accumulation, delayed half-life clearance,
and toxic threshold exceedances in renal impairment (eGFR derangements).
Zero cloud egress — 100% sovereign mathematical execution.
"""

import math
from typing import Dict, List, Any, Optional, Tuple

# ---------------------------------------------------------------------------
# Renal-Targeted Pharmacokinetic Drug Constants
# Based on established clinical clinical pharmacology parameters:
# Vd_L_kg: Volume of distribution (L/kg)
# half_life_normal_h: Elimination half-life in normal renal function (hours)
# fe_renal: Fraction excreted unchanged by kidneys (0.0 to 1.0)
# ka_h: Absorption rate constant (1/h)
# standard_dose_mg: Standard single dose
# standard_interval_h: Standard dosing interval (tau)
# c_toxic_mg_L: Toxic plasma concentration threshold
# c_mec_mg_L: Minimum effective concentration threshold
# ---------------------------------------------------------------------------
PK_DRUG_DATABASE: Dict[str, Dict[str, Any]] = {
    "ketorolac": {
        "display_name": "Ketorolac (Toradol)",
        "drug_class": "NSAID",
        "vd_l_kg": 0.22,
        "half_life_normal_h": 5.3,
        "fe_renal": 0.91,
        "ka_h": 1.6,
        "standard_dose_mg": 10.0,
        "standard_interval_h": 6,
        "c_toxic_mg_l": 4.5,
        "c_mec_mg_l": 0.8,
        "toxicity_hazard": "Acute Tubular Necrosis & Glomerular Ischemia"
    },
    "ibuprofen": {
        "display_name": "Ibuprofen (Advil/Motrin)",
        "drug_class": "NSAID",
        "vd_l_kg": 0.15,
        "half_life_normal_h": 2.1,
        "fe_renal": 0.70,
        "ka_h": 1.8,
        "standard_dose_mg": 400.0,
        "standard_interval_h": 8,
        "c_toxic_mg_l": 45.0,
        "c_mec_mg_l": 10.0,
        "toxicity_hazard": "Afferent Arteriolar Spasm & Interstitial Nephritis"
    },
    "naproxen": {
        "display_name": "Naproxen (Aleve)",
        "drug_class": "NSAID",
        "vd_l_kg": 0.16,
        "half_life_normal_h": 14.0,
        "fe_renal": 0.85,
        "ka_h": 1.2,
        "standard_dose_mg": 250.0,
        "standard_interval_h": 12,
        "c_toxic_mg_l": 60.0,
        "c_mec_mg_l": 15.0,
        "toxicity_hazard": "Severe Cumulative NSAID Nephropathy"
    },
    "metformin": {
        "display_name": "Metformin (Glucophage)",
        "drug_class": "Biguanide",
        "vd_l_kg": 3.5,
        "half_life_normal_h": 6.2,
        "fe_renal": 0.95,
        "ka_h": 0.7,
        "standard_dose_mg": 500.0,
        "standard_interval_h": 12,
        "c_toxic_mg_l": 5.0,
        "c_mec_mg_l": 1.0,
        "toxicity_hazard": "Metformin-Associated Lactic Acidosis (MALA)"
    },
    "lisinopril": {
        "display_name": "Lisinopril (Zestril/Prinivil)",
        "drug_class": "ACE Inhibitor",
        "vd_l_kg": 1.8,
        "half_life_normal_h": 12.0,
        "fe_renal": 1.00,
        "ka_h": 0.5,
        "standard_dose_mg": 20.0,
        "standard_interval_h": 24,
        "c_toxic_mg_l": 0.14,
        "c_mec_mg_l": 0.02,
        "toxicity_hazard": "Efferent Arteriolar Collapse & Refractory Hyperkalemia"
    },
    "enalapril": {
        "display_name": "Enalapril (Vasotec)",
        "drug_class": "ACE Inhibitor",
        "vd_l_kg": 1.7,
        "half_life_normal_h": 11.0,
        "fe_renal": 0.90,
        "ka_h": 0.8,
        "standard_dose_mg": 10.0,
        "standard_interval_h": 12,
        "c_toxic_mg_l": 0.12,
        "c_mec_mg_l": 0.02,
        "toxicity_hazard": "Severe Intraglomerular Pressure Drop"
    },
    "furosemide": {
        "display_name": "Furosemide (Lasix)",
        "drug_class": "Loop Diuretic",
        "vd_l_kg": 0.18,
        "half_life_normal_h": 1.5,
        "fe_renal": 0.65,
        "ka_h": 1.3,
        "standard_dose_mg": 40.0,
        "standard_interval_h": 12,
        "c_toxic_mg_l": 12.0,
        "c_mec_mg_l": 1.5,
        "toxicity_hazard": "Ototoxicity & Profound Pre-Renal Azotemia"
    },
    "spironolactone": {
        "display_name": "Spironolactone (Aldactone)",
        "drug_class": "Potassium-Sparing Diuretic",
        "vd_l_kg": 1.2,
        "half_life_normal_h": 13.8,
        "fe_renal": 0.50,
        "ka_h": 0.9,
        "standard_dose_mg": 25.0,
        "standard_interval_h": 24,
        "c_toxic_mg_l": 0.8,
        "c_mec_mg_l": 0.1,
        "toxicity_hazard": "Fatal Cardiac Hyperkalemic Arrest"
    }
}

# Synonyms & Brand Mapping
DRUG_SYNONYMS: Dict[str, str] = {
    "toradol": "ketorolac",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "glucophage": "metformin",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "vasotec": "enalapril",
    "lasix": "furosemide",
    "aldactone": "spironolactone"
}


def resolve_pk_drug(drug_name: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Resolves arbitrary medication string to canonical PK parameter definition."""
    if not drug_name:
        return None, None
    clean = drug_name.strip().lower()

    # Exact match
    if clean in PK_DRUG_DATABASE:
        return clean, PK_DRUG_DATABASE[clean]

    # Synonym match
    if clean in DRUG_SYNONYMS:
        canonical = DRUG_SYNONYMS[clean]
        return canonical, PK_DRUG_DATABASE[canonical]

    # Substring search
    for key, data in PK_DRUG_DATABASE.items():
        if key in clean or clean in key:
            return key, data
    for syn, key in DRUG_SYNONYMS.items():
        if syn in clean:
            return key, PK_DRUG_DATABASE[key]

    return None, None


def calculate_patient_ke(drug_name: str, egfr: float = 90.0) -> Tuple[float, float]:
    """
    Computes patient elimination rate constant (ke) and half-life (t1/2) using Rowland & Tozer scaling.
    Returns: (ke_patient, half_life_patient_h)
    """
    _, drug_params = resolve_pk_drug(drug_name)
    if not drug_params:
        drug_params = PK_DRUG_DATABASE["ketorolac"]
    fe = drug_params["fe_renal"]
    t_half_normal = drug_params["half_life_normal_h"]
    k_normal = math.log(2) / t_half_normal
    cl_ratio = max(0.08, min(1.4, egfr / 90.0))
    k_patient_scale = (1.0 - fe) + (fe * cl_ratio)
    k_patient = max(0.005, k_normal * k_patient_scale)
    t_half_patient = math.log(2) / k_patient
    return k_patient, round(t_half_patient, 2)


def simulate_pk_curve(
    drug_name: str,
    egfr: float = 90.0,
    weight_kg: float = 70.0,
    dose_mg: Optional[float] = None,
    interval_hours: Optional[int] = None,
    total_hours: int = 72
) -> Dict[str, Any]:
    """
    Simulates multi-dose One-Compartment open pharmacokinetic plasma concentrations.

    Args:
        drug_name: Medication name.
        egfr: Patient glomerular filtration rate (mL/min/1.73m2). Normal >= 90.
        weight_kg: Patient body weight in kilograms (default: 70kg).
        dose_mg: Prescribed single dose in mg. Defaults to standard dose if None.
        interval_hours: Dosing interval (tau) in hours. Defaults to standard interval if None.
        total_hours: Total duration of simulation in hours (default: 72 hours).

    Returns:
        Structured dictionary containing curve coordinates, half-life changes,
        toxic ceiling, peak/trough levels, and clinical titration insights.
    """
    canonical_key, drug_params = resolve_pk_drug(drug_name)

    if not drug_params:
        return {
            "error": f"Pharmacokinetic clearance model not configured for medication '{drug_name}'.",
            "available_drugs": list(PK_DRUG_DATABASE.keys())
        }

    # Parameter extraction
    dose = float(dose_mg) if dose_mg is not None and dose_mg > 0 else drug_params["standard_dose_mg"]
    tau = int(interval_hours) if interval_hours is not None and interval_hours > 0 else drug_params["standard_interval_h"]
    weight = max(30.0, min(200.0, float(weight_kg or 70.0)))
    vd = drug_params["vd_l_kg"] * weight  # Total Volume of Distribution in Liters
    ka = drug_params["ka_h"]
    fe = drug_params["fe_renal"]
    t_half_normal = drug_params["half_life_normal_h"]
    c_toxic = drug_params["c_toxic_mg_l"]
    c_mec = drug_params["c_mec_mg_l"]

    # Calculate elimination rate constants (k_e = ln(2) / t_half)
    k_normal = math.log(2) / t_half_normal

    # Patient renal elimination scaling:
    # Rowland & Tozer renal impairment model: k_patient = k_normal * [(1 - fe) + fe * (eGFR / 90)]
    cl_ratio = max(0.08, min(1.4, egfr / 90.0))
    k_patient_scale = (1.0 - fe) + (fe * cl_ratio)
    k_patient = max(0.005, k_normal * k_patient_scale)
    t_half_patient = math.log(2) / k_patient

    time_points: List[float] = []
    normal_curve: List[float] = []
    patient_curve: List[float] = []

    # Number of simulation steps (1 hour resolution up to total_hours)
    step_size = 1.0
    current_t = 0.0

    while current_t <= total_hours:
        time_points.append(round(current_t, 1))

        # Calculate concentration at time current_t under repeated dosing
        # C(t) = Sum_{n=0..N-1} [Dose * ka / (Vd * (ka - k))] * [exp(-k*(t - n*tau)) - exp(-ka*(t - n*tau))]
        num_doses = int(current_t // tau) + 1
        
        c_norm = 0.0
        c_pat = 0.0

        for n in range(num_doses):
            t_since_dose = current_t - (n * tau)
            if t_since_dose >= 0:
                # Normal concentration contribution
                if abs(ka - k_normal) > 0.0001:
                    factor_norm = (dose * ka) / (vd * (ka - k_normal))
                    c_norm += factor_norm * (math.exp(-k_normal * t_since_dose) - math.exp(-ka * t_since_dose))

                # Patient concentration contribution
                if abs(ka - k_patient) > 0.0001:
                    factor_pat = (dose * ka) / (vd * (ka - k_patient))
                    c_pat += factor_pat * (math.exp(-k_patient * t_since_dose) - math.exp(-ka * t_since_dose))

        normal_curve.append(round(max(0.0, c_norm), 3))
        patient_curve.append(round(max(0.0, c_pat), 3))
        current_t += step_size

    # Telemetry metrics
    peak_patient = max(patient_curve)
    peak_normal = max(normal_curve)
    # Trough at 72 hours (prior to next hypothetical dose)
    trough_patient = patient_curve[-1]
    trough_normal = normal_curve[-1]

    toxic_exceeded = any(cp >= c_toxic for cp in patient_curve)
    half_life_multiplier = round(t_half_patient / t_half_normal, 2)
    accumulation_ratio = round(peak_patient / max(0.001, peak_normal), 2)

    # Clinical narrative & recommended titration
    if toxic_exceeded:
        severity_label = "CRITICAL ACCUMULATION"
        status_color = "#ef4444"
        titration_advice = (
            f"Toxicity limit ({c_toxic} mg/L) breached due to {half_life_multiplier}x prolonged half-life. "
            f"Recommended Titration: Reduce dose by 50% ({dose * 0.5:.0f}mg) and extend interval to q{tau * 2}h."
        )
    elif egfr < 45.0:
        severity_label = "SUBSTANTIAL DELAYED CLEARANCE"
        status_color = "#f97316"
        titration_advice = (
            f"Elimination delayed ({t_half_patient:.1f}h vs {t_half_normal:.1f}h normal). "
            f"Monitor peak levels closely or extend dosing interval."
        )
    elif egfr < 60.0:
        severity_label = "MILD RETENTION"
        status_color = "#f59e0b"
        titration_advice = "Mild accumulation detected. Routine therapeutic monitoring advised."
    else:
        severity_label = "NORMAL CLEARANCE"
        status_color = "#10b981"
        titration_advice = "Standard elimination kinetics. Therapeutic window maintained."

    return {
        "drug_key": canonical_key,
        "display_name": drug_params["display_name"],
        "drug_class": drug_params["drug_class"],
        "toxicity_hazard": drug_params["toxicity_hazard"],
        "egfr": egfr,
        "weight_kg": weight,
        "dose_mg": dose,
        "interval_hours": tau,
        "c_toxic_mg_l": c_toxic,
        "c_mec_mg_l": c_mec,
        "half_life_normal_h": round(t_half_normal, 1),
        "half_life_patient_h": round(t_half_patient, 1),
        "half_life_multiplier": half_life_multiplier,
        "peak_patient_mg_l": peak_patient,
        "peak_normal_mg_l": peak_normal,
        "trough_patient_mg_l": trough_patient,
        "trough_normal_mg_l": trough_normal,
        "accumulation_ratio": accumulation_ratio,
        "toxic_exceeded": toxic_exceeded,
        "severity_label": severity_label,
        "status_color": status_color,
        "titration_advice": titration_advice,
        "time_points": time_points,
        "normal_curve": normal_curve,
        "patient_curve": patient_curve
    }
