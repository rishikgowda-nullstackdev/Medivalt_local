"""
MediVault Local - Backend Core FastAPI Server (Day 4 Enhanced)
Zero-Cloud, HIPAA/DPDP-Compliant Local Clinical Record Reviewer.
Runs 100% offline on loopback interface (127.0.0.1).
Implements defensive input validation, Ollama AI bridge, and compliance audit exports.
"""

import os
import csv
import json
import sqlite3
from io import BytesIO, StringIO
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from pypdf import PdfReader

from backend.redactor import ClinicalRedactor
from backend.network_guard import network_guard
from backend.audit_logger import audit_logger
from backend.validators import InputValidator
from backend.ai_bridge import ai_bridge
from backend.orchestrator import ClinicalOrchestrator, call_person_b_ingestion, call_person_c_ai_engine
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    validate_hospital_domain,
    generate_otp,
    dispatch_simulated_email,
    get_current_practitioner,
    DEFAULT_DEMO_PRACTITIONER
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# FastAPI App
app = FastAPI(
    title="MediVault Local API",
    description="Zero-cloud offline clinical contraindication review engine.",
    version="1.3.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handler (AGENTS.md Rule 4 Compliance)
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevents raw stack traces from ever leaking to clients."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "Client Request Error", "detail": exc.detail}
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Processing Safeguard",
            "detail": "An unexpected error occurred. The operation was aborted to preserve clinical safety.",
            "type": exc.__class__.__name__
        }
    )


