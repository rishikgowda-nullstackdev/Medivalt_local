# 🏥 MediVault Local — AI Agent Context Document (Person A / Backend)

> **Project:** MediVault Local · ASYNC'26, Track 1: Sovereign AI  
> **Author:** Person A (Repo Lead + Backend)  
> **Date:** 24 September 2026  
> **Version:** 1.3.0  
> **Stack:** Python 3.10+, FastAPI, SQLite, Ollama (llama3.2:3b), plain HTML/CSS/JS frontend

---

## 📌 HOW TO USE THIS DOCUMENT WITH AN AI AGENT

This document is the **single source of truth** for any AI coding agent (Cursor, Claude, Copilot, Gemini) working on this project. Before writing a single line of code, the agent must read this fully.

**Copy-paste this into your AI agent's context window:**

> "You are helping build MediVault Local — a zero-cloud, HIPAA/DPDP-compliant offline clinical record reviewer. The backend (FastAPI + SQLite) is already fully built by Person A. Your job is to build [PERSON B's ingestion / PERSON C's AI engine / PERSON D's frontend]. You must match the exact function signatures, return types, import paths, and JSON shapes described in this document. Do not deviate from field names. Do not add cloud calls. Do not change the contract endpoints."

Then paste this entire document.

---

## 1. Project Architecture (What Exists, What Needs Work)

```
MediVault Local/
├── backend/          ✅ COMPLETE — Do NOT edit (Person A owns this)
│   ├── main.py       ✅ FastAPI server, all API endpoints
│   ├── orchestrator.py ✅ Clinical pipeline wiring
│   ├── redactor.py   ✅ HIPAA 18-PHI de-identification engine
│   ├── pharmacology.py ✅ Brand→generic drug normalization
│   ├── audit_logger.py ✅ SHA-256 hash-chained audit ledger
│   ├── auth.py       ✅ Offline JWT + PBKDF2 + OTP auth
│   ├── network_guard.py ✅ Zero-cloud loopback enforcement
│   ├── validators.py ✅ Input sanitization
│   ├── ai_bridge.py  ✅ Local Ollama bridge
│   └── benchmarks.py ✅ 5-scenario end-to-end latency runner
│
├── ingestion/        ⚠️  NEEDS WORK — Person B owns this
│   ├── pipeline.py   ✅ Already implemented, needs testing/polish
│   └── __init__.py   ✅ Already implemented
│
├── ai_engine/        ⚠️  NEEDS WORK — Person C owns this
│   ├── engine.py     ✅ Already implemented, needs testing/polish
│   ├── pharmacology.py ✅ Drug knowledge base
│   ├── polypharmacy.py ✅ Triple-Whammy, QTc, Serotonin checks
│   ├── lab_evaluator.py ✅ Quantitative lab biomarker guardrails
│   ├── alternatives.py ✅ Safe formulary alternatives
│   └── __init__.py   ✅ Already implemented
│
├── frontend/         ⚠️  NEEDS WORK — Person D owns this
│   ├── index.html    ⚠️  Needs to call new endpoints + show new UI
│   └── app.js        ⚠️  Needs auth, patient selector, audit panel
│
├── database/
│   ├── schema.sql    ✅ Full SQLite schema (auto-loaded on start)
│   └── medivault.db  ✅ Auto-created on first run
│
└── samples/          ✅ 5 synthetic patient PDF/TXT fixtures for testing
```

### The Data Flow

```
[File Upload] → [Person B: process_file()] → [redacted_text: str]
                                                      ↓
                               [Person C: analyze(redacted_text)] → { flagged, reason, drug, severity }
                                                      ↓
                              [Person A backend: /api/review] → full clinical report
                                                      ↓
                              [Person D frontend: renders badge + alternatives]
```

---

## 2. The Frozen Contract — Field Names Are Locked

> ⚠️ **AI Agent Rule:** Never rename a field. Never change a return type. Never add a cloud API call. The shapes below are locked by `CONTRACTS.md`.

### Contract Function 1 — Person B (Ingestion)

**File:** `ingestion/pipeline.py`  
**Function that backend calls:**

```python
def process_file(file_path_or_bytes: Union[str, bytes], filename: Optional[str] = None) -> str:
    """
    Person B Frozen Contract.
    in:  file bytes (PDF or .txt) or a file path string
    out: a single redacted plain-text string (PHI replaced with [REDACTED_*] tokens)
    """
```

