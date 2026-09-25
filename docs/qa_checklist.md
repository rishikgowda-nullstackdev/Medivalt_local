# MediVault Local — QA Checklist (Person D)
> **QA Owner:** Sujan MB (Person D)  
> **Run after every merge to `main`.** Tag bugs as GitHub Issues with `[frontend]` or `[qa]` prefix.

---

## How to Run

1. Start the server: `run_demo.bat` or `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
2. Open `http://127.0.0.1:8000` in your browser
3. Work through each section below in order
4. Mark ✅ PASS or ❌ FAIL (with a note) for each item
5. Any FAIL → open a GitHub Issue, tag it with `[qa]` and the folder owner's tag

---

## Section 1 — Header & Trust Indicators

| # | Test | Expected Result | Status |
|---|---|---|---|
| 1.1 | Page loads at `http://127.0.0.1:8000` | Dashboard renders with no JS errors in console | |
| 1.2 | "AIR-GAPPED: 0 BYTES TRANSMITTED" pill visible | Pulsing green badge visible in top-right header | |
| 1.3 | Ollama status pill updates | If Ollama running: "llama3.2:3b Ready"; if not: "Rules Engine Active" | |
| 1.4 | Doctor profile pill shows name and hospital | e.g. "Dr. Gregory House, MD" + "Princeton Plainsboro" | |
| 1.5 | Click doctor profile pill | Auth modal opens with 3 tabs (Demo Staff / Sign In / Register) | |

---

## Section 2 — Patient Intake: Demo Mode

| # | Test | Expected Result | Status |
|---|---|---|---|
| 2.1 | "Demo Patients" tab is selected by default | Demo dropdown visible; Upload section hidden | |
| 2.2 | Select PT-101 from dropdown | Patient card shows: "Stage 3 CKD", "Essential Hypertension", "T2DM"; meds: Lisinopril, Metformin, Amlodipine | |
| 2.3 | Select PT-102 from dropdown | Patient card shows: "Moderate Asthma", "Allergic Rhinitis"; meds: Salbutamol, Fluticasone | |
| 2.4 | Select PT-103 from dropdown | Patient card shows: "Atrial Fibrillation"; meds: Warfarin, Digoxin | |

---

## Section 3 — Patient Intake: Upload / Paste Mode

| # | Test | Expected Result | Status |
|---|---|---|---|
| 3.1 | Click "Upload / Paste Note" tab | Upload zone and textarea appear; demo dropdown hidden | |
| 3.2 | Click "Insert Sample Note" | Discharge note text fills the textarea | |
| 3.3 | Click "Run Safe Harbor PHI Redaction" | Patient card updates with extracted conditions, meds, allergies | |
| 3.4 | Drag `samples/patient_1_ckd_discharge.pdf` onto the upload zone | "Ingesting & Redacting..." spinner, then patient card updates; PHI count shown | |
| 3.5 | Drop an unsupported file type (e.g. `.jpg`) | Error state shown in drop zone; no crash | |

---

## Section 4 — Contraindication Safety Check

| # | Test | Expected Result | Status |
|---|---|---|---|
| 4.1 | With PT-101 loaded, type `Ibuprofen` → click Run Review | 🔴 CRITICAL banner; alert card mentions "CKD" and "NSAIDs" | |
| 4.2 | With PT-101 loaded, type `Advil` → click Run Review | 🔴 CRITICAL (brand normalized to Ibuprofen) | |
| 4.3 | With PT-102 loaded, click "Propranolol (Asthma Risk)" chip | 🟡 WARNING banner with bronchospasm mechanism | |
| 4.4 | With PT-101 loaded, type `Acetaminophen` → click Run Review | 🟢 SAFE / CLEARED banner | |
| 4.5 | With PT-103 loaded, type `Aspirin` → click Run Review | Warning or Critical due to Warfarin bleeding risk | |
| 4.6 | Click Run Review with empty medication field | Alert prompts user to enter a medication; no crash | |
| 4.7 | Click Run Review with no network (Ollama offline) | Result still returned via deterministic fallback; no crash | |
| 4.8 | Audit hash and latency shown after each review | `Audit SHA-256: xxx...xxx` and `Latency: XXX ms` fields update | |

