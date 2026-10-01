# MediVault Local — Hackathon Demo Script
> **Driver:** Sujan MB (Person D) | **Presentation Slot:** ~5–7 minutes  
> **Track:** ASYNC'26, Track 1: Sovereign AI

---

## Pre-Demo Checklist (Do This BEFORE Judges Arrive)

- [ ] Run `run_demo.bat` and confirm the server starts on `http://127.0.0.1:8000`
- [ ] Open `http://127.0.0.1:8000` in Chrome/Firefox (full screen)
- [ ] Confirm the **"AIR-GAPPED: 0 BYTES TRANSMITTED"** pill is visible and pulsing green
- [ ] Have `samples/patient_1_ckd_discharge.pdf` ready on the desktop for drag-and-drop
- [ ] (Optional) Start Ollama: run `ollama serve` in a terminal — confirm header reads **"Ollama: llama3.2:3b Ready"**
- [ ] Wi-Fi off, Ethernet unplugged — do this **during** the demo for max impact

---

## The Demo Flow (Click-by-Click)

### BEAT 1 — The Hook & Architecture (45 sec) — *Rishikgowda SM (Person A) speaks*
> "Hospitals are legally barred by HIPAA and DPDP from uploading patient records to cloud LLMs. Yet doctors fatigue and miss fatal drug interactions every day. We engineered MediVault Local: 100% sovereign AI that runs completely on this air-gapped machine. I built our backend integration, the deterministic-override architecture, our FastMCP server, and our local cryptographic ledger. Zero bytes leave this laptop. Let us prove it to you live."

---

### BEAT 2 — The Air-Gap Kill Move & 3D Interface (45 sec) — *Sujan MB (Person D) drives & speaks*

1. **Say:** *"I designed and built the complete clinician dashboard, our 3D anatomical glass-heart visualization, and patient safety portal. Watch the network security indicator in our top-right header."*
2. Point to: `AIR-GAPPED: 0 BYTES TRANSMITTED (127.0.0.1)` — pulsing emerald beacon.
3. **Disconnect Wi-Fi live in front of judges.** Say: *"The laptop is now physically disconnected from the global internet."*
4. **Refresh the page.** The entire dashboard, 3D anatomical organ models, and local databases render instantly.
5. **Say:** *"Instantaneous execution. Zero cloud ping. Real sovereign software."*

---

### BEAT 3 — Ingestion, HIPAA Safe Harbor Redaction & Handwritten OCR (60 sec) — *Rakshith DA (Person B) speaks, Sujan drives*

1. Sujan clicks the **"Upload / Paste Note"** tab or drops `samples/patient_1_ckd_discharge.pdf`.
2. **Rakshith speaks:**
> "I built our ingestion pipeline and privacy engine. When a paper record or digital note enters the node, our system executes two operations:
> 1. **Zero-Cloud OCR:** For scanned prescription slips or handwritten doctor notes, our offline ONNX RapidOCR extracts raw text without third-party vision APIs.
> 2. **HIPAA Safe Harbor § 164.514(b) Redaction:** All 18 direct identifiers — patient names, phone numbers, MRNs, dates — are sanitized into irreversible SHA-256 tokens (`ANON_...`) in volatile RAM. Only pure clinical facts reach our decision engine."
3. Watch the patient profile card auto-populate with extracted Stage 3 CKD, Hypertension, and baseline labs (eGFR: 38 mL/min).

---

### BEAT 4 — The Deterministic-Override Safety Engine & Vector RAG (90 sec) — *Kushal M (Person C) speaks, Sujan drives*

1. Sujan selects **PT-101**, types `Advil` (or `Ketorolac 30mg IV`), and clicks **"RUN OFFLINE CONTRAINDICATION REVIEW"**.
2. A prominent 🔴 **CRITICAL CONTRAINDICATION DETECTED** banner appears with hemodynamic alert and Rowland & Tozer PK clearance simulation curve showing a 2.2x excretion delay.
3. **Kushal speaks:**
> "I designed our clinical AI engine and pharmacology knowledge graph. A critical flaw with cloud LLMs in healthcare is hallucination. MediVault Local solves this with our **Deterministic Override Design**:
> 1. Our local SQLite pharmacology matrix first evaluates absolute contraindications (e.g. NSAID prostaglandin inhibition in CKD). If a hard contraindication is flagged, it is mathematically locked.
> 2. Our offline **Vector RAG engine** retrieves semantic embeddings across 32 curated FDA monographs and KDIGO clinical guidelines.
> 3. Local Ollama (llama3.2) only generates explanatory pathophysiology context. The SLM can **never** unflag or hallucinate a green clearance over our deterministic safety rules."