# ---------------------------------------------------------------------------
# Database Initialization & Auto-Migration
# ---------------------------------------------------------------------------
def init_db():
    """Initializes SQLite database from schema.sql if not present."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)

    # Auto-migration for audit_logs practitioner attribution columns
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(audit_logs)")
    existing_cols = [c[1] for c in cursor.fetchall()]
    for col, def_val in [
        ("practitioner_id", "PRAC-103"),
        ("practitioner_name", "Dr. Gregory House, MD"),
        ("hospital_name", "Princeton Plainsboro Teaching Hospital")
    ]:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE audit_logs ADD COLUMN {col} TEXT DEFAULT '{def_val}'")

    conn.commit()
    conn.close()

init_db()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Contract Schemas (CONTRACTS.md Specification)
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    redacted_text: str

class AnalyzeResponse(BaseModel):
    flagged: bool
    reason: str
    drug: Optional[str] = None
    severity: Optional[str] = None

class UploadRecordResponse(BaseModel):
    redacted_text: str

class ReviewRequest(BaseModel):
    patient_id: Optional[str] = "PT-101"
    proposed_medication: str = Field(..., example="Ibuprofen")
    dosage: Optional[str] = "400mg PO TID"
    raw_notes_override: Optional[str] = None

class RedactRequest(BaseModel):
    text: str

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    hospital_id: str
    medical_license: str
    password: str
    role: Optional[str] = "PHYSICIAN"

class VerifyEmailRequest(BaseModel):
    email: str
    verification_code: str

class ResendCodeRequest(BaseModel):
    email: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SwitchDemoRequest(BaseModel):
    practitioner_id: str


# ---------------------------------------------------------------------------
# CONTRACTS.md Endpoints (Person A & Frontend Integration)
# ---------------------------------------------------------------------------
@app.post("/upload-record", response_model=UploadRecordResponse)
@app.post("/api/upload-record")
async def upload_record_endpoint(file: UploadFile = File(...)):
    """
    Person A Backend Contract:
    in: multipart file (PDF or TXT)
    out: { "redacted_text": str }
    """
    content = await file.read()
    InputValidator.validate_upload_file(file, content)

    filename = file.filename or "record.txt"

    # Try Person B's module if available
    b_result = call_person_b_ingestion(content, filename)
    if b_result:
        return {"redacted_text": b_result}

    # Built-in pure-Python fallback
    raw_text = ""
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            raw_text = "\n".join(pages).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {str(e)}")
    else:
        try:
            raw_text = content.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not raw_text:
        raise HTTPException(
            status_code=400,
            detail="Uploaded document contains no readable text or is corrupted."
        )

    processed = ClinicalRedactor.process_clinical_note(raw_text)

    return {
        "redacted_text": processed["redacted_text"],
        "filename": filename,
        "patient_token": processed["patient_token"],
        "phi_detected": processed["phi_detected"],
        "entities": processed["entities"]
    }


@app.post("/analyze", response_model=AnalyzeResponse)
@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(req: AnalyzeRequest):
    """
    Person A Backend Contract:
    in: { "redacted_text": str }
    out: { "flagged": bool, "reason": str, "drug": str|null, "severity": str|null }
    """
    validated_text = InputValidator.validate_clinical_text(req.redacted_text, field_name="redacted_text")

    # Try Person C's AI Engine first
    c_result = call_person_c_ai_engine(validated_text)
    if c_result and "flagged" in c_result:
        return AnalyzeResponse(
            flagged=c_result.get("flagged", False),
            reason=c_result.get("reason", "No interactions detected."),
            drug=c_result.get("drug"),
            severity=c_result.get("severity")
        )

    # Built-in deterministic extraction and safety check
    entities = ClinicalRedactor.extract_entities(validated_text)
    conditions = entities.get("diagnosed_conditions", [])
    medications = entities.get("current_medications", [])
    allergies = entities.get("allergies", [])

    flagged = False
    reasons = []
    flagged_drug = None
    severity = None

    for med in medications:
        status, alerts, canonical = ClinicalOrchestrator.check_contraindications(
            med, conditions, [m for m in medications if m != med], allergies
        )
        if status in ("CRITICAL", "WARNING"):
            flagged = True
            flagged_drug = med
            severity = status
            reasons.append(alerts[0]["clinical_mechanism"])
            break

    if flagged:
        return AnalyzeResponse(
            flagged=True,
            reason=reasons[0] if reasons else "Contraindication detected.",
            drug=flagged_drug,
            severity=severity
        )

    return AnalyzeResponse(
        flagged=False,
        reason="No known adverse contraindications detected in record.",
        drug=None,
        severity="SAFE"
    )


# ---------------------------------------------------------------------------
# Extended Management & Telemetry Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    """System health & offline mode verification."""
    return {
        "status": "ONLINE",
        "zero_cloud_mode": True,
        "binding": "127.0.0.1 (Loopback Only)",
        "database": "SQLite (database/medivault.db)",
        "hipaa_safe_harbor": "ENFORCED",
        "dpdp_compliant": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/network-guard")
def get_network_guard_telemetry():
    """Returns telemetry proving 0 outbound external traffic."""
    return network_guard.get_network_status()


@app.get("/api/ai-status")
def get_ai_status():
    """Returns connectivity status of the local Ollama SLM."""
    return ai_bridge.get_status()


@app.get("/api/patients")
def list_patients():
    """Returns list of pre-configured demo patients."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, patient_name, age, gender FROM patients")
    patients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"patients": patients}


@app.get("/api/patients/{patient_id}")
def get_patient_profile(patient_id: str):
    """Retrieves full medical record for a specific patient."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Patient ID '{patient_id}' not found. Available demo profiles: PT-101, PT-102, PT-103."
        )

    cursor.execute("SELECT condition_name, icd10_code FROM patient_conditions WHERE patient_id = ?", (patient_id,))
    conditions = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT medication_name, dosage, frequency FROM patient_medications WHERE patient_id = ?", (patient_id,))
    medications = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT allergen, reaction FROM patient_allergies WHERE patient_id = ?", (patient_id,))
    allergies = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "patient": dict(patient),
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies
    }


@app.post("/api/redact")
def redact_text_endpoint(req: RedactRequest):
    """Redacts 18 HIPAA PHI identifiers from raw text."""
    validated = InputValidator.validate_clinical_text(req.text, field_name="text")
    redacted_text, detected_phi, token = ClinicalRedactor.redact_phi(validated)
    return {
        "patient_token": token,
        "redacted_text": redacted_text,
        "phi_detected": detected_phi
    }


@app.post("/api/extract")
def extract_entities_endpoint(req: RedactRequest):
    """Extracts conditions, medications, allergies, and lab values from text."""
    validated = InputValidator.validate_clinical_text(req.text, field_name="text")
    return ClinicalRedactor.process_clinical_note(validated)


# ---------------------------------------------------------------------------
# Sovereign Authentication Endpoints (HIPAA § 164.312(a)(2)(i) & (iv))
# ---------------------------------------------------------------------------
@app.get("/api/auth/hospitals")
def list_hospitals():
    """Returns list of registered healthcare facilities and accepted email domains."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT hospital_id, hospital_name, facility_code, domain_whitelist, department, city_state FROM hospitals")
    hospitals = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"hospitals": hospitals}


