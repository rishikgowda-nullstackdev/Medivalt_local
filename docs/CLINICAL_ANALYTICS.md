# MediVault Local — Clinical Analytics & Sovereign Insights Manual
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A: Rishikgowda SM, Person B: Rakshith DA, Person C: Kushal M, Person D: Sujan MB)  
> **Standards:** HIPAA Safe Harbor § 164.514(b) & Security Rule § 164.312(b) | DPDP Act 2023 | 100% Zero-Cloud Offline Execution

---

## 1. Executive Summary & Clinical Value

While individual prescription review prevents single adverse drug reactions (ADRs), modern hospital Chief Medical Officers (CMOs) and Pharmacy Directors require **population-level surveillance** to identify systematic prescribing vulnerabilities, track high-risk collision trends, and audit air-gap compliance.

**MediVault Local Clinical Analytics & Sovereign Insights** (Tab 5 in Doctor Workstation) introduces an on-device business intelligence and clinical analytics engine operating 100% offline:
```
http://127.0.0.1:8000 (Tab 5 / Ctrl+5)
```

---

## 2. Key Capabilities & Metric Dimensions

### A. Population Risk & Interception KPIs
- **Total Prescriptions Reviewed**: Cumulative counter of all CDSS review operations.
- **Adverse Drug Events (ADEs) Intercepted**: Number of prescriptions flagged before reaching the patient (e.g. fatal NSAIDs in Stage 3 CKD).
- **Contraindication Intercept Rate**: Percentage of all evaluated prescriptions triggering safety interventions.
- **Sovereign Cloud Egress**: **Strictly 0 Bytes** — cryptographic verification that no PHI or telemetry leaves the local machine.

### B. Interactive Chart.js Visualizations
1. **Prescription Triage Distribution (Doughnut Chart)**:
   - Visual breakdown of outcomes: **Critical Contraindications** (Red `#ef4444`), **Warning Thresholds** (Amber `#f59e0b`), and **Safe Clearances** (Emerald `#10b981`).
2. **Top Flagged High-Risk Drugs (Horizontal Bar Chart)**:
   - Highlights the 5 most frequently intercepted medications across all clinical encounters (e.g., Ibuprofen in renal disease, Warfarin in bleeding synergy, Metformin in reduced CrCl, Diphenhydramine in geriatric delirium).
3. **Review Volume & 0-Byte Cloud Egress Telemetry (Area/Line Chart)**:
   - Proves high-throughput local processing activity alongside a continuous flatline zero-byte public internet egress guarantee.

### C. High-Risk Drug Collision Leaderboard
Ranked table of multi-drug collision hazards intercepted by MediVault Local:

| Rank | Collision | Clinical Name | Mechanism | Severity | Evidence-Based Alternative |
|---|---|---|---|---|---|
| **#1** | NSAID + ACE-Inhibitor + Diuretic | *"The Triple Whammy"* | Afferent vasoconstriction + efferent vasodilation causing acute renal hemodynamic failure | **CRITICAL** | Acetaminophen (max 2g/day) + Monitored ACEi |
| **#2** | Warfarin + Aspirin / NSAID | *Synergistic Hemostatic Failure* | Dual platelet blockade and vitamin K factor inhibition multiplying major GI bleeding | **CRITICAL** | Monotherapy under daily INR surveillance |
| **#3** | Non-selective Beta Blocker + Asthma | *Refractory Bronchospastic Arrest* | Beta-2 smooth muscle antagonism triggering unmanageable airway obstruction | **CRITICAL** | Cardioselective Beta-1 (Metoprolol) or CCB (Amlodipine) |
| **#4** | Lisinopril + Spironolactone / K+ Salt | *Lethal Hyperkalemic Conduction Block* | Suppressed aldosterone excretion causing fatal ventricular arrhythmias | **WARNING** | Switch to Loop Diuretic (Furosemide) |
| **#5** | 1st-Gen Antihistamine in Elderly | *Geriatric Delirium & Falls (Beers)* | High central anticholinergic toxicity, nocturnal confusion, hip fractures | **CRITICAL** | 2nd-Gen non-sedating antihistamine (Loratadine) |

---

## 3. Architecture & API Endpoints

- **`GET /api/analytics/summary?days=N`**:
  Aggregates total reviews, alert breakdown, top flagged drugs, organ vulnerability, and average latency.
- **`GET /api/analytics/trends?limit=14`**:
  Returns time-series buckets for total reviews, flagged alerts, and verified 0-byte egress telemetry.
- **`GET /api/analytics/export`**:
  Generates and downloads an institutional CSV audit report containing event IDs, anonymized patient tokens, proposed drugs, and SHA-256 audit hashes.

---

## 4. Live Demo Script (2 Minutes for Hackathon Judges)

1. **Navigate to Tab 5**:
   - On the doctor workstation (`http://127.0.0.1:8000`), press `Ctrl+5` or click **"5. Clinical Analytics"** in the navigation bar.
2. **Point to the 0-Byte Sovereign Egress Metric**:
   - *"Notice this KPI: MediVault Local has processed hundreds of prescription reviews with exactly 0 bytes transmitted to any cloud API or external server."*
3. **Show Triage Distribution & Intercept Rate**:
   - Hover over the Doughnut chart to display the proportion of Critical vs Warning vs Safe reviews.
   - Point out the Horizontal Bar chart: *"Our top intercepted drug is Ibuprofen, demonstrating how the system consistently protects CKD patients from accidental nephrotoxicity."*
4. **Show The Triple Whammy in the Leaderboard**:
   - Scroll down to the High-Risk Drug Collision Leaderboard:
   - *"Here is the infamous 'Triple Whammy'—one of the leading causes of preventable acute dialysis admissions in hospitals. MediVault automatically intercepts this combo and suggests safe alternatives."*
5. **Download Institutional Audit CSV**:
   - Click **"Export CSV"** to demonstrate instant compliance reporting for hospital chief medical officers.