**Example input → output:**
```
in:  b"Patient: John Doe, Phone: 9876543210, Diagnosis: Stage 3 CKD, eGFR: 28"
out: "Patient: [REDACTED_NAME], Phone: [REDACTED_PHONE], Diagnosis: Stage 3 CKD, eGFR: 28"
```

**⚠️ AI Agent Note:** Do NOT redact clinical values like eGFR, drug names, or conditions. Only redact the 18 HIPAA Safe Harbor identifiers.

---

### Contract Function 2 — Person C (AI Engine)

**File:** `ai_engine/engine.py`  
**Function that backend calls:**

```python
def analyze(redacted_text: str) -> dict:
    """
    Person C Frozen Contract.
    in:  a redacted clinical text string
    out: exactly this dict shape — no extra fields, no renamed fields
    """
    # MUST return:
    return {
        "flagged": bool,          # True if any contraindication found
        "reason": str,            # human-readable clinical explanation
        "drug": str | None,       # the problematic drug, or null
        "severity": str | None    # "CRITICAL", "WARNING", or "SAFE"
    }
```

**Example output (contraindication found):**
```json
{
  "flagged": true,
  "reason": "Administration of Ibuprofen is contraindicated in Stage 3 CKD. NSAIDs reduce renal prostaglandin synthesis, causing acute kidney injury in patients with impaired baseline GFR.",
  "drug": "Ibuprofen",
  "severity": "CRITICAL"
}
```

**Example output (safe):**
```json
{
  "flagged": false,
  "reason": "No adverse interactions detected.",
  "drug": null,
  "severity": "SAFE"
}
```

---

### Contract Endpoints — Person A (Backend, Already Built)

#### `POST /upload-record`
```
in:  multipart/form-data, key="file", value=<PDF or .txt bytes>
out: { "redacted_text": "Patient: [REDACTED_NAME], Diagnosis: Stage 3 CKD..." }
```

#### `POST /analyze`
```
in:  Content-Type: application/json
     { "redacted_text": "Patient: [REDACTED_NAME], Diagnosis: Stage 3 CKD..." }
out: { "flagged": true, "reason": "...", "drug": "Ibuprofen", "severity": "CRITICAL" }
```

---

## 3. Person B — What Your AI Agent Needs to Build / Verify

> **Folder:** `/ingestion/` only. Do not touch `/backend/` or `/ai_engine/`.

### 3.1 Functions That Must Exist in `ingestion/pipeline.py`

The backend imports these at runtime. If they are missing or renamed, the backend silently falls back to its own copy — but Person B's version should be the one running.

```python
# ── MUST EXPORT ────────────────────────────────────────────────

def process_file(file_path_or_bytes: Union[str, bytes], filename: Optional[str] = None) -> str:
    """Main contract function. Calls extract_text() then redact_phi()."""

def extract_text(file_source: Union[str, bytes], filename: Optional[str] = None) -> str:
    """Extracts raw text from PDF (pypdf) or TXT. No cloud, no temp files."""

def redact_phi(text: str) -> Tuple[str, List[str], str]:
    """
    Returns:
        redacted_text: str       — PHI replaced with [REDACTED_*] tokens
        detected_phi: List[str]  — list of detected PHI categories (e.g. ["REDACTED_PHONE"])
        patient_token: str       — "ANON_" + first 12 chars of SHA-256 hash of original text
    """

def extract_entities(text: str) -> Dict[str, Any]:
    """
    Returns:
        {
          "diagnosed_conditions": List[str],   # e.g. ["Chronic Kidney Disease", "Hypertension"]
          "current_medications":  List[str],   # e.g. ["Ibuprofen 400mg", "Metoprolol"]
          "allergies":            List[str],   # e.g. ["Penicillin", "Sulfa"]
          "clinical_labs":        Dict[str, str],  # legacy: { "eGFR": "28 mL/min/1.73m2" }
          "biomarkers":           Dict[str, Dict]  # rich: { "eGFR": { "value": 28.0, "unit": "...", "status": "CRITICAL_LOW" } }
        }
    """

def extract_lab_biomarkers(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses numeric lab values. Returns dict of biomarker objects.
    Supported keys: "eGFR", "Creatinine", "Potassium", "INR", "Platelets", "BloodPressure"
    Each value shape:
        { "value": float, "unit": str, "display": str, "status": str }
    Status values:
        eGFR:       "CRITICAL_LOW" (<30), "WARNING_LOW" (31-44), "NORMAL" (>=45)
        Creatinine: "HIGH" (>1.4),        "NORMAL"
        Potassium:  "CRITICAL_HIGH"(>5.0),"LOW"(<3.5),           "NORMAL"
        INR:        "CRITICAL_HIGH"(>3.5),"ELEVATED"(>3.0),      "NORMAL"
        Platelets:  "CRITICAL_LOW" (<50k),"LOW"(<100k),           "NORMAL"
    """
```

