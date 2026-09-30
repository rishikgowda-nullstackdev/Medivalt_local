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

