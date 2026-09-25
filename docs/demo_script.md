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

### BEAT 1 — The Hook (30 sec) — *Rishikgowda speaks*
> "Hospitals can't legally send patient data to ChatGPT. But doctors still miss deadly drug interactions every day. We built MediVault Local: 100% sovereign AI, runs entirely on this laptop, zero bytes to the cloud. Let us show you."

---

### BEAT 2 — The Air-Gap Kill Move (45 sec) — *Sujan drives*

1. **Say:** *"Before I touch anything — watch the network pill in the top-right."*
2. Point to: `AIR-GAPPED: 0 BYTES TRANSMITTED (127.0.0.1)` — green pulse.
3. **Disconnect Wi-Fi live in front of judges.** Say: *"Now the machine has no internet."*
4. **Refresh the page.** The dashboard loads perfectly from localhost.
5. **Say:** *"Still works. Zero cloud dependency. This is sovereignty."*

---

### BEAT 3 — Upload a Real Patient Record (60 sec) — *Sujan drives*

1. Click the **"Upload / Paste Note"** tab on the left panel.
2. **Drag and drop** `samples/patient_1_ckd_discharge.pdf` onto the upload zone.
3. Watch: *"Ingesting & Redacting..."* → then *"PHI Redacted: X elements"*
4. The patient profile card auto-populates:
   - Conditions: **Stage 3 Chronic Kidney Disease**, Essential Hypertension, Type 2 Diabetes
   - Medications: Lisinopril, Metformin, Amlodipine
5. **Say:** *"The system just stripped all 18 HIPAA Safe Harbor identifiers — name, phone, SSN — and extracted the clinical facts. Rakshith built this redaction engine."*

---

### BEAT 4 — The Killer Contraindication (90 sec) — *Sujan drives, Kushal explains*

1. In the **Proposed Prescription** box, type: `Advil`  | Dosage: `400mg PO TID`
2. Click **"RUN OFFLINE CONTRAINDICATION REVIEW"**
3. Watch the result card:
   - 🔴 **CRITICAL CONTRAINDICATION DETECTED** banner appears
   - Alert card: *"Ibuprofen — NSAIDs inhibit renal prostaglandins (PGE2, PGI2), causing afferent arteriolar vasoconstriction and acute kidney injury in CKD patients."*
4. **Say:** *"The doctor typed a brand name — Advil. Our system normalized it to the generic, Ibuprofen, and flagged it instantly. This catches the real-world mistake."*
5. **Kushal speaks:** *"This is a two-layer safety check: first a deterministic SQLite rule fires — zero hallucination possible. Then Ollama generates the clinical explanation on top. The LLM can never override the rule."*

---

### BEAT 5 — Show a Safe Prescription (30 sec) — *Sujan drives*

1. Click the **"Acetaminophen (Safe)"** quick-prescribe chip (or type `Acetaminophen`, `500mg PO QID`)
2. Click **"RUN OFFLINE CONTRAINDICATION REVIEW"**
3. Result: 🟢 **PRESCRIPTION CLEARED (SAFE)**
4. **Say:** *"And here's what a safe prescription looks like. The system isn't just blocking — it's triaging."*

---

### BEAT 6 — Try a Warning-Level Scenario (30 sec) — *Sujan drives*

1. Switch to patient `PT-102: Sarah Connor (Moderate Asthma)` from the Demo Patients dropdown
2. Click **"Propranolol (Asthma Risk)"** quick-prescribe chip
3. Result: 🟡 **CLINICAL CAUTION / RELATIVE CONTRAINDICATION**
4. **Say:** *"Non-selective beta-blockers in asthma can cause bronchospasm. Flagged as a warning, not a block. Doctors get context, not just a stop sign."*

---

### BEAT 7 — The Cryptographic Audit Drawer (60 sec) — *Rishikgowda speaks, Sujan drives*

1. Scroll to the bottom. Click **"Local Cryptographic Audit Trail"** to expand it.
2. Show the log table — timestamp, reviewer, hospital, prescription, status, SHA-256 hash.
3. Click **"Verify Chain Integrity"** button.
4. Watch: `✅ CRYPTOGRAPHIC PROOF: All N audit blocks verified intact (Zero Tampering Detected). HIPAA § 164.312(b) Certified`
5. **Rishikgowda speaks:** *"Every review is sealed with a SHA-256 hash chained to the previous entry — like a medical blockchain, but local. You can mathematically prove no record was altered. This is HIPAA audit compliance, built in."*

---

### BEAT 8 — Wrap & Hand to Judges (30 sec) — *All team*

> *"MediVault Local: no cloud, no hallucinations, no data leaks. A doctor can use this in a hospital with no internet and still get instant, provably accurate contraindication checks. We built this in a week. Questions?"*

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