### 3.2 PHI Patterns to Redact (18 HIPAA Safe Harbor Identifiers)

Your AI agent should use these exact regex patterns and replacement tokens:

```python
PHI_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b",                                           "[REDACTED_SSN]"),
    (r"\b\d{9,12}\b",                                                     "[REDACTED_NATIONAL_ID]"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",        "[REDACTED_PHONE]"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",           "[REDACTED_EMAIL]"),
    (r"(?i)\b(?:MRN|MR#|Record\s*#?|Patient\s*ID|Acct\s*#?)\s*[:#]?\s*[A-Z0-9-]{4,15}\b", "[REDACTED_MRN]"),
    (r"(?i)\b(?:DOB|Date of Birth|Born)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",       "[REDACTED_DOB]"),
    (r"\b\d{5}(?:-\d{4})?\b",                                            "[REDACTED_ZIP]"),
    (r"(?i)\b\d{1,5}\s+[A-Za-z0-9\s.,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way)\b", "[REDACTED_ADDRESS]"),
    (r"(?i)\b(?:Dr\.|Doctor|Physician|Patient|Pt\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", "[REDACTED_NAME]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b",                                     "[REDACTED_IP]"),
]
```

### 3.3 What the Backend Actually Calls (Exact Import Path)

```python
# This is in backend/orchestrator.py — do not change this import
from ingestion.pipeline import process_file
result = process_file(file_bytes, filename)   # returns str
```

And for the extended review engine:
```python
from ingestion.pipeline import extract_entities
entities = extract_entities(redacted_text)
# entities["biomarkers"] feeds the lab threshold safety layer
```

### 3.4 Validation Rules Person B Must Enforce

```python
# Raise ValueError (not HTTPException — backend handles HTTP wrapping) if:
if not raw_text or len(raw_text.strip()) < 10:
    raise ValueError("Uploaded document contains no readable text.")
if len(raw_text) > 500_000:  # 500KB character limit
    raise ValueError("Document exceeds maximum permitted size.")
# Never write to disk. Use BytesIO for PDF parsing. No temp files.
# Never make network calls of any kind.
```

### 3.5 Test Your Work

Run this to confirm your functions return the right shapes:
```bash
python -m backend.benchmarks
```
All 5 scenarios should show `✅ PASS`. If any show `❌ FAIL`, fix Person B's pipeline before Day 5.

---

## 4. Person C — What Your AI Agent Needs to Build / Verify

> **Folder:** `/ai_engine/` only. Do not touch `/backend/` or `/ingestion/`.

### 4.1 Functions That Must Exist in `ai_engine/engine.py`

```python
# ── MUST EXPORT ────────────────────────────────────────────────

def analyze(redacted_text: str) -> dict:
    """
    Frozen contract function — shape is locked, see Section 2.
    Calls extract_entities() from ingestion.pipeline, then evaluate_full_safety().
    Never invents a flag from the LLM alone.
    """

def evaluate_full_safety(
    proposed_med: str,
    conditions: List[str],
    medications: List[str],
    allergies: List[str],
    labs: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """
    Full 7-layer clinical safety evaluation.
    Returns a TUPLE (not a dict) — exact shape:
        overall_status:           str            — "CRITICAL", "WARNING", or "SAFE"
        alerts:                   List[dict]     — see alert schema below
        canonical_drug:           str            — generic molecule name (e.g. "ibuprofen")
        recommended_alternatives: List[dict]     — safe formulary substitutes
    """
```