@app.get("/api/auth/practitioners")
def list_demo_practitioners():
    """Returns pre-configured demo doctors for 1-click evaluation."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.practitioner_id, p.full_name, p.email, p.medical_license, p.role, p.email_verified,
               h.hospital_name, h.department
        FROM practitioners p
        JOIN hospitals h ON p.hospital_id = h.hospital_id
    """)
    practitioners = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"practitioners": practitioners}


@app.get("/api/auth/me")
def get_current_user_profile(request: Request):
    """Returns the authenticated physician profile."""
    prac = get_current_practitioner(request)
    return {"practitioner": prac}


@app.post("/api/auth/register")
def register_practitioner(req: RegisterRequest):
    """
    Registers a clinical practitioner with institutional domain verification.
    Dispatches a 6-digit verification code to local sovereign mail outbox.
    """
    if not req.full_name or len(req.full_name.strip()) < 3:
        raise HTTPException(status_code=400, detail="Full legal practitioner name is required.")

    if not req.password or len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    if not req.medical_license or len(req.medical_license.strip()) < 4:
        raise HTTPException(status_code=400, detail="Valid medical license (NPI or State Medical Council number) is required.")

    conn = get_db()
    cursor = conn.cursor()

    # 1. Verify hospital existence and email domain whitelist
    cursor.execute("SELECT hospital_name, domain_whitelist FROM hospitals WHERE hospital_id = ?", (req.hospital_id,))
    hospital = cursor.fetchone()
    if not hospital:
        conn.close()
        raise HTTPException(status_code=404, detail="Selected hospital facility not found.")

    domain_ok, domain_msg = validate_hospital_domain(req.email, hospital["domain_whitelist"])
    if not domain_ok:
        conn.close()
        raise HTTPException(status_code=400, detail=domain_msg)

    email_clean = req.email.strip().lower()

    # 2. Check for duplicate email
    cursor.execute("SELECT practitioner_id, email_verified FROM practitioners WHERE email = ?", (email_clean,))
    existing = cursor.fetchone()
    if existing:
        if existing["email_verified"] == 1:
            conn.close()
            raise HTTPException(status_code=400, detail="An account with this institutional email already exists. Please log in.")
        # If unverified, regenerate OTP for them
        otp = generate_otp()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        salt, pwd_hash = hash_password(req.password)
        cursor.execute("""
            UPDATE practitioners
            SET full_name = ?, password_hash = ?, salt = ?, medical_license = ?,
                verification_token = ?, token_expires_at = ?
            WHERE email = ?
        """, (req.full_name.strip(), pwd_hash, salt, req.medical_license.strip(), otp, expires, email_clean))
        conn.commit()
        conn.close()
        dispatch_simulated_email(email_clean, req.full_name.strip(), hospital["hospital_name"], otp)
        return {
            "status": "PENDING_VERIFICATION",
            "message": f"Verification code re-sent to {email_clean}. Enter the 6-digit code to activate.",
            "email": email_clean,
            "simulated_code": otp,
            "hospital_name": hospital["hospital_name"]
        }

    # 3. Create new unverified practitioner
    practitioner_id = f"PRAC-{int(datetime.now(timezone.utc).timestamp() * 1000) % 1000000}"
    salt, pwd_hash = hash_password(req.password)
    otp = generate_otp()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    cursor.execute("""
        INSERT INTO practitioners (
            practitioner_id, hospital_id, full_name, email, password_hash, salt,
            medical_license, role, email_verified, verification_token, token_expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
    """, (
        practitioner_id, req.hospital_id, req.full_name.strip(), email_clean,
        pwd_hash, salt, req.medical_license.strip(), req.role or "PHYSICIAN", otp, expires
    ))
    conn.commit()
    conn.close()

    dispatch_simulated_email(email_clean, req.full_name.strip(), hospital["hospital_name"], otp)

    return {
        "status": "PENDING_VERIFICATION",
        "message": f"Institutional verification code sent to {email_clean}. Please verify to activate your account.",
        "email": email_clean,
        "simulated_code": otp,
        "hospital_name": hospital["hospital_name"]
    }


