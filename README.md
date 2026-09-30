# MediVault Local — Sovereign AI Clinical Contraindication Reviewer
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A: Rishikgowda SM, Person B: Rakshith DA, Person C: Kushal M, Person D: Sujan MB)  
> **Release:** v1.3 (Enterprise Sovereign Clinical Suite)  
> **Zero-Cloud Compliance:** 100% Offline Local Machine Execution (`127.0.0.1` loopback only)  
> **Regulatory Standard:** HIPAA Safe Harbor § 164.514(b)(2) & Security Rule § 164.312(b) | DPDP Act 2023  
> **Test Coverage:** 117/117 Automated Tests Passing across 17 Clinical Test Modules  

---

## 1. Executive Summary & Problem Statement.

Hospitals and clinical practitioners face a critical dilemma: **they cannot legally transmit confidential patient health records to cloud-hosted Large Language Models (LLMs)** without severe regulatory violations under HIPAA and the India DPDP Act. At the same time, clinical cognitive overload causes dangerous prescription contraindications to slip through (e.g., prescribing NSAIDs to a Stage 3 CKD patient, triggering Triple Whammy acute kidney injury, or ordering non-selective beta-blockers for an asthmatic).

**MediVault Local** solves this crisis with a **100% Sovereign AI architecture**:
- **Zero Cloud Egress:** Binds strictly to `127.0.0.1`. Patient data never leaves the local machine (0 bytes transmitted, verified by automated network assertion tests).
- **Zero Hallucination Safety Guarantee:** Clinical safety is anchored to a **deterministic SQLite pharmacology knowledge engine**. A local SLM (`llama3.2:3b` via Ollama) provides natural clinical explanations, but cannot override deterministic safety rules.
- **Cryptographic Audit Trail:** Every clinical review is sealed with a **local SHA-256 hash-chained Merkle ledger** proving tamper-free compliance with HIPAA § 164.312(b).
- **End-to-End Interoperability:** On-device OCR (RapidOCR), FHIR R4 Bundle export, optical air-gap SVG QR codes, and HL7 CDS Hooks.

---

## 2. System Architecture.

```
   ┌──────────────────────────────────────────────────────────┐
   │             DOCTOR WORKSTATION / CLINIC UI               │
   │               Web Interface (127.0.0.1:8000)             │
   └───────────┬──────────────────────────────────┬───────────┘
               │ Multi-Med Intake / OCR / FHIR    │ Air-Gap Optical QR
               ▼                                  ▼
   ┌──────────────────────────────────────────────────────────┐
   │                     BACKEND PIPELINE                     │
   │                                                          │
   │  [1. Ingestion & PHI Redaction] (Safe Harbor § 164.514)  │
   │     • Strips 18 PHI identifiers (SSN, Phone, MRN, etc.)  │
   │     • Generates cryptographic patient token (ANON_...)   │
   │     • On-device RapidOCR for scanned paper slips         │
   │                                                          │
   │  [2. Pharmacology & Entity Extraction]                   │
   │     • Multi-medicine prescription bundle parsing         │
   │     • Brand-to-generic normalization (Advil -> Ibuprofen)│
   │     • Cross-reactivity allergy checking (Penicillins)    │
   │                                                          │
   │  [3. Deterministic Safety Engine]                        │
   │     • Drug-Disease & Drug-Drug contraindication matrices │
   │     • Polypharmacy: Triple Whammy, QTc, Serotonin Syndr. │
   │     • AGS Beers 2023 Criteria & Cockcroft-Gault CrCl     │
   │     • Quantitative lab biomarker thresholds (eGFR, K+, INR)
   │                                                          │
   │  [4. Pharmacokinetic (PK) Accumulation Simulator]        │
   │     • Rowland & Tozer renal clearance dynamics           │
   │     • 72h plasma concentration curves & toxic ceilings   │
   │                                                          │
   │  [5. Local SLM Reasoning Bridge]                         │
   │     • Ollama (llama3.2:3b) on local port 11434           │
   │     • Automatic fallback to deterministic synthesis      │
   │                                                          │
   │  [6. SHA-256 Hash-Chained Audit Ledger]                  │
   │     • HIPAA § 164.312(b) tamper-proof local log          │
   │     • Merkle chain verification & export (CSV / JSON)    │
   └───────────────────────────┬──────────────────────────────┘
                               │
                               ▼
   ┌──────────────────────────────────────────────────────────┐
   │                  DOCTOR-FACING DASHBOARD                 │
   │   🔴 CRITICAL CONTRAINDICATION / 🟡 WARNING / 🟢 SAFE    │
   │   • Clinical Hazard Index & Patient Vulnerability Gauge  │
   │   • Dynamic Hemodynamic & eGFR Trajectory Charts         │
   │   • Printable Hospital Clearance Certificate             │
   │   • Interactive Judge Demo Crisis Runner [Ctrl+6]        │
   └──────────────────────────────────────────────────────────┘
```