### 4.2 Alert Object Schema

Every item in the `alerts` list must have this exact shape. The backend reads these field names directly.

```python
alert = {
    "severity":           str,   # "CRITICAL" | "WARNING"
    "interaction_type":   str,   # "DRUG_DISEASE" | "DRUG_DRUG" | "ALLERGY" | "LAB_THRESHOLD" | "POLYPHARMACY"
    "conflicting_factor": str,   # human-readable: "Diagnosed Condition: Chronic Kidney Disease"
    "clinical_mechanism": str,   # detailed explanation sent to the LLM for elaboration
    "recommendation":     str,   # what the doctor should do instead
}
```

### 4.3 Recommended Alternative Object Schema

```python
alternative = {
    "alternative_drug":  str,   # e.g. "Acetaminophen"
    "dosage_guide":      str,   # e.g. "500mg PO Q6H (max 2g/day in CKD)"
    "rationale":         str,   # why it's safer
    "target_indication": str,   # the condition it treats
}
```

### 4.4 The Zero-Hallucination Rule (Critical for Judges)

```python
# ✅ CORRECT — LLM only elaborates on what the deterministic layer already found
if overall_status in ("CRITICAL", "WARNING") and alerts:
    from backend.ai_bridge import ai_bridge
    explanation = ai_bridge.get_clinical_explanation(
        drug=canonical_drug,
        condition=alerts[0]["conflicting_factor"],
        mechanism=alerts[0]["clinical_mechanism"]
    )
    # Only use LLM output to enrich the reason string, never to set flagged=True

# ❌ WRONG — Never do this
if llm_says_dangerous:
    flagged = True   # This is a hallucination risk, forbidden by design
```

### 4.5 The 7 Safety Check Layers (in order)

Person C's `evaluate_full_safety()` must run these checks in this exact order. Each sub-module already exists in `/ai_engine/`:

```python
# 1. Brand → Generic Normalization
from ai_engine.pharmacology import PharmacologyKnowledge
canonical_drug, detected_brand = PharmacologyKnowledge.normalize_drug_name(proposed_med)

# 2. Allergy Cross-Reactivity
allergy_alerts = PharmacologyKnowledge.check_allergies(proposed_med, allergies)

# 3. Quantitative Lab Biomarker Guardrails (only if labs dict is provided)
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
lab_alerts = LabBiomarkerEvaluator.evaluate_drug_against_labs(canonical_drug, detected_brand, labs)

# 4. Polypharmacy Syndromes (Triple Whammy, QTc, Serotonin)
from ai_engine.polypharmacy import PolypharmacyEngine
poly_alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed_med, medications)

# 5. Drug <-> Disease (SQLite query on contraindications_disease table)
# 6. Drug <-> Drug   (SQLite query on contraindications_drug table)

# 7. Safe Alternatives (only if status is CRITICAL or WARNING)
from ai_engine.alternatives import SafeAlternativeRecommender
recommended_alternatives = SafeAlternativeRecommender.get_safe_alternatives(
    proposed_med, conditions, allergies
)
```

### 4.6 SQLite Tables Person C Queries

```sql
-- Drug <-> Disease rules
SELECT condition_name, severity, mechanism, recommendation
FROM contraindications_disease
WHERE (? LIKE '%' || drug_name || '%' OR drug_name = ?)
  AND (? LIKE '%' || condition_name || '%' OR condition_name LIKE '%' || ? || '%')
-- params: (search_drug, search_drug, cond_clean, cond_clean)

-- Drug <-> Drug interactions
SELECT drug_a, drug_b, severity, mechanism, recommendation
FROM contraindications_drug
WHERE (drug_a = ? AND (? LIKE '%' || drug_b || '%' OR drug_b = ?))
   OR (drug_b = ? AND (? LIKE '%' || drug_a || '%' OR drug_a = ?))
-- params: (search_drug, med_search, med_search, search_drug, med_search, med_search)
```

### 4.7 DB Path Convention (Always Use This)

```python
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")
```

### 4.8 What the Backend Calls (Exact Import Paths)

