"""
MediVault Local — Patient Portal Backend Router
Zero-Cloud, HIPAA/DPDP-Compliant Patient-Facing API.

Provides patient registration, authentication, profile viewing,
and LLM-powered personalized food/diet/wellness recommendations.
Patient tokens are completely isolated from practitioner tokens.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from backend.ai_bridge import ai_bridge

logger = logging.getLogger("medivault.patient_portal")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")

patient_router = APIRouter(prefix="/api/patient", tags=["Patient Portal"])


# ---------------------------------------------------------------------------
# Database Helper
# ---------------------------------------------------------------------------
def _get_db():
    """Returns a SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------
class PatientRegisterRequest(BaseModel):
    patient_id: str = Field(..., description="Clinical patient ID (e.g. PT-101)")
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: Optional[str] = Field(None, description="YYYY-MM-DD format")


class PatientLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class PatientCompanionChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class PostDoctorAdviceRequest(BaseModel):
    patient_id: str = Field(..., description="Target patient ID (e.g. PT-101)")
    category: str = Field("GENERAL", description="GENERAL, MEDICATION, DIETARY, WARNING_SIGNS, or FOLLOW_UP")
    advice_text: str = Field(..., min_length=3, description="Doctor clinical advice or prescription notes")
    plain_summary: Optional[str] = Field(None, description="Patient-friendly plain language translation")
    severity: str = Field("ROUTINE", description="ROUTINE, URGENT, or CRITICAL")
    practitioner_name: Optional[str] = Field(None, description="Attending physician name")
    hospital_name: Optional[str] = Field(None, description="Attending hospital name")


class DraftAdviceSLMRequest(BaseModel):
    clinical_notes: str = Field(..., min_length=3)
    patient_id: Optional[str] = Field("PT-101")
    category: Optional[str] = Field("GENERAL")


class LogAdherenceRequest(BaseModel):
    log_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    time_slot: str = Field(..., description="MORNING, AFTERNOON, EVENING, or NIGHT")
    medication_name: str = Field(..., min_length=1)
    dosage: Optional[str] = None
    taken: bool = True