---

## 3. Team Ownership & Folder Architecture

Built collaboratively across 4 specialized roles adhering strictly to folder boundaries defined in [`AGENTS.md`](file:///c:/Users/Rishikgowda%20S%20M/Medivault%20local/Medivalt_local/Agents.md):

| Role | Team Member | Folder | Core Responsibilities |
|---|---|---|---|
| **Repo Lead & Backend API** | **Person A: Rishikgowda SM** | `/backend`, `database/` | FastAPI application, orchestrator glue code, thread-safe audit logger, SQLite WAL concurrency, release packaging |
| **Data Ingestion & Privacy** | **Person B: Rakshith DA** | `/ingestion` | PDF & TXT text extraction, RapidOCR scanned image processing, 18 HIPAA Safe Harbor regex PHI de-identification |
| **AI Engine & Pharmacology** | **Person C: Kushal M** | `/ai_engine` | SQLite interaction database, deterministic pharmacology rules, polypharmacy cascades, PK simulator, Ollama SLM bridge |
| **Frontend UI, Docs & QA** | **Person D: Sujan MB** | `/frontend`, `/docs` | Physician dashboard, judge demo modal, live audit drawer, patient portal, accessibility, manual QA & demo scripts |

---

## 4. Frozen Contracts ([`CONTRACTS.md`](file:///c:/Users/Rishikgowda%20S%20M/Medivault%20local/Medivalt_local/Contracts.md))

All modules interface seamlessly through frozen, backwards-compatible contracts:

- **Ingestion Contract:**
  - Input: Multipart PDF, plain-text note, or scanned prescription image (PNG/JPG).
  - Output: Redacted plain-text string (`[REDACTED_SSN]`, etc.) with anonymized patient token and extracted clinical entities.
- **Safety Analysis Contract:**
  - Input: `{ "redacted_text": str }`
  - Output: `{ "flagged": bool, "reason": str, "drug": str|null, "severity": str|null }`
- **Clinical Review Endpoint:**
  - `POST /api/review`
  - Evaluates single or multi-drug prescription bundles against patient diagnostic history, active medications, quantitative biomarkers, and allergies.
  - Returns itemized alerts, polypharmacy hazards, PK simulation curves, and Clinical Hazard Index.

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

### 1-Click Test Suite (Windows)
Double-click `run_tests.bat` in the repository root to verify all 117 automated tests:

```bash
run_tests.bat
```

### Manual CLI Launch
```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Start the local loopback server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **`http://127.0.0.1:8000`**  
Patient-facing portal: **`http://127.0.0.1:8000/patient-portal`**

---

## 6. Verification & Automated Test Suites (117 Tests)

MediVault Local includes 117 automated test cases across 17 modules verifying all regulatory and clinical requirements:

```bash
python -m unittest discover -s tests -p "*.py" -v
```

| Test Module | Tests | What It Verifies |
|---|:---:|---|
| `test_pipeline.py` | 14 | 18 HIPAA Safe Harbor PHI redactions, brand normalization, frozen API contracts, zero-cloud egress assertion |
| `test_polypharmacy.py` | 5 | Lethal Triple Whammy (ACEi + Diuretic + NSAID), cumulative QTc prolongation, and Serotonin Syndrome |
| `test_prescription_bundle.py` | 5 | Multi-drug prescription order parsing, real-world discharge formats, safe care plans |
| `test_pk_model.py` | 10 | Rowland & Tozer renal clearance dynamics, 72h plasma accumulation curves, toxic ceilings |
| `test_hazard_index.py` | 8 | Clinical Hazard Index composite vulnerability scoring across organ stress, interactions, and age |
| `test_patient_portal.py` | 10 | Patient registration, PBKDF2 authentication, plain-English lab explanations, role isolation |
| `test_alternatives.py` | 4 | Formulary substitution (e.g. suggesting Linagliptin for Metformin in severe CKD) |
| `test_geriatric_renal.py` | 7 | AGS Beers 2023 criteria for elderly patients, Cockcroft-Gault CrCl calculations |
| `test_lab_biomarkers.py` | 7 | Quantitative lab cutoffs (eGFR < 30 lactic acidosis, K+ > 5.0 hyperkalemia, INR > 3.5 hemorrhage) |
| `test_offline_ocr.py` | 9 | Sovereign RapidOCR image text extraction, scanned PDF OCR fallback, corrupted image defense |
| `test_interoperability.py` | 7 | FHIR R4 Bundle parsing, HL7 v2 messages, and Base64+zlib optical QR decompression |
| `test_cds_hooks.py` | 4 | Official HL7 CDS Hooks medication-prescribe discovery, 1-click suggestion cards, FHIR bundles |
| `test_demo_scenarios.py` | 5 | Pre-configured judge crisis scenario executions and talking points |
| `test_certificate.py` | 2 | Hospital clearance certificate generation and cryptographic verification |
| `test_analytics.py` | 6 | Institutional epidemiological metrics, risk distribution, Chart.js time-series, CSV export |
| `test_auth.py` | 7 | PBKDF2 hashing (100k rounds), offline compact JWT, institutional domain whitelisting, demo doctor switcher |
| `stress_test.py` | 1 | 12 concurrent clinical reviews across 6 threads; verifies SQLite WAL mode with 0 locks and 100% chain integrity |

---

## 7. The Hackathon Demo Script (The "Killer Demo Move")

To demonstrate sovereign AI compliance to judges:

1. **Start the Dashboard:** Launch `run_demo.bat` and open `http://127.0.0.1:8000`.
2. **The Killer Air-Gap Move:** Disconnect the demonstration laptop from Wi-Fi and Ethernet. Show judges that the app runs 100% locally on `127.0.0.1`.
3. **Trigger Judge Demo Scenarios:** Press `Ctrl+6` (or click "Judge Challenge Suite") to open the interactive crisis runner:
   - **Scenario 1 [Press 1]: Acute Renal Collapse** — Stage 3 CKD patient prescribed Ketorolac; shows instant AKI cascade and PK accumulation curve crossing toxic ceiling.
   - **Scenario 2 [Press 2]: The Triple Whammy** — Hypertensive patient on Lisinopril + Furosemide ordered Naproxen; flags afferent/efferent hemodynamic collapse.
   - **Scenario 3 [Press 3]: Hidden Cross-Reactive Anaphylaxis** — Penicillin-allergic patient ordered Amoxicillin; demonstrates 1-click safe formulary swap to Ciprofloxacin.
   - **Scenario 4 [Press 4]: Anticoagulant Hemorrhage** — Warfarin patient with high INR ordered Aspirin; detects supra-therapeutic bleeding risk.
4. **Air-Gap Transfer:** Click **"Optical QR Transfer"** to show camera-to-screen air-gapped cryptographic record transfer without Bluetooth, Wi-Fi, or cable connection.
5. **Printable Certificate:** Click **"Clinical Clearance Certificate"** to view and print the official hospital record sealed with SHA-256 Merkle proof (HIPAA § 164.312(b)).
6. **Verify Audit Trail:** Open the Cryptographic Audit Drawer and click **"Verify Hash Chain"** to demonstrate mathematical proof of zero tampering.

### Keyboard Shortcuts
- `Ctrl + Enter` — Run safety review or de-identify clinical notes
- `Ctrl + 1` — Switch to CDSS Review Engine
- `Ctrl + 2` — Switch to Intake & PHI Redaction
- `Ctrl + 3` — Switch to Interoperability Sandbox (FHIR / HL7 / QR)
- `Ctrl + 4` — Switch to Cryptographic Audit Ledger
- `Ctrl + 5` — Switch to Clinical Analytics Dashboard
- `Ctrl + 6` (or `D`) — Open Judge Demo Challenge Suite (Hotkeys `1`, `2`, `3`, `4`)

### Team Presentation Division
- **Rishikgowda SM (Person A — Repo Lead & Backend):** Architecture, loopback network guard, thread-safe audit logger, and the deterministic-override safety philosophy.
- **Rakshith DA (Person B — Ingestion & Privacy):** Zero-leakage data privacy, 18 HIPAA Safe Harbor PHI redactions, RapidOCR on-device slip parsing.
- **Kushal M (Person C — AI Engine & Pharmacology):** Pharmacology contraindication rules, Rowland & Tozer PK accumulation model, Beers criteria, and Ollama SLM reasoning integration.
- **Sujan MB (Person D — Frontend & QA):** Drives the live interface demo, highlights the Air-Gap trust pill, executes judge crisis scenarios, and demonstrates the audit verification drawer.