```python
# orchestrator.py calls this for /analyze endpoint:
from ai_engine.engine import analyze
result = analyze(redacted_text)  # returns dict matching contract

# orchestrator.py calls this for /api/review endpoint:
from ai_engine.engine import evaluate_full_safety
status, alerts, canonical, alternatives = evaluate_full_safety(
    proposed_med, conditions, medications, allergies, labs
)
```

### 4.9 The 5 Test Scenarios Person C Must Pass

```python
# Run: python -m backend.benchmarks
SCENARIOS = [
    # 1. CKD Stage 3 + Ibuprofen → must flag CRITICAL
    # 2. Asthma + Propranolol → must flag CRITICAL
    # 3. Warfarin + Aspirin → must flag CRITICAL
    # 4. Penicillin Allergy + Amoxicillin → must flag CRITICAL
    # 5. Safe case (e.g. Lisinopril for hypertension, no conflicts) → must return SAFE
]
```

---

## 5. Person D — What Your AI Agent Needs to Build

> **Folder:** `/frontend/` only. Plain HTML + CSS + JS — no React, no build step.  
> **Base URL:** All API calls go to `http://127.0.0.1:8000`

### 5.1 UI Screens Required

```
Screen 1: Login / Demo Mode
  → POST /api/auth/switch-demo  (picks a demo doctor, no password)
  → Stores access_token in localStorage

Screen 2: Patient Selection
  → GET /api/patients            (list all demo patients)
  → GET /api/patients/{id}       (load full medical record when selected)

Screen 3: Drug Review (Main Screen)
  → POST /api/review             (full clinical check with auth token)
  → Renders: CRITICAL badge or SAFE badge
  → Renders: alerts list
  → Renders: recommended_alternatives

Screen 4: Audit Log
  → GET /api/audit-logs?limit=15
  → GET /api/audit-verify        (show "Hash Chain: VERIFIED" or "TAMPERED")
  → GET /api/audit-export?format=csv  (download button)
```

### 5.2 Authentication Flow for AI Agent

```javascript
// Step 1: Switch to a demo doctor (no password needed for hackathon)
const res = await fetch('http://127.0.0.1:8000/api/auth/switch-demo', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ practitioner_id: 'PRAC-101' })  // or PRAC-102, PRAC-103
});
const data = await res.json();
localStorage.setItem('medivault_token', data.access_token);
// data.practitioner has: full_name, hospital_name, department, role

// Step 2: Use the token on authenticated calls
const token = localStorage.getItem('medivault_token');
const reviewRes = await fetch('http://127.0.0.1:8000/api/review', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`  // ← add this header
  },
  body: JSON.stringify({
    patient_id: 'PT-101',
    proposed_medication: 'Ibuprofen',
    dosage: '400mg PO TID'
  })
});
```

### 5.3 Full `/api/review` Response Shape (What to Render)

```javascript
// POST /api/review response:
{
  "overall_status": "CRITICAL",        // → show red badge
  "alerts": [
    {
      "severity": "CRITICAL",
      "interaction_type": "DRUG_DISEASE",
      "conflicting_factor": "Diagnosed Condition: Chronic Kidney Disease",
      "clinical_mechanism": "NSAIDs inhibit prostaglandin synthesis, reducing renal perfusion...",
      "recommendation": "Avoid NSAIDs. Use acetaminophen for analgesia."
    }
  ],
  "canonical_drug": "ibuprofen",
  "patient_hash": "sha256:ANON_4A9B...",
  "recommended_alternatives": [
    {
      "alternative_drug": "Acetaminophen",
      "dosage_guide": "500mg PO Q6H (max 2g/day in CKD)",
      "rationale": "Safe analgesic in CKD; does not affect renal prostaglandins",
      "target_indication": "Pain Management"
    }
  ],
  "execution_time_ms": 42.7,
  "zero_cloud_enforced": true,
  "practitioner": {
    "full_name": "Dr. Gregory House, MD",
    "hospital_name": "Princeton Plainsboro Teaching Hospital"
  },
  "timestamp": "2026-09-24T15:00:00Z"
}
```

### 5.4 Trust Badge Strip (Top of Page — Always Visible)

```javascript
// Call on page load:
const health = await fetch('http://127.0.0.1:8000/api/health').then(r => r.json());
const guard  = await fetch('http://127.0.0.1:8000/api/network-guard').then(r => r.json());
const ai     = await fetch('http://127.0.0.1:8000/api/ai-status').then(r => r.json());

