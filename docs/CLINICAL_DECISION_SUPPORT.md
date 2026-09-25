# MediVault Local — Clinical Decision Support & Pharmacology Architecture
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A: Rishikgowda SM, Person B: Rakshith DA, Person C: Kushal M, Person D: Sujan MB)  
> **Regulatory Standard:** HIPAA Safe Harbor § 164.514(b)(2) & Security Rule § 164.312(b) | DPDP Act 2023  

---

## 1. Overview & Clinical Rationale

In real-world inpatient and ambulatory medical environments, prescribing errors rarely stem from a simple failure to memorize a single drug name. Instead, severe adverse drug events (ADEs) arise from **multi-dimensional clinical interactions**:
1. **Quantitative Organ Clearance Thresholds**: Organ function determines drug clearance. Prescribing the standard dose of Metformin to a patient with $\text{eGFR} = 28\text{ mL/min}$ triggers fatal lactic acidosis, whereas at $\text{eGFR} = 55\text{ mL/min}$ it is safe.
2. **Cumulative Polypharmacy Synergies**: Multiple concurrent medications combining to produce cascade toxicity (e.g. *The Triple Whammy*).
3. **Lack of Actionable Safe Alternatives**: An alert that merely says "Do not prescribe" causes physician alarm fatigue; an effective CDSS must offer an immediate, non-contraindicated formulary alternative.

MediVault Local solves these failure points with **100% Sovereign, Zero-Cloud Deterministic Decision Support**.

---

## 2. Multi-Dimensional Clinical Features

### A. Quantitative Lab Biomarker Guardrails

Patient lab parameters extracted by Person B (`/ingestion`) are evaluated against exact mathematical inequality rules (`contraindications_lab`) by Person C (`/ai_engine`):

| Biomarker | Parameter | Clinical Hazard | Safety Cutoff | Action / Recommendation |
|---|---|---|---|---|
| **eGFR** | Renal Filtration | Metformin Accumulation & Lactic Acidosis | $< 30\text{ mL/min}$ | **CRITICAL**: Absolute contraindication. Switch to Linagliptin or Insulin. |
| **eGFR** | Renal Clearance | Metformin Dosage Titration | $30 - 44\text{ mL/min}$ | **WARNING**: Limit max dose to 1000mg/day. Monitor renal function every 3 months. |
| **eGFR** | Renal Perfusion | NSAID Afferent Vasoconstriction | $< 30\text{ mL/min}$ | **CRITICAL**: Absolute contraindication. Discontinue NSAIDs. |
| **eGFR** | Renal Clearance | Enoxaparin (Lovenox) Major Bleed | $< 30\text{ mL/min}$ | **WARNING**: 50% dose reduction required (1 mg/kg once daily) or switch to UFH. |
| **Potassium ($K^+$)** | Cardiac Conduction | ACEi / ARB Fatal Hyperkalemic Arrest | $> 5.0\text{ mEq/L}$ | **CRITICAL**: Suspend ACEi/ARB. Administer potassium binder; switch to CCB. |
| **Potassium ($K^+$)** | Cardiac Conduction | Spironolactone Arrhythmia | $> 5.0\text{ mEq/L}$ | **CRITICAL**: Absolute contraindication in pre-existing hyperkalemia. |
| **INR** | Coagulation | Warfarin Supratherapeutic Hemorrhage | $> 3.5\text{ INR}$ | **CRITICAL**: Hold warfarin dose. Check bleeding signs; administer low-dose oral Vit K1. |
| **Platelets** | Primary Hemostasis | Antiplatelet (Aspirin/Clopidogrel) Diathesis | $< 50\times 10^3/\mu\text{L}$ | **CRITICAL**: Spontaneous bleeding hazard. Hold antiplatelet until platelets $> 50\text{k}$. |

---

### B. Cumulative Polypharmacy Matrix

#### 1. "The Triple Whammy" (Renal Hemodynamic Collapse)
- **Regimen Cluster**: $\text{[ACE Inhibitor / ARB]} + \text{[Loop/Thiazide Diuretic]} + \text{[NSAID]}$
- **Pathophysiology**:
  1. *NSAID*: Inhibits prostaglandin synthesis $\rightarrow$ severe vasoconstriction of the **afferent** renal arteriole.
  2. *ACEi/ARB*: Blocks angiotensin II $\rightarrow$ prevents vasoconstriction and forces vasodilation of the **efferent** renal arteriole.
  3. *Diuretic*: Reduces intravascular plasma volume and renal perfusion pressure.
  4. *Synergistic Result*: Intraglomerular hydrostatic pressure completely collapses. Glomerular filtration ceases, resulting in acute ischemic acute kidney injury (AKI) and sudden fluid overload.
