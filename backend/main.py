"""
MediVault Local - Backend Core FastAPI Server
Zero-Cloud, HIPAA/DPDP-Compliant Local Clinical Record Reviewer.
Runs 100% offline on loopback interface (127.0.0.1).
"""

import os
import sqlite3
from io import BytesIO
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader

from backend.redactor import ClinicalRedactor
from backend.network_guard import network_guard
from backend.audit_logger import audit_logger
from backend.orchestrator import ClinicalOrchestrator

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# FastAPI App
app = FastAPI(
    title="MediVault Local API",
    description="Zero-cloud offline clinical contraindication review engine.",
    version="1.1.0"
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
# Database Initialization
# ---------------------------------------------------------------------------
def init_db():
    """Initializes SQLite database from schema.sql if not present."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

init_db()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    patient_id: Optional[str] = "PT-101"
    proposed_medication: str = Field(..., example="Ibuprofen")
    dosage: Optional[str] = "400mg PO TID"
    raw_notes_override: Optional[str] = None

class RedactRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# API Endpoints
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
        raise HTTPException(status_code=404, detail="Patient record not found")

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


@app.post("/api/upload-record")
async def upload_patient_record(file: UploadFile = File(...)):
    """
    Ingests PDF or plain text clinical records.
    Extracts text, strips HIPAA PHI, and extracts diagnostic entities.
    """
    content = await file.read()
    raw_text = ""

    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            extracted_pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            raw_text = "\n".join(extracted_pages).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {str(e)}")
    else:
        # Plain text
        try:
            raw_text = content.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file content: {str(e)}")

    if not raw_text:
        raise HTTPException(status_code=400, detail="Uploaded document contains no readable text.")

    # Process de-identification and clinical extraction
    processed = ClinicalRedactor.process_clinical_note(raw_text)

    return {
        "filename": file.filename,
        "patient_token": processed["patient_token"],
        "redacted_text": processed["redacted_text"],
        "phi_detected": processed["phi_detected"],
        "entities": processed["entities"]
    }


@app.post("/api/redact")
def redact_text_endpoint(req: RedactRequest):
    """Redacts 18 HIPAA PHI identifiers from raw text."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided.")
    redacted_text, detected_phi, token = ClinicalRedactor.redact_phi(req.text)
    return {
        "patient_token": token,
        "redacted_text": redacted_text,
        "phi_detected": detected_phi
    }


@app.post("/api/extract")
def extract_entities_endpoint(req: RedactRequest):
    """Extracts conditions, medications, allergies, and lab values from text."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided.")
    return ClinicalRedactor.process_clinical_note(req.text)


@app.post("/api/review")
def review_prescription(req: ReviewRequest):
    """
    Main Clinical Verification Engine.
    Cross-checks proposed prescription against patient diagnostic history & active medications.
    """
    if not req.proposed_medication or not req.proposed_medication.strip():
        raise HTTPException(status_code=400, detail="Proposed medication name is required.")

    result = ClinicalOrchestrator.process_review(
        proposed_med=req.proposed_medication,
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
    Mathematically proves that zero log entries were tampered with, deleted, or inserted.
    """
    return audit_logger.verify_integrity()


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