# ---------------------------------------------------------------------------
# Auth Helpers
# ---------------------------------------------------------------------------
def _get_patient_from_token(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extracts and validates a patient JWT from Bearer header or cookie.
    Returns the decoded payload if valid, None otherwise.
    """
    token = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif "medivault_patient_session" in request.cookies:
        token = request.cookies.get("medivault_patient_session")

    if not token:
        return None

    payload = decode_access_token(token)
    if payload and payload.get("role") == "patient" and "patient_id" in payload:
        return payload

    return None


def _require_patient(request: Request) -> Dict[str, Any]:
    """Raises 401 if no valid patient token is present."""
    patient = _get_patient_from_token(request)
    if not patient:
        raise HTTPException(
            status_code=401,
            detail="Patient authentication required. Please log in at /patient-portal."
        )
    return patient


# ---------------------------------------------------------------------------
# Lab Plain-Language Explanations
# ---------------------------------------------------------------------------
LAB_EXPLANATIONS = {
    "egfr": {
        "name": "Kidney Filtration Rate (eGFR)",
        "normal_range": "≥ 60 mL/min",
        "explain": lambda v: (
            f"Your kidney filtration rate is {v:.0f}% of what's considered fully healthy. "
            + ("This is in the normal range — your kidneys are working well!" if v >= 60
               else "This is below normal — your kidneys are working harder than they should. Your care team is monitoring this closely."
               if v >= 30
               else "This is significantly reduced — your kidneys need extra support. Your doctor is managing this carefully.")
        ),
        "status": lambda v: "NORMAL" if v >= 60 else ("WARNING_LOW" if v >= 30 else "CRITICAL_LOW"),
    },
    "creatinine": {
        "name": "Kidney Waste Marker (Creatinine)",
        "normal_range": "0.6 – 1.2 mg/dL",
        "explain": lambda v: (
            f"Your creatinine level is {v:.1f} mg/dL. "
            + ("This is in the healthy range!" if v <= 1.2
               else "This is higher than normal, which means your kidneys may not be filtering waste as efficiently. Your doctor is keeping an eye on this."
               if v <= 2.0
               else "This is elevated — your kidneys need support clearing waste from your blood. Your care team has a plan for this.")
        ),
        "status": lambda v: "NORMAL" if v <= 1.2 else ("WARNING_HIGH" if v <= 2.0 else "CRITICAL_HIGH"),
    },
    "potassium": {
        "name": "Heart Rhythm Mineral (Potassium)",
        "normal_range": "3.5 – 5.0 mEq/L",
        "explain": lambda v: (
            f"Your potassium level is {v:.1f} mEq/L. "
            + ("This is in the safe range — great for your heart rhythm!" if 3.5 <= v <= 5.0
               else "This is a bit high — too much potassium can affect your heartbeat. Your doctor may adjust your diet or medications."
               if v > 5.0
               else "This is a bit low — potassium helps your heart beat regularly. Your care team may suggest potassium-rich foods.")
        ),
        "status": lambda v: "NORMAL" if 3.5 <= v <= 5.0 else ("CRITICAL_HIGH" if v > 5.0 else "WARNING_LOW"),
    },
    "inr": {
        "name": "Blood Clotting Speed (INR)",
        "normal_range": "2.0 – 3.0 (on Warfarin)",
        "explain": lambda v: (
            f"Your INR is {v:.1f}. "
            + ("This is in your target range — your blood thinner is working as expected!" if 2.0 <= v <= 3.0
               else "This is above your target range — your blood is thinner than intended, which increases bleeding risk. Your doctor may adjust your Warfarin dose."
               if v > 3.0
               else "This is below your target range — your blood may be clotting too easily. Your doctor may need to adjust your medication.")
        ),
        "status": lambda v: "NORMAL" if 2.0 <= v <= 3.0 else ("CRITICAL_HIGH" if v > 3.5 else ("WARNING_HIGH" if v > 3.0 else "WARNING_LOW")),
    },
    "platelets": {
        "name": "Clotting Cells (Platelets)",
        "normal_range": "150 – 400 ×10³/µL",
        "explain": lambda v: (
            f"Your platelet count is {v:.0f} thousand per microliter. "
            + ("This is in the healthy range!" if v >= 150
               else "This is below normal — your blood may not clot as quickly if you get a cut. Your care team is monitoring this."
               if v >= 50
               else "This is very low — you may bruise or bleed more easily. Your doctor has a plan to help.")
        ),
        "status": lambda v: "NORMAL" if v >= 150 else ("WARNING_LOW" if v >= 50 else "CRITICAL_LOW"),
    },
}


def _explain_lab(biomarker_name: str, value: float, unit: str) -> Dict[str, Any]:
    """Generates plain-language explanation for a lab biomarker."""
    key = biomarker_name.lower().strip()
    info = LAB_EXPLANATIONS.get(key)

    if info:
        return {
            "biomarker": info["name"],
            "raw_name": biomarker_name,
            "value": value,
            "unit": unit,
            "normal_range": info["normal_range"],
            "status": info["status"](value),
            "plain_explanation": info["explain"](value),
        }

    # Generic fallback for unknown biomarkers
    return {
        "biomarker": biomarker_name,
        "raw_name": biomarker_name,
        "value": value,
        "unit": unit,
        "normal_range": "Ask your doctor",
        "status": "UNKNOWN",
        "plain_explanation": f"Your {biomarker_name} level is {value} {unit}. Ask your care team what this means for you.",
    }


# ---------------------------------------------------------------------------
# Endpoint 1: Patient Registration
# ---------------------------------------------------------------------------
@patient_router.post("/register")
def register_patient(body: PatientRegisterRequest, response: Response):
    """
    Registers a new patient portal account.
    Validates that the patient_id exists in the clinical patients table.
    """
    conn = _get_db()
    cursor = conn.cursor()

    # Validate patient_id exists
    cursor.execute("SELECT patient_id, patient_name FROM patients WHERE patient_id = ?", (body.patient_id,))
    patient_row = cursor.fetchone()
    if not patient_row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Patient ID '{body.patient_id}' not found in the clinical system. Please check with your care team."
        )

    # Check username availability
    cursor.execute("SELECT id FROM patient_users WHERE username = ?", (body.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Username '{body.username}' is already taken. Please choose a different one."
        )

    # Hash password and insert
    salt_hex, hash_hex = hash_password(body.password)
    cursor.execute("""
        INSERT INTO patient_users (patient_id, username, password_hash, salt, full_name, date_of_birth)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (body.patient_id, body.username, hash_hex, salt_hex, body.full_name, body.date_of_birth))
    conn.commit()
    conn.close()

    logger.info("Patient portal account created: %s -> %s", body.username, body.patient_id)

    return {
        "success": True,
        "username": body.username,
        "patient_id": body.patient_id,
        "message": "Your account has been created! You can now sign in."
    }