- **De-escalation Protocol**: Discontinue the NSAID immediately. Substitute with Acetaminophen (max 2g/day) or topical Lidocaine patch. Check BMP within 48 hours.

#### 2. Cumulative QTc Prolongation
- **Regimen Cluster**: Antiarrhythmics (Amiodarone) + Macrolides/Fluoroquinolones (Azithromycin, Ciprofloxacin) + Antipsychotics/Antiemetics (Haloperidol, Ondansetron).
- **Pathophysiology**: Additive blockade of the human Ether-à-go-go-Related Gene (hERG) cardiac $I_{\text{Kr}}$ potassium channel delays ventricular repolarization, predisposing the myocardium to polymorphic ventricular tachycardia (Torsades de Pointes) and sudden cardiac death.

#### 3. Cumulative Serotonin Syndrome
- **Regimen Cluster**: SSRI/SNRI (Fluoxetine, Sertraline) + Serotonergic Analgesic (Tramadol) + MAOI/Triptan.
- **Pathophysiology**: Severe overactivation of central and peripheral 5-HT1A and 5-HT2A receptors causing autonomic instability, hyperthermia, and neuromuscular rigidity.

---

### C. Safe Alternative Formulary & "1-Click Swap"

When a prescription is blocked, MediVault Local displays non-contraindicated alternatives:

| Blocked Prescription | Clinical Conflict | Recommended Safe Alternative | Clinical Rationale |
|---|---|---|---|
| **Ibuprofen / Naproxen** | CKD / Peptic Ulcer | **Acetaminophen 500mg PO Q6H** (Max 2g/24h) | Hepatic metabolism preserves renal prostaglandin vasodilating tone. |
| **Ibuprofen / Naproxen** | Severe Localized Joint Pain | **Lidocaine 5% Topical Patch** | Negligible systemic bioavailability ($<3\%$), zero nephrotoxicity. |
| **Propranolol** | Bronchial Asthma | **Metoprolol Succinate 25mg daily** | Cardioselective beta-1 adrenergic antagonist; spares bronchial beta-2 receptors. |
| **Propranolol** | Hypertension in Asthma | **Amlodipine 5mg daily** | Dihydropyridine calcium channel blocker with zero bronchospastic airway effect. |
| **Amoxicillin** | Penicillin Anaphylaxis | **Azithromycin 500mg Day 1, 250mg daily** | Macrolide with zero beta-lactam cross-reactivity. |
| **Metformin** | Severe CKD ($\text{eGFR} < 30$) | **Linagliptin 5mg daily** | DPP-4 inhibitor eliminated primarily via bile/feces; 0% renal dose adjustment needed. |

Doctors click **"Swap & Verify"** to instantly update the prescription order and re-execute the safety verification in under 20 milliseconds.

---

### D. Official Cryptographic Clinical Clearance Certificate

Every review creates an immutable block in the local SHA-256 hash-chained ledger (`database/audit_trail.jsonl` and SQLite `audit_logs`).

Physicians can export or print an official, court-admissible certificate via `GET /api/report/clearance?event_id=...` featuring:
- Institutional Letterhead & Facility Code (Boston MA, Memphis TN, Princeton NJ)
- Reviewing Physician NPI & Medical License Attribution
- De-identified Patient Cryptographic Pseudonym (`ANON_...`)
- Snapshot of Extracted Organ Function Biomarkers (eGFR, Cr, K+, INR)
- Final Clearance Status Badge & Alert Pathophysiology
- Cryptographic SHA-256 Seal Block & Previous Block Hash Chain

---

## 3. Modular Team Responsibilities (`AGENTS.md`)

- **Person A (`/backend`):** FastAPI orchestrator, SQLite WAL concurrency, cryptographic audit ledger, PBKDF2 physician authentication, and clinical certificate generation.
- **Person B (`/ingestion`):** PDF/TXT extraction, 18 HIPAA Safe Harbor PHI de-identification, and quantitative lab biomarker numerical parser.
- **Person C (`/ai_engine`):** Deterministic SQLite pharmacology rules, lab threshold evaluator (`contraindications_lab`), polypharmacy matrix engine (`polypharmacy_rules`), safe alternative formulary (`safe_alternatives`), and Ollama SLM reasoning integration.
- **Person D (`/frontend`, `/docs`):** Physician dashboard, quantitative lab biomarker bar, polypharmacy warning banner, 1-Click safe alternative cards, and clinical documentation.