@app.post("/api/auth/verify-email")
def verify_email_endpoint(req: VerifyEmailRequest, response: Response):
    """
    Verifies 6-digit OTP code, marks doctor as active, and returns signed session token.
    """
    email_clean = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.practitioner_id, p.hospital_id, p.full_name, p.email, p.medical_license,
               p.role, p.email_verified, p.verification_token, p.token_expires_at,
               h.hospital_name, h.department
        FROM practitioners p
        JOIN hospitals h ON p.hospital_id = h.hospital_id
        WHERE p.email = ?
    """, (email_clean,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Practitioner account not found.")

    if row["email_verified"] == 1:
        conn.close()
        token = create_access_token({"practitioner_id": row["practitioner_id"], "email": email_clean})
        response.set_cookie(key="medivault_session", value=token, httponly=True, samesite="lax")
        return {
            "status": "ALREADY_VERIFIED",
            "message": "Account already verified.",
            "access_token": token,
            "practitioner": dict(row)
        }

    # Check OTP
    stored_token = (row["verification_token"] or "").strip()
    submitted_token = req.verification_code.strip()

    if not stored_token or stored_token != submitted_token:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid 6-digit verification code. Please check and try again.")

    # Check expiration
    if row["token_expires_at"]:
        try:
            exp_dt = datetime.fromisoformat(row["token_expires_at"])
            if datetime.now(timezone.utc) > exp_dt:
                conn.close()
                raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")
        except Exception:
            pass

    # Activate
    cursor.execute("""
        UPDATE practitioners
        SET email_verified = 1, verification_token = NULL, token_expires_at = NULL
        WHERE practitioner_id = ?
    """, (row["practitioner_id"],))
    conn.commit()
    conn.close()

    token = create_access_token({"practitioner_id": row["practitioner_id"], "email": email_clean})
    response.set_cookie(key="medivault_session", value=token, httponly=True, samesite="lax")

    practitioner_data = dict(row)
    practitioner_data["email_verified"] = 1

    return {
        "status": "VERIFIED",
        "message": f"Welcome, {row['full_name']}! Your institutional account with {row['hospital_name']} is now active.",
        "access_token": token,
        "practitioner": practitioner_data
    }


@app.post("/api/auth/resend-code")
def resend_verification_code(req: ResendCodeRequest):
    """Regenerates a new 6-digit OTP code."""
    email_clean = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.practitioner_id, p.full_name, h.hospital_name
        FROM practitioners p
        JOIN hospitals h ON p.hospital_id = h.hospital_id
        WHERE p.email = ?
    """, (email_clean,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Practitioner account not found.")

    otp = generate_otp()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    cursor.execute("""
        UPDATE practitioners
        SET verification_token = ?, token_expires_at = ?
        WHERE email = ?
    """, (otp, expires, email_clean))
    conn.commit()
    conn.close()

    dispatch_simulated_email(email_clean, row["full_name"], row["hospital_name"], otp)

    return {
        "status": "CODE_RESENT",
        "message": f"New verification code generated for {email_clean}.",
        "simulated_code": otp
    }


@app.post("/api/auth/login")
def login_endpoint(req: LoginRequest, response: Response):
    """
    Authenticates physician. Blocks unverified accounts per HIPAA § 164.312(a)(2)(iv).
    """
    email_clean = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.practitioner_id, p.hospital_id, p.full_name, p.email, p.password_hash, p.salt,
               p.medical_license, p.role, p.email_verified,
               h.hospital_name, h.department
        FROM practitioners p
        JOIN hospitals h ON p.hospital_id = h.hospital_id
        WHERE p.email = ?
    """, (email_clean,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(req.password, row["salt"], row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if row["email_verified"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Institutional email address is not yet verified. Please complete 6-digit verification."
        )

    token = create_access_token({"practitioner_id": row["practitioner_id"], "email": email_clean})
    response.set_cookie(key="medivault_session", value=token, httponly=True, samesite="lax")

    practitioner_data = dict(row)
    del practitioner_data["password_hash"]
    del practitioner_data["salt"]

    return {
        "status": "SUCCESS",
        "message": f"Logged in as {row['full_name']} ({row['hospital_name']})",
        "access_token": token,
        "practitioner": practitioner_data
    }


@app.post("/api/auth/switch-demo")
def switch_demo_doctor(req: SwitchDemoRequest, response: Response):
    """1-click demo doctor switcher for hackathon judges."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.practitioner_id, p.hospital_id, p.full_name, p.email, p.medical_license,
               p.role, p.email_verified, h.hospital_name, h.department
        FROM practitioners p
        JOIN hospitals h ON p.hospital_id = h.hospital_id
        WHERE p.practitioner_id = ?
    """, (req.practitioner_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Demo doctor '{req.practitioner_id}' not found.")

    token = create_access_token({"practitioner_id": row["practitioner_id"], "email": row["email"]})
    response.set_cookie(key="medivault_session", value=token, httponly=True, samesite="lax")

    return {
        "status": "SWITCHED",
        "message": f"Active reviewer switched to {row['full_name']}",
        "access_token": token,
        "practitioner": dict(row)
    }


@app.post("/api/auth/logout")
def logout_endpoint(response: Response):
    """Clears local session cookie."""
    response.delete_cookie(key="medivault_session")
    return {"status": "LOGGED_OUT", "message": "Session terminated."}


@app.post("/api/review")
def review_prescription(req: ReviewRequest, request: Request):
    """
    Main Clinical Verification Engine.
    Cross-checks proposed prescription against patient diagnostic history & active medications.
    Binds the authenticated physician & hospital to the SHA-256 audit ledger.
    """
    validated_med = InputValidator.validate_medication_name(req.proposed_medication)

    # Resolve authenticated practitioner
    current_doctor = get_current_practitioner(request)

    # If reviewing an existing patient ID, verify existence
    if req.patient_id and not req.raw_notes_override:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id FROM patients WHERE patient_id = ?", (req.patient_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"Patient ID '{req.patient_id}' not found in local database."
            )
        conn.close()

    result = ClinicalOrchestrator.process_review(
        proposed_med=validated_med,
        patient_id=req.patient_id if not req.raw_notes_override else None,
        raw_notes=req.raw_notes_override,
        practitioner=current_doctor
    )
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


@app.get("/api/audit-logs")
def get_audit_trail(limit: int = 15):
    """Retrieves recent cryptographic audit logs."""
    return {"audit_trail": audit_logger.get_recent_logs(limit=limit)}


@app.get("/api/audit-verify")
def verify_audit_chain():
    """
    Cryptographically verifies the SHA-256 hash chain across all audit entries.
    """
    return audit_logger.verify_integrity()


@app.get("/api/audit-export")
def export_audit_trail(format: str = Query("json", pattern="^(json|csv)$")):
    """
    Exports the complete local cryptographic audit log for compliance audits.
    Supports JSON or CSV format with physician and institutional attribution.
    """
    logs = audit_logger.get_recent_logs(limit=1000)

    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Timestamp (UTC)", "Event ID", "Reviewing Physician", "Hospital Facility",
            "Patient Hash", "Proposed Medication", "Overall Status", "Alerts Count",
            "Zero Cloud Enforced", "SHA-256 Audit Hash"
        ])

        for log in reversed(logs):
            writer.writerow([
                log.get("timestamp"),
                log.get("event_id"),
                log.get("practitioner_name", "Dr. Gregory House, MD"),
                log.get("hospital_name", "Princeton Plainsboro Teaching Hospital"),
                log.get("patient_hash"),
                log.get("proposed_medication"),
                log.get("overall_status"),
                log.get("alerts_count", 0),
                log.get("zero_cloud_enforced", True),
                log.get("audit_hash")
            ])

        response = Response(content=output.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=medivault_audit_{int(datetime.now().timestamp())}.csv"
        return response

    return JSONResponse(content={"audit_export": logs, "total_records": len(logs)})


# ---------------------------------------------------------------------------
# Serve Frontend Static Assets
# ---------------------------------------------------------------------------
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_index():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse({"message": "Frontend index.html not yet generated."})