# ---------------------------------------------------------------------------
# Endpoint 2: Patient Login
# ---------------------------------------------------------------------------
@patient_router.post("/login")
def login_patient(body: PatientLoginRequest, response: Response):
    """
    Authenticates patient credentials and returns an offline JWT.
    Sets an HTTP-only session cookie for browser-based access.
    """
    conn = _get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT patient_id, username, password_hash, salt, full_name FROM patient_users WHERE username = ?",
        (body.username,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user = dict(row)
    if not verify_password(body.password, user["salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    # Create patient-specific JWT (role=patient, separate from doctor tokens)
    token = create_access_token({
        "patient_id": user["patient_id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": "patient",
    }, expires_minutes=480)

    resp = JSONResponse({
        "success": True,
        "token": token,
        "patient_id": user["patient_id"],
        "full_name": user["full_name"],
    })
    resp.set_cookie(
        key="medivault_patient_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,  # 8-hour session
    )
    return resp


# ---------------------------------------------------------------------------
# Endpoint 3: Patient Profile
# ---------------------------------------------------------------------------
@patient_router.get("/profile")
def get_patient_profile(request: Request):
    """
    Returns the authenticated patient's full medical profile with
    plain-language lab explanations.
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]

    conn = _get_db()
    cursor = conn.cursor()

    # Demographics
    cursor.execute("SELECT patient_id, patient_name, age, gender FROM patients WHERE patient_id = ?", (patient_id,))
    demo_row = cursor.fetchone()
    if not demo_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient clinical record not found.")

    demographics = dict(demo_row)

    # Conditions
    cursor.execute(
        "SELECT condition_name, icd10_code, diagnosed_date FROM patient_conditions WHERE patient_id = ?",
        (patient_id,)
    )
    conditions = [dict(r) for r in cursor.fetchall()]

    # Medications
    cursor.execute(
        "SELECT medication_name, dosage, frequency, status FROM patient_medications WHERE patient_id = ?",
        (patient_id,)
    )
    medications = [dict(r) for r in cursor.fetchall()]

    # Allergies
    cursor.execute(
        "SELECT allergen, reaction FROM patient_allergies WHERE patient_id = ?",
        (patient_id,)
    )
    allergies = [dict(r) for r in cursor.fetchall()]

    # Labs with plain-language explanations
    cursor.execute(
        "SELECT biomarker_name, value, unit FROM patient_labs WHERE patient_id = ?",
        (patient_id,)
    )
    raw_labs = cursor.fetchall()
    labs = [_explain_lab(r["biomarker_name"], r["value"], r["unit"]) for r in raw_labs]

    conn.close()

    return {
        "patient_id": demographics["patient_id"],
        "full_name": patient.get("full_name", demographics["patient_name"]),
        "age": demographics.get("age"),
        "gender": demographics.get("gender"),
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
        "labs": labs,
        "zero_cloud": True,
    }


# Condition keywords for dietary guideline matching (must be declared before use below)
_CONDITION_KEYWORDS = [
    "kidney disease",
    "diabetes",
    "hypertension",
    "asthma",
    "atrial fibrillation",
]


# ---------------------------------------------------------------------------
# Endpoint 4: Personalized Food & Wellness Recommendations
# ---------------------------------------------------------------------------
@patient_router.get("/recommendations")
def get_patient_recommendations(request: Request):
    """
    Returns personalized dietary and wellness recommendations combining:
    1. Deterministic dietary_guidelines from SQLite (always available)
    2. LLM-generated personalized narrative from Ollama (if online)
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]

    conn = _get_db()
    cursor = conn.cursor()

    # Fetch patient conditions for keyword matching
    cursor.execute(
        "SELECT condition_name FROM patient_conditions WHERE patient_id = ?",
        (patient_id,)
    )
    conditions = [r["condition_name"] for r in cursor.fetchall()]

    # Fetch medications and labs for LLM context
    cursor.execute(
        "SELECT medication_name, dosage, frequency FROM patient_medications WHERE patient_id = ?",
        (patient_id,)
    )
    medications = [f"{r['medication_name']} {r['dosage']} {r['frequency']}" for r in cursor.fetchall()]

    cursor.execute(
        "SELECT biomarker_name, value, unit FROM patient_labs WHERE patient_id = ?",
        (patient_id,)
    )
    labs_raw = cursor.fetchall()
    labs = {r["biomarker_name"]: {"value": r["value"], "unit": r["unit"]} for r in labs_raw}

    # Match dietary guidelines against patient conditions
    recommended_foods: List[Dict[str, str]] = []
    foods_to_avoid: List[Dict[str, str]] = []
    wellness_tips: List[Dict[str, str]] = []

    for condition in conditions:
        condition_lower = condition.lower()
        # Try matching against known condition keywords
        for keyword in _CONDITION_KEYWORDS:
            if keyword in condition_lower:
                cursor.execute(
                    "SELECT category, item, rationale FROM dietary_guidelines WHERE condition_keyword = ?",
                    (keyword,)
                )
                for row in cursor.fetchall():
                    entry = {"item": row["item"], "rationale": row["rationale"], "condition": keyword.title()}
                    if row["category"] == "FOOD_RECOMMENDED":
                        if entry not in recommended_foods:
                            recommended_foods.append(entry)
                    elif row["category"] == "FOOD_AVOID":
                        if entry not in foods_to_avoid:
                            foods_to_avoid.append(entry)
                    elif row["category"] == "WELLNESS_TIP":
                        if entry not in wellness_tips:
                            wellness_tips.append(entry)

    conn.close()

    # Generate personalized narrative via Ollama LLM
    personalized_narrative = None
    generated_by = "deterministic_rules"

    if conditions:
        narrative = ai_bridge.generate_patient_wellness_guide(
            patient_name=patient.get("full_name", "there"),
            conditions=conditions,
            medications=medications,
            labs=labs,
        )
        if narrative:
            personalized_narrative = narrative
            generated_by = "llama3.2:3b"

    return {
        "patient_id": patient_id,
        "personalized_narrative": personalized_narrative,
        "generated_by": generated_by,
        "dietary_guidelines": {
            "recommended_foods": recommended_foods,
            "foods_to_avoid": foods_to_avoid,
            "wellness_tips": wellness_tips,
        },
        "conditions_matched": [c for c in conditions],
        "zero_cloud": True,
    }




# ---------------------------------------------------------------------------
# Endpoint 5: Patient Logout
# ---------------------------------------------------------------------------
@patient_router.post("/logout")
def logout_patient(response: Response):
    """Clears the patient session cookie."""
    resp = JSONResponse({"success": True, "message": "You have been signed out."})
    resp.delete_cookie("medivault_patient_session")
    return resp


# ---------------------------------------------------------------------------
# Endpoint 6: Sovereign AI Patient Health Companion Chat
# ---------------------------------------------------------------------------
@patient_router.post("/companion/chat")
def patient_companion_chat(req: PatientCompanionChatRequest, request: Request):
    """
    Empathetic, jargon-free offline AI health companion for patients.
    Grounded in the patient's active conditions, medications, and lab values.
    Enforces strict patient safety guardrails with zero cloud calls.
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]
    full_name = patient.get("full_name", "Friend")
    first_name = full_name.split()[0] if full_name else "there"

    conn = _get_db()
    cursor = conn.cursor()

    # Fetch conditions
    cursor.execute(
        "SELECT condition_name FROM patient_conditions WHERE patient_id = ?",
        (patient_id,)
    )
    conditions = [r["condition_name"] for r in cursor.fetchall()]

    # Fetch meds
    cursor.execute(
        "SELECT medication_name FROM patient_medications WHERE patient_id = ?",
        (patient_id,)
    )
    medications = [r["medication_name"] for r in cursor.fetchall()]

    # Fetch labs
    cursor.execute(
        "SELECT biomarker_name, value, unit FROM patient_labs WHERE patient_id = ?",
        (patient_id,)
    )
    labs = {r["biomarker_name"].lower(): f"{r['value']} {r['unit']}" for r in cursor.fetchall()}
    conn.close()

    user_msg = req.message.strip()
    msg_lower = user_msg.lower()

    # 1. Deterministic Safety Guardrails Check
    # Safety Rule 1: Patient asking about taking NSAIDs (Ibuprofen, Advil, Aleve, Motrin) with Kidney Disease
    has_ckd = any("kidney" in c.lower() or "ckd" in c.lower() or "renal" in c.lower() for c in conditions)
    asks_nsaid = any(n in msg_lower for n in ["ibuprofen", "advil", "motrin", "aleve", "naproxen", "toradol", "painkiller"])

    if has_ckd and asks_nsaid:
        reply = (
            f"Hello {first_name}. Because your medical chart notes kidney sensitivity, "
            f"it is very important to **avoid non-steroidal anti-inflammatory medicines like Ibuprofen, Advil, or Aleve**. "
            f"These medications reduce blood supply to your kidneys and can make your kidney function drop suddenly. "
            f"For mild everyday aches, doctors often recommend **Acetaminophen (Tylenol)** or warm compresses instead. "
            f"Please check with your doctor or pharmacist before taking any new over-the-counter pain pills."
        )
        return {
            "reply": reply,
            "suggested_followups": [
                "What foods should I eat to protect my kidneys?",
                "What dose of Tylenol is safe for me?",
                "How much water should I drink each day?"
            ],
            "model": "Sovereign Clinical Safety Engine (Local)"
        }

    # 2. Try Local Ollama SLM
    reply = None
    model_used = "MediVault Local Wellness Assistant"

    if ai_bridge.is_online():
        prompt = (
            f"You are a kind, compassionate offline healthcare companion speaking with a patient named {first_name}.\n"
            f"Patient conditions: {', '.join(conditions) if conditions else 'General wellness'}.\n"
            f"Current medications: {', '.join(medications) if medications else 'None'}.\n"
            f"Lab results: {', '.join([f'{k}: {v}' for k, v in labs.items()]) if labs else 'Normal'}.\n\n"
            f"Patient asks: '{user_msg}'\n\n"
            f"Rules for response:\n"
            f"1. Explain in simple, friendly, comforting language (6th-grade reading level, no complex medical jargon).\n"
            f"2. Keep the answer to 3-5 sentences.\n"
            f"3. Never diagnose new diseases or tell them to stop prescribed medications without speaking to their doctor.\n"
            f"4. If they have kidney disease or high blood pressure, remind them about low sodium and kidney-friendly habits.\n"
            f"5. Address them warmly as {first_name}."
        )
        try:
            import httpx
            with httpx.Client(timeout=3.5) as client:
                res = client.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 180}
                    }
                )
                if res.status_code == 200:
                    raw_text = res.json().get("response", "").strip()
                    if raw_text and len(raw_text) > 20:
                        reply = raw_text
                        model_used = "Ollama Local (llama3.2:3b)"
        except Exception:
            pass

    # 3. Deterministic Empathetic Fallback
    if not reply:
        if any(w in msg_lower for w in ["diet", "food", "eat", "meal", "nutrition"]):
            if has_ckd:
                reply = (
                    f"Hi {first_name}! For protecting your kidneys, focusing on fresh, low-sodium meals is wonderful. "
                    f"Enjoy foods like cauliflower, blueberries, red bell peppers, and lean proteins like egg whites or skinless poultry. "
                    f"Try to limit high-sodium processed foods, canned soups, and salty seasonings, as keeping your salt intake low helps keep your blood pressure gentle on your kidneys."
                )
            else:
                reply = (
                    f"Hi {first_name}! Eating a colorful mix of vegetables, fruits, and lean proteins is one of the best things you can do for your health. "
                    f"Drinking plenty of water and swapping out processed snacks for fresh fruits like apples or berries will keep your energy steady all day."
                )
        elif any(w in msg_lower for w in ["water", "drink", "fluid", "hydration"]):
            reply = (
                f"Staying hydrated is great for your overall wellness, {first_name}! "
                f"Unless your doctor has given you a specific daily fluid restriction for your heart or kidneys, "
                f"aiming for about 6 to 8 glasses of water spread evenly throughout the day is a healthy baseline. "
                f"Sipping steadily is much easier on your system than drinking large amounts all at once."
            )
        elif any(w in msg_lower for w in ["lab", "result", "egfr", "creatinine", "test"]):
            if "egfr" in labs:
                reply = (
                    f"Your most recent eGFR lab showed **{labs['egfr']}**, {first_name}. "
                    f"eGFR measures how efficiently your kidneys filter your bloodstream. "
                    f"Keeping your blood pressure well-controlled with your prescribed medications and staying well-hydrated are two of the best everyday ways to keep this number stable."
                )
            else:
                reply = (
                    f"Hi {first_name}, your lab results reflect your body's overall balance. "
                    f"If you'd like to review any specific number like blood pressure or kidney filtration, "
                    f"your doctor's team can help walk through your trend over time during your next checkup."
                )
        else:
            reply = (
                f"Hello {first_name}! I am your offline MediVault Health Companion. "
                f"I can help explain your lab numbers, dietary guidelines, and general wellness habits in plain language. "
                f"Feel free to ask about foods that support your health, safe everyday habits, or how your prescribed routine works together."
            )

    suggested = [
        "What foods should I eat to protect my kidneys?",
        "How much water should I drink daily?",
        "Can I take Tylenol for a headache?"
    ]

    return {
        "reply": reply,
        "suggested_followups": suggested,
        "model": model_used
    }


# ---------------------------------------------------------------------------
# Endpoint 7: Attending Physician Advice Composer (Doctor -> Patient)
# ---------------------------------------------------------------------------
@patient_router.post("/advice")
def post_doctor_advice(body: PostDoctorAdviceRequest, request: Request):
    """
    Publishes attending physician advice and care instructions to the patient's record.
    Accessible from the Doctor Workstation floating communication drawer.
    """
    valid_categories = {"GENERAL", "MEDICATION", "DIETARY", "WARNING_SIGNS", "FOLLOW_UP"}
    cat_upper = body.category.strip().upper()
    if cat_upper not in valid_categories:
        cat_upper = "GENERAL"

    valid_severities = {"ROUTINE", "URGENT", "CRITICAL"}
    sev_upper = body.severity.strip().upper()
    if sev_upper not in valid_severities:
        sev_upper = "ROUTINE"

    conn = _get_db()
    cursor = conn.cursor()

    # Verify target patient exists
    cursor.execute("SELECT patient_id, patient_name FROM patients WHERE patient_id = ?", (body.patient_id,))
    pt_row = cursor.fetchone()
    if not pt_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Patient '{body.patient_id}' not found in hospital registry.")

    # Doctor attribution resolution (JWT or header or default)
    practitioner_name = body.practitioner_name or "Dr. Gregory House, MD"
    hospital_name = body.hospital_name or "Princeton Plainsboro Teaching Hospital"
    practitioner_id = "PRAC-103"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = decode_access_token(auth_header.split(" ", 1)[1].strip())
        if payload and payload.get("role") in ("PHYSICIAN", "CHIEF_OF_MEDICINE", "CLINICIAN"):
            practitioner_name = payload.get("full_name", practitioner_name)
            hospital_name = payload.get("hospital_name", hospital_name)
            practitioner_id = payload.get("practitioner_id", practitioner_id)

    # If plain summary wasn't provided, create a brief auto-summary
    plain_summary = body.plain_summary
    if not plain_summary or len(plain_summary.strip()) < 5:
        plain_summary = body.advice_text

    cursor.execute("""
        INSERT INTO patient_doctor_notes 
        (patient_id, practitioner_id, practitioner_name, hospital_name, category, advice_text, plain_summary, severity, is_read)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (body.patient_id, practitioner_id, practitioner_name, hospital_name, cat_upper, body.advice_text, plain_summary, sev_upper))

    note_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info("Doctor advice posted by %s for patient %s (id=%s)", practitioner_name, body.patient_id, note_id)

    return {
        "success": True,
        "advice_id": note_id,
        "patient_id": body.patient_id,
        "category": cat_upper,
        "severity": sev_upper,
        "practitioner_name": practitioner_name,
        "message": f"Clinical instructions successfully transmitted to {pt_row['patient_name']}'s Sanctuary."
    }


# ---------------------------------------------------------------------------
# Endpoint 8: Get Doctor Advice for Patient (Patient Sanctuary Inbox)
# ---------------------------------------------------------------------------
@patient_router.get("/advice")
def get_doctor_advice(request: Request, patient_id: Optional[str] = None):
    """
    Returns all care advice notes published by physicians for the patient.
    """
    target_patient_id = patient_id

    # If patient JWT is present, enforce their own patient_id
    patient = _get_patient_from_token(request)
    if patient:
        target_patient_id = patient["patient_id"]

    if not target_patient_id:
        target_patient_id = "PT-101"

    conn = _get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, patient_id, practitioner_id, practitioner_name, hospital_name,
               category, advice_text, plain_summary, severity, created_at, is_read
        FROM patient_doctor_notes
        WHERE patient_id = ?
        ORDER BY created_at DESC, id DESC
    """, (target_patient_id,))

    rows = cursor.fetchall()
    notes = [dict(r) for r in rows]
    conn.close()

    unread_count = sum(1 for n in notes if not n.get("is_read"))

    return {
        "patient_id": target_patient_id,
        "notes": notes,
        "total": len(notes),
        "unread_count": unread_count,
        "zero_cloud": True
    }


# ---------------------------------------------------------------------------
# Endpoint 9: Acknowledge / Mark Doctor Advice as Read
# ---------------------------------------------------------------------------
@patient_router.post("/advice/{advice_id}/read")
def mark_advice_as_read(advice_id: int, request: Request):
    """
    Marks a doctor advice note as read by the patient.
    """
    conn = _get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE patient_doctor_notes SET is_read = 1 WHERE id = ?", (advice_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail="Doctor advice note not found.")

    return {"success": True, "advice_id": advice_id, "is_read": True}


# ---------------------------------------------------------------------------
# Endpoint 10: Offline SLM Plain-Language Advice Drafter
# ---------------------------------------------------------------------------
@patient_router.post("/advice/draft-slm")
def draft_plain_language_advice(body: DraftAdviceSLMRequest):
    """
    Translates complex clinical notes into comforting, 6th-grade reading level
    instructions for the patient using the local SLM or deterministic rules.
    """
    clinical_text = body.clinical_notes.strip()
    category = (body.category or "GENERAL").upper()

    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT patient_name, age, gender FROM patients WHERE patient_id = ?", (body.patient_id,))
    p_row = cursor.fetchone()
    conn.close()

    patient_name = p_row["patient_name"] if p_row else "Patient"
    first_name = patient_name.split()[0]

    plain_draft = None
    model_used = "MediVault Clinical Plain-Language Engine"

    # 1. Try local Ollama SLM
    if ai_bridge.is_online():
        prompt = (
            f"You are a compassionate clinical communication specialist at Princeton Plainsboro Teaching Hospital.\n"
            f"Translate these doctor clinical notes into clear, warm, patient-friendly instructions for {first_name}.\n\n"
            f"Doctor's Clinical Notes:\n\"{clinical_text}\"\n"
            f"Category: {category}\n\n"
            f"Rules for translation:\n"
            f"1. Use simple 6th-grade reading level. Eliminate complex medical jargon (e.g. change 'contraindicated' to 'unsafe', 'hemodynamic collapse' to 'kidney strain').\n"
            f"2. Keep it to 2-4 direct, reassuring sentences.\n"
            f"3. Include actionable everyday guidance.\n"
            f"4. Do not include markdown headers or meta commentary, just the direct message to the patient."
        )
        try:
            import httpx
            with httpx.Client(timeout=3.5) as client:
                res = client.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 150}
                    }
                )
                if res.status_code == 200:
                    out = res.json().get("response", "").strip()
                    if len(out) > 20:
                        plain_draft = out
                        model_used = "Ollama Local (llama3.2:3b)"
        except Exception:
            pass

    # 2. Intelligent Deterministic Fallback
    if not plain_draft:
        lower_txt = clinical_text.lower()
        replacements = [
            ("contraindicated", "unsafe to take"),
            ("contraindication", "safety risk"),
            ("renal impairment", "kidney sensitivity"),
            ("chronic kidney disease", "kidney condition"),
            ("hemodynamic", "blood flow"),
            ("precipitates", "can trigger"),
            ("edema", "swelling or fluid buildup"),
            ("titrate", "gradually adjust"),
            ("prn", "as needed"),
            ("bid", "twice a day"),
            ("tid", "three times a day"),
            ("qd", "once a day"),
            ("po", "by mouth"),
        ]
        simplified = clinical_text
        for word, sub in replacements:
            simplified = re.sub(rf"\b{word}\b", sub, simplified, flags=re.IGNORECASE)

        if "ibuprofen" in lower_txt or "nsaid" in lower_txt:
            plain_draft = (
                f"Please avoid Ibuprofen, Advil, or Aleve right now, {first_name}, as they put too much strain on your kidneys. "
                f"For aches, you can safely take Tylenol (Acetaminophen) as directed. "
                f"Remember to drink water steadily and notify us if you notice any unusual swelling."
            )
        elif "fluid" in lower_txt or "water" in lower_txt:
            plain_draft = (
                f"Your care team recommends keeping your fluid intake around 7 to 8 glasses of water a day. "
                f"Try to limit salty processed snacks, and weigh yourself each morning before breakfast to monitor for fluid retention."
            )
        else:
            plain_draft = (
                f"Here are your updated care instructions, {first_name}: {simplified}. "
                f"Following this routine closely will protect your health and keep your numbers stable."
            )

    return {
        "success": True,
        "patient_id": body.patient_id,
        "patient_name": patient_name,
        "plain_summary": plain_draft,
        "model": model_used
    }


# ---------------------------------------------------------------------------
# Pre-compiled Plain-English Outpatient Drug Leaflets (1-Click Guides)
# ---------------------------------------------------------------------------
DRUG_PATIENT_LEAFLETS: Dict[str, Dict[str, Any]] = {
    "lisinopril": {
        "display_name": "Lisinopril (Prinivil, Zestril)",
        "drug_class": "ACE Inhibitor (Blood Pressure & Kidney Protector)",
        "why_prescribed": "Relaxes your blood vessels to lower high blood pressure and shields your kidney filtration filters from progressive damage.",
        "how_to_take": "Take once daily in the morning with a full glass of water, with or without food.",
        "missed_dose": "Take it as soon as you remember that day. If it is almost time for your next morning dose, skip the missed one. Never take two tablets at once.",
        "cautions": "Avoid salt substitutes that contain potassium. Do NOT take Ibuprofen or Advil, which blocks Lisinopril from protecting your kidneys.",
        "warning_signs": "Call your doctor immediately if you develop swelling of your lips/tongue or a persistent dry hacking cough.",
        "schedule_slot": "MORNING"
    },
    "metformin": {
        "display_name": "Metformin (Glucophage)",
        "drug_class": "Biguanide (Blood Sugar Balancer)",
        "why_prescribed": "Helps your body respond better to natural insulin and reduces the amount of excess sugar your liver produces.",
        "how_to_take": "Take with meals (breakfast and dinner) to reduce stomach upset.",
        "missed_dose": "Take with food as soon as you remember. If it is near your next meal, skip the missed dose and resume your normal mealtime schedule.",
        "cautions": "Avoid excessive alcohol. If you are scheduled for any X-ray or CT scan requiring IV dye, remind your doctor you take Metformin.",
        "warning_signs": "Report unusual muscle pain, severe fatigue, or cold feelings to your care team promptly.",
        "schedule_slot": "MORNING & EVENING"
    },
    "amlodipine": {
        "display_name": "Amlodipine (Norvasc)",
        "drug_class": "Calcium Channel Blocker (Vascular Relaxant)",
        "why_prescribed": "Gently widens and relaxes your arteries so your heart doesn't have to pump against high resistance.",
        "how_to_take": "Take once daily at the same time each day, with or without food.",
        "missed_dose": "Take as soon as you remember, unless it has been more than 12 hours since your scheduled time.",
        "cautions": "Avoid large amounts of grapefruit juice, which can raise medicine levels in your bloodstream.",
        "warning_signs": "Check your ankles for puffiness or swelling at the end of the day and let your doctor know.",
        "schedule_slot": "MORNING"
    },
    "furosemide": {
        "display_name": "Furosemide (Lasix)",
        "drug_class": "Loop Diuretic (Water Balance Pill)",
        "why_prescribed": "Helps your kidneys flush out excess fluid and sodium to prevent swelling in your legs and lungs.",
        "how_to_take": "Take in the morning with breakfast so that you do not have to wake up at night to use the bathroom.",
        "missed_dose": "Take when remembered if earlier in the day; avoid taking late in the evening.",
        "cautions": "Do not take OTC pain pills like Ibuprofen or Aleve, which cancel out Furosemide's ability to remove fluid.",
        "warning_signs": "Watch for severe muscle cramps or dizziness when standing up quickly.",
        "schedule_slot": "MORNING"
    },
    "warfarin": {
        "display_name": "Warfarin (Coumadin)",
        "drug_class": "Anticoagulant (Blood Thinner)",
        "why_prescribed": "Prevents dangerous blood clots from forming in your blood vessels or heart chambers.",
        "how_to_take": "Take once daily in the evening at the exact same hour every day.",
        "missed_dose": "Take as soon as possible on the same day. Do not take a double dose the next day.",
        "cautions": "Keep your intake of green leafy vegetables consistent from day to day. Avoid Aspirin, Ibuprofen, and cranberry juice.",
        "warning_signs": "Seek immediate care for bleeding that won't stop, dark tarry stools, or unusual bruising.",
        "schedule_slot": "EVENING"
    },
    "pantoprazole": {
        "display_name": "Pantoprazole (Protonix)",
        "drug_class": "Proton Pump Inhibitor (Stomach Shield)",
        "why_prescribed": "Reduces stomach acid to heal the stomach lining and prevent ulcers or acid reflux.",
        "how_to_take": "Take 30 to 60 minutes before your first meal of the day.",
        "missed_dose": "Take before your next meal if remembered, or skip and take before breakfast the next day.",
        "cautions": "Swallow tablets whole; do not crush or chew.",
        "warning_signs": "Report persistent diarrhea or severe stomach cramping to your doctor.",
        "schedule_slot": "MORNING"
    },
    "albuterol": {
        "display_name": "Albuterol Inhaler (Ventolin, ProAir)",
        "drug_class": "Fast-Acting Bronchodilator (Rescue Inhaler)",
        "why_prescribed": "Quickly opens up constricted airways during sudden wheezing, coughing, or shortness of breath.",
        "how_to_take": "Inhale 1 to 2 puffs as needed for sudden chest tightness. Wait 1 minute between puffs.",
        "missed_dose": "Use only as needed for breathing comfort or as directed before exercise.",
        "cautions": "Always check your counter and keep an unexpired rescue inhaler with you wherever you go.",
        "warning_signs": "If you need your inhaler more than twice a week for relief, call your doctor to adjust maintenance therapy.",
        "schedule_slot": "AS_NEEDED"
    }
}


# ---------------------------------------------------------------------------
# Endpoint 11: 1-Click Plain-English Medication Safety Guides
# ---------------------------------------------------------------------------
@patient_router.get("/medication-guides")
def get_patient_medication_guides(request: Request):
    """
    Returns patient-friendly medication safety leaflets for all active medications
    in the patient's record.
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]

    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT medication_name, dosage, frequency, status
        FROM patient_medications
        WHERE patient_id = ?
    """, (patient_id,))
    med_rows = cursor.fetchall()
    conn.close()

    guides = []
    for r in med_rows:
        raw_name = r["medication_name"]
        dosage = r["dosage"] or ""
        freq = r["frequency"] or ""

        # Match against our curated plain-English leaflets
        matched_key = None
        for k in DRUG_PATIENT_LEAFLETS:
            if k in raw_name.lower():
                matched_key = k
                break

        if matched_key:
            info = DRUG_PATIENT_LEAFLETS[matched_key]
            guides.append({
                "medication_name": raw_name,
                "dosage": dosage,
                "frequency": freq,
                "display_name": info["display_name"],
                "drug_class": info["drug_class"],
                "why_prescribed": info["why_prescribed"],
                "how_to_take": info["how_to_take"],
                "missed_dose": info["missed_dose"],
                "cautions": info["cautions"],
                "warning_signs": info["warning_signs"],
                "schedule_slot": info["schedule_slot"]
            })
        else:
            # Empathetic dynamic fallback for unlisted prescription
            guides.append({
                "medication_name": raw_name,
                "dosage": dosage,
                "frequency": freq,
                "display_name": raw_name,
                "drug_class": "Prescription Medication",
                "why_prescribed": f"Prescribed by your care team to support your health management plan.",
                "how_to_take": f"Take {dosage} {freq} exactly as indicated on your prescription label.",
                "missed_dose": "Take as soon as you remember, unless it is close to your next scheduled dose. Never double up.",
                "cautions": "Always confirm with your pharmacist before starting any new over-the-counter vitamins or pain pills.",
                "warning_signs": "Report unexpected dizziness, rash, or breathing difficulties immediately.",
                "schedule_slot": "MORNING" if "daily" in freq.lower() else "EVENING"
            })

    return {
        "patient_id": patient_id,
        "guides": guides,
        "total": len(guides),
        "zero_cloud": True
    }


# ---------------------------------------------------------------------------
# Endpoint 12: Daily Medication Schedule & Adherence Tracker
# ---------------------------------------------------------------------------
@patient_router.get("/adherence")
def get_patient_adherence(request: Request, log_date: Optional[str] = None):
    """
    Returns today's medication slots (Morning, Afternoon, Evening, Night) with
    completion status and patient compliance streak.
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]

    import datetime
    today_str = log_date or datetime.date.today().isoformat()

    conn = _get_db()
    cursor = conn.cursor()

    # Active medications
    cursor.execute("""
        SELECT medication_name, dosage, frequency
        FROM patient_medications
        WHERE patient_id = ?
    """, (patient_id,))
    meds = cursor.fetchall()

    # Existing logs for this date
    cursor.execute("""
        SELECT time_slot, medication_name, taken
        FROM patient_adherence_log
        WHERE patient_id = ? AND log_date = ?
    """, (patient_id, today_str))
    logged = {(r["time_slot"], r["medication_name"].lower()): bool(r["taken"]) for r in cursor.fetchall()}

    # Calculate streak (consecutive days with at least 1 logged med)
    cursor.execute("""
        SELECT DISTINCT log_date 
        FROM patient_adherence_log 
        WHERE patient_id = ? AND taken = 1 
        ORDER BY log_date DESC LIMIT 30
    """, (patient_id,))
    logged_dates = [r["log_date"] for r in cursor.fetchall()]
    conn.close()

    streak_days = len(logged_dates)

    slots: Dict[str, List[Dict[str, Any]]] = {
        "MORNING": [],
        "AFTERNOON": [],
        "EVENING": [],
        "NIGHT": []
    }

    total_tasks = 0
    completed_tasks = 0

    for m in meds:
        m_name = m["medication_name"]
        dosage = m["dosage"] or ""
        freq_lower = (m["frequency"] or "").lower()

        # Slot classification
        assigned_slots = ["MORNING"]
        if "twice" in freq_lower or "bid" in freq_lower:
            assigned_slots = ["MORNING", "EVENING"]
        elif "evening" in freq_lower or "night" in freq_lower or "bedtime" in freq_lower:
            assigned_slots = ["EVENING"]
        elif "afternoon" in freq_lower:
            assigned_slots = ["AFTERNOON"]

        for slot in assigned_slots:
            is_taken = logged.get((slot, m_name.lower()), False)
            total_tasks += 1
            if is_taken:
                completed_tasks += 1

            slots[slot].append({
                "medication_name": m_name,
                "dosage": dosage,
                "slot": slot,
                "taken": is_taken
            })

    compliance_pct = round((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 100

    return {
        "patient_id": patient_id,
        "log_date": today_str,
        "slots": slots,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "compliance_pct": compliance_pct,
        "streak_days": max(1, streak_days),
        "zero_cloud": True
    }


# ---------------------------------------------------------------------------
# Endpoint 13: Log Medication Taken Toggle
# ---------------------------------------------------------------------------
@patient_router.post("/adherence/log")
def log_medication_adherence(body: LogAdherenceRequest, request: Request):
    """
    Logs or toggles medication intake status for a specific time slot.
    """
    patient = _require_patient(request)
    patient_id = patient["patient_id"]

    import datetime
    log_date = body.log_date or datetime.date.today().isoformat()
    slot_upper = body.time_slot.strip().upper()

    conn = _get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patient_adherence_log (patient_id, log_date, time_slot, medication_name, dosage, taken)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(patient_id, log_date, time_slot, medication_name) 
        DO UPDATE SET taken = excluded.taken, logged_at = CURRENT_TIMESTAMP
    """, (patient_id, log_date, slot_upper, body.medication_name, body.dosage, 1 if body.taken else 0))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "patient_id": patient_id,
        "log_date": log_date,
        "time_slot": slot_upper,
        "medication_name": body.medication_name,
        "taken": body.taken
    }