// Render based on:
// health.zero_cloud_mode === true  →  🟢 Zero-Cloud Mode
// guard.air_gap_verified === true  →  🛡️ Air-Gapped
// ai.status === "ONLINE"           →  🤖 AI: Ready
// ai.status !== "ONLINE"           →  🔴 AI: Offline (still works — deterministic fallback)
```

### 5.5 File Upload Flow

```javascript
// 1. Upload the file
const formData = new FormData();
formData.append('file', fileInput.files[0]);
const uploadRes = await fetch('http://127.0.0.1:8000/upload-record', {
  method: 'POST',
  body: formData
});
const { redacted_text } = await uploadRes.json();
// Show redacted_text to the doctor (proves PII is gone)

// 2. Run analysis on the redacted text (simple contract endpoint)
const analyzeRes = await fetch('http://127.0.0.1:8000/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ redacted_text })
});
const result = await analyzeRes.json();
// result = { flagged, reason, drug, severity }
```

### 5.6 Demo Doctors (Pre-Seeded — Use for 1-Click Demo)

```javascript
// GET /api/auth/practitioners returns:
[
  { "practitioner_id": "PRAC-101", "full_name": "Dr. Sarah Chen, MD", "hospital_name": "...", "department": "Cardiology" },
  { "practitioner_id": "PRAC-102", "full_name": "Dr. Arjun Mehta, MD", "hospital_name": "...", "department": "Nephrology" },
  { "practitioner_id": "PRAC-103", "full_name": "Dr. Gregory House, MD", "hospital_name": "...", "department": "Diagnostics" }
]
```

### 5.7 Demo Patients (Pre-Seeded — Use for Patient Selector)

```javascript
// GET /api/patients returns patients. Use GET /api/patients/{id} for full record.
// Patient IDs: "PT-101", "PT-102", "PT-103"
// PT-101: CKD Stage 3, on Metoprolol — critical if Ibuprofen proposed
// PT-102: Asthma, on Salbutamol — critical if Propranolol proposed
// PT-103: Atrial Fibrillation, on Warfarin — critical if Aspirin proposed
```

### 5.8 Audit Log Display

```javascript
// GET /api/audit-logs?limit=15
// Returns: { "audit_trail": [ { timestamp, event_id, proposed_medication, overall_status, practitioner_name, audit_hash, ... } ] }

// GET /api/audit-verify
// Returns: { "integrity": "VERIFIED" | "TAMPERED", "total_entries": int, "chain_valid": bool }

// CSV download button:
// <a href="http://127.0.0.1:8000/api/audit-export?format=csv" download>Download Compliance Report</a>
```

---

## 6. Database Schema — What Everyone Needs to Know

The SQLite database at `database/medivault.db` auto-creates from `database/schema.sql` on first server start. **Never manually create or alter tables** — they are already there.

### Key Tables

```sql
-- Drug-Disease rules (Person C reads this)
contraindications_disease (drug_name, condition_name, severity, mechanism, recommendation)

-- Drug-Drug interactions (Person C reads this)
contraindications_drug (drug_a, drug_b, severity, mechanism, recommendation)

-- Safe alternatives (Person C reads this)
safe_alternatives (blocked_drug, suggested_alternative, clinical_condition, dosage_guide, clinical_rationale)

-- Demo patients (Person D and Person A read this)
patients (patient_id, patient_name, age, gender)
patient_conditions (patient_id, condition_name, icd10_code)
patient_medications (patient_id, medication_name, dosage, frequency)
patient_allergies (patient_id, allergen, reaction)
patient_labs (patient_id, biomarker_name, value, unit)

-- Auth (Person A owns, Person D reads via API)
hospitals (hospital_id, hospital_name, domain_whitelist, department)
practitioners (practitioner_id, hospital_id, full_name, email, password_hash, role, email_verified)

-- Audit trail (auto-written by /api/review)
audit_logs (timestamp, event_id, practitioner_id, proposed_medication, overall_status, audit_hash)
```

---

## 7. Running the Project

### Start the Server
```bash
# From the workspace root (not from /backend/):
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# OR use the batch file:
run_demo.bat
```

### Verify Everything Works
```bash
# Health check:
curl http://127.0.0.1:8000/api/health