---

### BEAT 5 — Safe Regimen Triage & Formulary Alternatives (30 sec) — *Sujan drives, Kushal speaks*

1. Sujan clicks the quick-prescribe chip **"Acetaminophen (Safe)"**.
2. Review returns 🟢 **PRESCRIPTION CLEARED (SAFE FOR REGIMEN)**.
3. **Kushal speaks:** *"Notice the engine also recommends safe alternative analgesics, titrating doses to the patient's exact eGFR of 38 mL/min."*

---

### BEAT 6 — 1-Click Institutional Doctor Switcher & Verification (45 sec) — *Sujan drives*

1. Sujan clicks the **Doctor Profile Pill** in the top header (`🩺 Dr. Gregory House, MD | Princeton Plainsboro [Verified Staff]`).
2. Shows the 3-tab modal: 1-Click Demo Staff Switcher, Institutional Sign In, and Institutional Register.
3. **Sujan speaks:** *"We enforce hospital email domain whitelisting (e.g. `@metrogeneral.org`, `@ppth.org`) and 6-digit cryptographic OTP email verification, complete with a sovereign simulated intranet mail outbox for zero-cloud testing."*
4. Clicks **"Switch to Dr. Meredith Grey, MD (Metro General Hospital)"**. The session updates with cryptographic non-repudiation.

---

### BEAT 7 — SHA-256 Merkle Ledger, PDF Export & FastMCP Server (60 sec) — *Rishikgowda SM (Person A) speaks, Sujan drives*

1. Sujan clicks **"PDF Export"** on the review result. An authentic, cryptographically signed A4 Clinical Clearance Certificate downloads immediately.
2. Sujan expands the **"Local Cryptographic Audit Trail"** drawer and clicks **"Verify Chain Integrity"**.
3. Green confirmation appears: `✅ CRYPTOGRAPHIC PROOF: All audit blocks verified intact (Zero Tampering Detected). HIPAA § 164.312(b) Certified`.
4. **Rishikgowda speaks:**
> "Every review is hashed with the doctor's verified NPI, timestamp, and previous block hash into an immutable local SHA-256 chain.
> Furthermore, we have built a fully compliant **FastMCP Server** (`medivault-local-cdss`). External sovereign AI agents in Claude Desktop or Cursor can invoke our review, PK simulation, vector knowledge search, and certified PDF export directly over stdio or REST loopback without a single packet leaving this machine."

---

### BEAT 8 — The Closing Pitch & Q&A (30 sec) — *All Team*

> **Rishikgowda:** *"MediVault Local delivers zero-cloud privacy, zero-hallucination safety, and mathematical audit integrity. It's ready for any clinic, field hospital, or ICU workstation today. Thank you, and we welcome your questions."*

**Expect questions on:**
- *"How does it work offline?"* → Ollama runs locally on port 11434. SQLite is a local file.
- *"What if Ollama is down?"* → Deterministic fallback is always on. Demo works without Ollama.
- *"Is this HIPAA compliant?"* → Binds to 127.0.0.1 only. PHI never leaves RAM. Audit trail is local. No external API calls.

---

## Backup Plan (If Something Breaks)

| Problem | Fix |
|---|---|
| Server won't start | Check Python venv: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| Ollama not ready | Status pill shows "Rules Engine Active" — demo still works fully deterministically |
| PDF upload fails | Switch to "Demo Patients" tab — no upload needed, all 3 patients work |
| Audit drawer empty | Run the safety check once first to generate an audit entry |
| Browser blank page | Hard refresh `Ctrl+Shift+R`, confirm server is running on port 8000 |