---

## Section 5 — Quick Prescribe Chips

| # | Test | Expected Result | Status |
|---|---|---|---|
| 5.1 | Click "Advil (Brand Normalization)" chip | Medication field fills "Advil", safety check runs automatically | |
| 5.2 | Click "Propranolol (Asthma Risk)" chip | Medication field fills "Propranolol", safety check runs | |
| 5.3 | Click "Aspirin (Bleeding Risk)" chip | Medication field fills "Aspirin", safety check runs | |
| 5.4 | Click "Amoxicillin (Allergy Check)" chip | Medication field fills "Amoxicillin", safety check runs | |

---

## Section 6 — Cryptographic Audit Trail

| # | Test | Expected Result | Status |
|---|---|---|---|
| 6.1 | Click "Local Cryptographic Audit Trail" header | Table drawer expands with log rows | |
| 6.2 | Audit table shows recent review entries | Columns: Timestamp, Reviewer, Event ID, Patient Token, Prescription, Status, SHA-256 | |
| 6.3 | Click "Verify Chain Integrity" button | Spinner appears, then green "CRYPTOGRAPHIC PROOF: All N blocks verified" | |
| 6.4 | Status column uses correct color coding | CRITICAL = red, WARNING = amber, SAFE = green | |
| 6.5 | Collapse audit drawer | Table hides; toggle text reverts to "Show Logs" | |
| 6.6 | "Export CSV" link is present | Link visible; points to `/api/audit-export?format=csv` | |
| 6.7 | "Export JSON" link is present | Link visible; points to `/api/audit-export?format=json` | |

---

## Section 7 — Physician Auth Modal

| # | Test | Expected Result | Status |
|---|---|---|---|
| 7.1 | "Demo Staff" tab shows doctor cards | List of 3+ demo doctors with Switch buttons | |
| 7.2 | Click "Switch" on a different doctor | Header pill updates to that doctor's name and hospital | |
| 7.3 | "Sign In" tab — enter default credentials | `dr.house@princeton.edu` + `HospitalPass123!` → closes modal, header updates | |
| 7.4 | "Sign In" with wrong password | Error alert shown in modal; modal stays open | |
| 7.5 | "Register" tab — submit incomplete form | Error: "All clinical credentials required" | |
| 7.6 | "Register" tab — complete valid registration | OTP screen shows with simulated 6-digit code | |
| 7.7 | Enter correct OTP code | Modal closes; header updates to new doctor | |
| 7.8 | Close modal via ✕ button | Modal hides; no state corruption | |

---

## Section 8 — Responsiveness & Visual Polish

| # | Test | Expected Result | Status |
|---|---|---|---|
| 8.1 | Resize browser to mobile width (~375px) | Layout reflows; no horizontal overflow; buttons remain usable | |
| 8.2 | Resize to tablet width (~768px) | Two-column layout adapts or stacks gracefully | |
| 8.3 | No JavaScript errors in browser console | Console is clean (no errors, acceptable warnings only) | |
| 8.4 | Rapid-click "Run Review" button multiple times | Button disables during loading; no duplicate requests crash the app | |

---

## Bug Reporting Template

When you find a FAIL, open a GitHub Issue with this format:

```
Title: [QA] <Short description of the bug>

## Steps to Reproduce
1. ...
2. ...
3. ...

## Expected Result
...

## Actual Result
...

## Severity
[ ] Blocker (breaks core demo flow)
[ ] Major (visible but workaround exists)
[ ] Minor (cosmetic / edge case)

## Owner Tag
[ ] [frontend] — Sujan MB
[ ] [backend]  — Rishikgowda SM
[ ] [ai_engine] — Kushal M
[ ] [ingestion] — Rakshith DA
```

---

## Sign-Off Criteria

All items in Sections 1–7 must be ✅ PASS before tagging `v1.0` on `main`.  
Section 8 (responsiveness) should be PASS but is not a release blocker.