# Run 5-scenario benchmark (all should PASS):
python -m backend.benchmarks

# Open Swagger docs:
# http://127.0.0.1:8000/docs
```

### Install Dependencies
```bash
pip install fastapi uvicorn[standard] pypdf pydantic requests
```

> **Ollama (for AI explanations):** Install from https://ollama.ai, then run:
> ```bash
> ollama pull llama3.2:3b
> ollama serve
> ```
> The system works fully without Ollama — the deterministic layer is the gatekeeper. Ollama only adds richer text explanations.

---

## 8. Hard Rules for Every AI Agent (Non-Negotiable)

These override any "smart" suggestion the AI agent might make.

| Rule | Reason |
|------|--------|
| ❌ Never add `import requests` to call an external URL | Zero-cloud — all network calls are blocked by design |
| ❌ Never add `openai`, `anthropic`, `google-generativeai` or any cloud SDK | HIPAA violation — patient data cannot leave the machine |
| ❌ Never rename a field in the contract JSON shapes | Frontend + backend both depend on exact field names |
| ❌ Never edit files outside your folder | Each folder has one owner; cross-folder edits break team parallelism |
| ❌ Never use `print()` for errors | Use `raise ValueError("clear message")` — backend wraps these into HTTP responses |
| ❌ Never write real patient data in tests or fixtures | Only synthetic records; using real data is a HIPAA violation |
| ✅ Always validate inputs before processing | Raise `ValueError` with a clear message if input is empty, too large, or unsupported |
| ✅ Always use `sqlite3.connect(DB_PATH, timeout=5.0)` | WAL mode is enabled; use the timeout to avoid lock errors |
| ✅ Always use `conn.row_factory = sqlite3.Row` | Enables dict-style row access (`row["column_name"]`) |

---

## 9. Integration Checklist (Day 5 & Hackathon Day)

Use this to confirm everything is wired before the demo.

### Person B ✅
- [ ] `python -m backend.benchmarks` → all 5 PASS
- [ ] `process_file(b"...", "test.pdf")` returns a string with `[REDACTED_*]` tokens
- [ ] `extract_entities("CKD, eGFR 28, Ibuprofen")` returns `diagnosed_conditions: ["Chronic Kidney Disease"]`
- [ ] No `requests`, no cloud imports anywhere in `/ingestion/`

### Person C ✅
- [ ] `from ai_engine.engine import analyze, evaluate_full_safety` works with no errors
- [ ] `analyze("CKD... Ibuprofen...")` returns `{"flagged": true, "reason": "...", "drug": "Ibuprofen", "severity": "CRITICAL"}`
- [ ] `evaluate_full_safety("Ibuprofen", ["Chronic Kidney Disease"], [], [])` returns a 4-tuple
- [ ] `python -m backend.benchmarks` → all 5 PASS
- [ ] LLM explanations work if Ollama is running, gracefully skip if it's not

### Person D ✅
- [ ] `POST /api/auth/switch-demo` with `{ "practitioner_id": "PRAC-101" }` logs in a doctor
- [ ] `GET /api/patients` populates the patient dropdown
- [ ] `POST /api/review` with token shows CRITICAL badge for PT-101 + Ibuprofen
- [ ] Trust badge strip (Zero-Cloud / Air-Gapped / AI) visible at top of page
- [ ] Audit log tab shows last 15 reviews + hash chain status
- [ ] Page works when opened at `http://127.0.0.1:8000` (backend serves `frontend/index.html`)

---

## 10. AI Agent Prompt Templates

Copy these prompts when starting a new AI agent session for each person's work.

### For Person B's Agent
```
You are coding Person B's work on MediVault Local, a zero-cloud offline clinical system.
Your folder: /ingestion/pipeline.py ONLY.
Do not touch /backend/, /ai_engine/, or /frontend/.

The backend already calls your functions at these exact import paths:
  from ingestion.pipeline import process_file   # returns str (redacted text)
  from ingestion.pipeline import extract_entities  # returns dict with keys: diagnosed_conditions, current_medications, allergies, clinical_labs, biomarkers

Rules:
- No network calls ever
- No temp file writes — use BytesIO for PDF parsing
- Raise ValueError (not HTTPException) for bad inputs
- Only redact PHI tokens, never clinical values like drug names or conditions

[Paste full Section 3 of this document here]
```

