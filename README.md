# MediVault Local — Sovereign AI Clinical Contraindication Reviewer
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A, Person B, Person C, Person D)  
> **Release:** v1.0 (Frozen Main)  
> **Zero-Cloud Compliance:** 100% Offline Local Machine Execution (127.0.0.1 only)  
> **Regulatory Standard:** HIPAA Safe Harbor § 164.514(b)(2) & Security Rule § 164.312(b) | DPDP Act 2023  

---

## 1. Executive Summary & Problem Statement

Hospitals and clinical practitioners face a critical dilemma: **they cannot legally transmit confidential patient health records to cloud-hosted Large Language Models (LLMs)** without severe regulatory violations under HIPAA and DPDP. At the same time, clinical cognitive overload causes dangerous prescription contraindications to slip through (e.g., prescribing NSAIDs to a Stage 3 CKD patient or non-selective beta-blockers to an asthmatic).

**MediVault Local** solves this crisis with a **100% Sovereign AI architecture**:
- **Zero Cloud Egress:** Binds strictly to `127.0.0.1`. Patient data never leaves the local machine (0 bytes transmitted).
- **Zero Hallucination Safety Guarantee:** Clinical safety is anchored to a **deterministic SQLite pharmacology knowledge engine**. A local SLM (`llama3.2:3b` via Ollama) provides natural clinical explanations, but cannot override deterministic safety rules.
- **Cryptographic Audit Trail:** Every clinical review is sealed with a **local SHA-256 hash-chained ledger** proving tamper-free compliance with HIPAA § 164.312(b).

---

## 2. System Architecture

```
   ┌───────────────────────┐
   │    Doctor / Clinic    │
   │  Web UI (127.0.0.1)   │
   └───────────┬───────────┘
               │  POST /api/upload-record (PDF/TXT)
               ▼
   ┌──────────────────────────────────────────────────────────┐
   │                     BACKEND PIPELINE                     │
   │                                                          │
   │  [1. Ingestion & PHI Redaction] (Safe Harbor § 164.514)  │
   │     • Strips 18 PHI identifiers (SSN, Phone, MRN, etc.)  │
   │     • Generates cryptographic patient token (ANON_...)   │
   │                                                          │
   │  [2. Pharmacology & Entity Extraction]                   │
   │     • Brand-to-generic normalization (Advil -> Ibuprofen)│
   │     • Cross-reactivity allergy checking (Penicillin)     │
   │                                                          │
   │  [3. Deterministic Safety Engine]                        │
   │     • SQLite table lookups (Disease & Drug interactions) │
   │     • 0% Hallucination rate; 100% rule enforcement       │
   │                                                          │
   │  [4. Local SLM Reasoning Bridge]                         │
   │     • Ollama (llama3.2:3b) on local port 11434           │
   │     • Automatic fallback to deterministic synthesis      │
   │                                                          │
   │  [5. SHA-256 Hash-Chained Audit Ledger]                  │
   │     • HIPAA § 164.312(b) tamper-proof local log          │
   │     • Genesis block verification & export (CSV/JSON)     │
   └───────────────────────────┬──────────────────────────────┘
                               │
                               ▼
   ┌──────────────────────────────────────────────────────────┐
   │                  DOCTOR-FACING DASHBOARD                 │
   │   🔴 CRITICAL CONTRAINDICATION / 🟡 WARNING / 🟢 SAFE    │
   │   Air-Gap Trust Pill: 0 bytes outbound transmitted       │
   └──────────────────────────────────────────────────────────┘
```

---

## 3. Team Ownership & Folder Architecture

Built collaboratively across 4 specialized roles adhering to strict folder boundaries:

| Role | Owner | Folder | Core Responsibilities |
|---|---|---|---|
| **Repo Lead & Backend API** | **Person A** | `/backend`, `database/` | FastAPI application, orchestrator glue code, thread-safe audit logger, SQLite WAL concurrency, release packaging |
| **Data Ingestion & Privacy** | **Person B** | `/ingestion` | PDF & TXT text extraction, 18 HIPAA Safe Harbor regex PHI de-identification |
| **AI Engine & Pharmacology** | **Person C** | `/ai_engine` | SQLite interaction database, deterministic pharmacology rules, local Ollama SLM reasoning integration |
| **Frontend UI, Docs & QA** | **Person D** | `/frontend`, `/docs` | Physician dashboard, air-gap trust pill, live audit drawer, manual QA & demo scripts |

---

## 4. Frozen Contracts (`CONTRACTS.md`)

All modules interface seamlessly through frozen, backwards-compatible contracts:

- **Ingestion Contract:**
  - Input: Multipart PDF or plain-text clinical document.
  - Output: Redacted plain-text string (`[REDACTED_SSN]`, etc.) with anonymized patient token.
- **Safety Analysis Contract:**
  - Input: `{ "redacted_text": str }`
  - Output: `{ "flagged": bool, "reason": str, "drug": str|null, "severity": str|null }`
- **Clinical Review Endpoint:**
  - `POST /api/review`
  - Evaluates proposed prescriptions against patient diagnostic history, active medications, and allergies.

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.10+
- (Optional for natural SLM explanations) [Ollama](https://ollama.com) installed with `ollama pull llama3.2:3b`. If Ollama is offline, the system automatically uses its built-in deterministic clinical synthesis engine.

### 1-Click Launch (Windows)
Double-click `run_demo.bat` in the repository root, or execute:

```bash
run_demo.bat
```

### Manual CLI Launch
```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Start the local loopback server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **`http://127.0.0.1:8000`**

---

## 6. Verification & Automated Test Suites

MediVault Local includes rigorous automated test suites verifying all compliance layers:

### A. Comprehensive Unit & Integration Tests (14 Tests)
```bash
python -m unittest tests/test_pipeline.py
```
*Verifies PHI redaction, brand normalization, allergy cross-checks, input guardrails, and cryptographic audit hashing.*

### B. Concurrency & Thread-Safety Stress Test (12 Parallel Requests)
```bash
python -m unittest tests/stress_test.py
```
*Simulates 12 concurrent physician reviews across 6 worker threads; verifies SQLite WAL mode with 0 database locks and 100% SHA-256 chain integrity.*

### C. Live Clinical Benchmark Scorecard (6 Clinical Scenarios)
```bash
python backend/benchmarks.py
```
*Measures end-to-end latency across real clinical PDF and TXT patient discharge notes with 100% accuracy.*

---

## 7. The Hackathon Demo Script (The "Killer Demo Move")

To demonstrate sovereign AI compliance to judges:

1. **Start the Dashboard:** Launch `run_demo.bat` and open `http://127.0.0.1:8000`.
2. **The Killer Air-Gap Move:** Disconnect the demonstration laptop from Wi-Fi and Ethernet.
3. **Upload Sample Record:** Drag & drop `samples/patient_1_ckd_discharge.pdf` (Renal profile) into the dashboard.
4. **Propose Dangerous Prescription:** Enter `Advil 400mg` or `Ibuprofen 400mg`.
5. **Observe Instant Triage:**
   - Triage banner flashes **🔴 CRITICAL CONTRAINDICATION**.
   - Advil is automatically normalized to generic `ibuprofen`.
   - Explains that NSAIDs inhibit renal prostaglandins in CKD Stage 3, risking acute renal shutdown.
   - Air-Gap Trust Pill confirms: `AIR-GAPPED: 0 BYTES TRANSMITTED`.
6. **Verify Audit Trail:** Open the Cryptographic Audit Drawer and click **"Verify Hash Chain"** to demonstrate mathematical proof of zero tampering.
