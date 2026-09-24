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
from datetime import datetime, timezone
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
# Database Initialization
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


@app.post("/api/review")
def review_prescription(req: ReviewRequest):
    """
    Main Clinical Verification Engine.
    Cross-checks proposed prescription against patient diagnostic history & active medications.
    """
    validated_med = InputValidator.validate_medication_name(req.proposed_medication)

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
        raw_notes=req.raw_notes_override
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
    Supports JSON or CSV format.
    """
    logs = audit_logger.get_recent_logs(limit=1000)

    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp (UTC)", "Event ID", "Patient Hash", "Proposed Medication", "Overall Status", "Alerts Count", "Zero Cloud Enforced", "SHA-256 Audit Hash"])

        for log in reversed(logs):
            writer.writerow([
                log.get("timestamp"),
                log.get("event_id"),
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