### For Person C's Agent
```
You are coding Person C's work on MediVault Local, a zero-cloud offline clinical system.
Your folder: /ai_engine/ ONLY.
Do not touch /backend/, /ingestion/, or /frontend/.

The backend calls your functions at these exact import paths:
  from ai_engine.engine import analyze         # contract: takes str, returns dict
  from ai_engine.engine import evaluate_full_safety  # takes 5 args, returns 4-tuple

Critical rule: The LLM (Ollama/llama3.2:3b) NEVER introduces a flag. The deterministic layer (SQLite + lexicon + polypharmacy) is the sole gatekeeper. The LLM only elaborates on an already-found flag.

[Paste full Section 4 of this document here]
```

### For Person D's Agent
```
You are coding Person D's work on MediVault Local, a zero-cloud offline clinical system.
Your folder: /frontend/ ONLY. Plain HTML + CSS + JS. No React, no build step.
Do not touch /backend/, /ingestion/, or /ai_engine/.

The backend runs at http://127.0.0.1:8000. All API calls go there.
The backend serves your frontend at http://127.0.0.1:8000 — it serves frontend/index.html as the root page.

[Paste full Section 5 of this document here]
[Also paste the full endpoint table from Section 11 of this document]
```

---

## 11. Full API Endpoint Reference

| Method | Endpoint | Body | Returns | Notes |
|--------|----------|------|---------|-------|
| `GET`  | `/api/health` | — | `{ status, zero_cloud_mode, hipaa_safe_harbor }` | Poll on page load |
| `GET`  | `/api/network-guard` | — | `{ air_gap_verified, zero_cloud_enforced }` | Trust badge |
| `GET`  | `/api/ai-status` | — | `{ status: "ONLINE"|"OFFLINE" }` | Ollama check |
| `POST` | `/upload-record` | `file` (multipart) | `{ redacted_text }` | Contract endpoint |
| `POST` | `/analyze` | `{ redacted_text }` | `{ flagged, reason, drug, severity }` | Contract endpoint |
| `GET`  | `/api/patients` | — | `{ patients: [...] }` | Dropdown data |
| `GET`  | `/api/patients/{id}` | — | `{ patient, conditions, medications, allergies }` | IDs: PT-101,102,103 |
| `POST` | `/api/redact` | `{ text }` | `{ redacted_text, phi_detected, patient_token }` | Utility |
| `POST` | `/api/extract` | `{ text }` | `{ diagnosed_conditions, current_medications, allergies, biomarkers }` | Utility |
| `GET`  | `/api/auth/hospitals` | — | `{ hospitals: [...] }` | For registration form |
| `GET`  | `/api/auth/practitioners` | — | `{ practitioners: [...] }` | Demo doctors list |
| `POST` | `/api/auth/register` | `{ full_name, email, hospital_id, medical_license, password }` | `{ status, simulated_code }` | Gets OTP |
| `POST` | `/api/auth/verify-email` | `{ email, verification_code }` | `{ access_token, practitioner }` | OTP verify |
| `POST` | `/api/auth/resend-code` | `{ email }` | `{ simulated_code }` | New OTP |
| `POST` | `/api/auth/login` | `{ email, password }` | `{ access_token, practitioner }` | Full login |
| `POST` | `/api/auth/switch-demo` | `{ practitioner_id }` | `{ access_token, practitioner }` | **Use this for demo** |
| `POST` | `/api/auth/logout` | — | `{ status }` | Clears cookie |
| `GET`  | `/api/auth/me` | header: `Authorization: Bearer <token>` | `{ practitioner }` | Current user |
| `POST` | `/api/review` | `{ patient_id, proposed_medication, dosage }` + auth header | Full clinical report | **Main engine** |
| `GET`  | `/api/audit-logs` | `?limit=15` | `{ audit_trail: [...] }` | Audit panel |
| `GET`  | `/api/audit-verify` | — | `{ integrity, chain_valid, total_entries }` | Hash check |
| `GET`  | `/api/audit-export` | `?format=json` or `?format=csv` | File download | Compliance button |

---

*Person A — MediVault Local, ASYNC'26, Track 1: Sovereign AI*  
*Backend v1.3.0 — 24 September 2026*
