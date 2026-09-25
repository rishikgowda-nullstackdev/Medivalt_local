# MediVault Local — Enterprise Hospital Interoperability & Clinical Decision Support
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A: Rishikgowda SM, Person B: Rakshith DA, Person C: Kushal M, Person D: Sujan MB)  
> **Standards:** HL7 CDS Hooks v1.0 | HL7 FHIR R4 | HL7 v2.x | 2023 AGS Beers Criteria | Cockcroft-Gault CrCl | HIPAA Safe Harbor § 164.514(b)(2) & Security Rule § 164.312(b)

---

## 1. Executive Summary & Sovereignty Architecture

Modern hospital electronic health record (EHR) systems (such as Epic, Cerner, and open-source VistA/OpenMRS) struggle to utilize cloud-hosted AI/ML decision support tools due to strict patient privacy mandates (HIPAA, HITECH, GDPR, and India's DPDP Act 2023). Transmitting unredacted protected health information (PHI) to remote cloud APIs exposes healthcare facilities to multi-million-dollar regulatory fines and catastrophic cybersecurity breaches.

**MediVault Local** bridges this divide by delivering an **Enterprise Sovereign Interoperability Gateway**. MediVault can seamlessly ingest clinical data from standard EHR interfaces, execute deep pharmacology and geriatric/renal safety audits entirely on local hardware, and securely transmit cryptographically verified clearance certificates across air-gapped hospital environments without a single byte leaving the local network.

```
                    ┌────────────────────────────────────────────────────────┐
                    │            Hospital EHR / Bedside Workstation         │
                    └───────┬───────────────────────────▲────────────────────┘
                            │                           │
                   HL7 FHIR / HL7 v2 /           HL7 CDS Hooks Cards /
                   Air-Gap Optical QR          Cryptographic Clearance QR
                            │                           │
                            ▼                           │
 ╔══════════════════════════════════════════════════════════════════════════════╗
 ║                         MEDIVAULT LOCAL GATEWAY                             ║
 ║                                                                              ║
 ║  ┌────────────────────────────────────────────────────────────────────────┐  ║
 ║  │ 1. Sovereign LAN Guard (RFC 1918 Private Subnets & Zero-Egress)         │  ║
 ║  └───────────────────────────────────┬────────────────────────────────────┘  ║
 ║                                      ▼                                       ║
 ║  ┌────────────────────────────────────────────────────────────────────────┐  ║
 ║  │ 2. Ingestion & Ontology Crosswalk Engine                               │  ║
 ║  │    • HL7 FHIR R4 Bundle Parser                                          │  ║
 ║  │    • HL7 v2 Pipe Delimited Message Parser (MSH/PID/OBX/AL1/RXE)        │  ║
 ║  │    • Air-Gap Optical QR Decompressor (zlib + Base64)                   │  ║
 ║  │    • Multi-Terminology Crosswalk (RxNorm, ICD-10-CM, LOINC)            │  ║
 ║  └───────────────────────────────────┬────────────────────────────────────┘  ║
 ║                                      ▼                                       ║
 ║  ┌────────────────────────────────────────────────────────────────────────┐  ║
 ║  │ 3. Sovereign Deterministic Clinical Safety Core                        │  ║
 ║  │    • Multi-Drug & Drug-Disease Contraindications                        │  ║
 ║  │    • Cumulative Polypharmacy Matrix (Triple Whammy, QTc, Serotonin)    │  ║
 ║  │    • 2023 AGS Beers Criteria (Elderly high-risk ADE prevention)        │  ║
 ║  │    • Cockcroft-Gault Creatinine Clearance (CrCl) Renal Titration        │  ║
 ║  │    • Quantitative Biomarker Lab Thresholds                             │  ║
 ║  └───────────────────────────────────┬────────────────────────────────────┘  ║
 ║                                      ▼                                       ║
 ║  ┌────────────────────────────────────────────────────────────────────────┐  ║
 ║  │ 4. Output & Interoperability Delivery                                  │  ║
 ║  │    • HL7 CDS Hooks v1.0 Service (`medication-prescribe`)               │  ║
 ║  │    • FHIR R4 Composition Diagnostic Export                             │  ║
 ║  │    • Vector SVG Clearance QR Code for Camera / Scanner Optical Air-Gap │  ║
 ║  │    • Immutable SHA-256 Hash-Chained Audit Ledger                       │  ║
 ║  └────────────────────────────────────────────────────────────────────────┘  ║
 ╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Zero-Cloud Wireless & Optical Air-Gap Transfer

Hospitals frequently require wireless interaction between roaming tablets, bedside carts, and clinical workstations without connecting to external cloud infrastructure or exposing internal clinical subnets to the public internet.

MediVault Local implements two complementary zero-cloud physical and wireless transfer channels:

### A. Sovereign Offline Wi-Fi LAN Guard (`backend/network_guard.py`)
- MediVault Local acts as an on-premise edge appliance or runs directly on a department server or nurse-station laptop.
- The `SovereignLANGuard` enforces strict **RFC 1918 Private Network** boundaries:
  - Allowed client IP ranges:
    - Loopback: `127.0.0.0/8`, `::1`
    - Class A Private: `10.0.0.0/8`
    - Class B Private: `172.16.0.0/12`
    - Class C Private: `192.168.0.0/16`
    - IPv6 Link-Local: `fe80::/10`
- **Zero-Egress Enforcement**: Any request originating from a public or non-private IP address is immediately rejected with HTTP 403 Forbidden. Outbound internet telemetry, phone-home beacons, and external API calls are disabled at the socket layer.

### B. Optical QR Air-Gap Data Exchange (`ingestion/pipeline.py` & `backend/main.py`)
For high-security ICU, isolation, or rural clinics where even local Wi-Fi is unavailable or forbidden, MediVault supports completely contactless **optical air-gap data exchange**:

1. **Intake Optical Scan (`POST /api/ingest/interop`)**:
   - A clinical note, prescription order, or patient transfer record can be encoded into a 2D QR matrix.
   - For larger payloads, MediVault supports `zlib`-compressed, Base64-encoded QR payloads (`zlib:base64...`), automatically inflating and de-serializing the JSON clinical structure.
2. **Clearance Seal Generation (`GET /api/report/clearance-qr?event_id=...`)**:
   - Once a prescription safety review is completed, MediVault generates an SVG/PNG vector QR clearance badge.
   - The QR code contains the patient token, medication, clearance status, timestamp, attending practitioner license, and the first 16 characters of the immutable SHA-256 audit hash.
   - A pharmacist, ward nurse, or auditing officer can scan the screen directly with any smartphone or handheld barcode scanner to verify clinical clearance with zero cables, zero USB drives, and zero network packets.

---

## 3. Universal Medical Terminology Crosswalk

Hospital electronic systems format clinical records using varying medical ontologies. MediVault’s `resolve_medical_ontology()` normalizes heterogeneous codes into canonical drug names, disease states, and biomarker identifiers via the local SQLite `ontology_crosswalk` catalog:

| Coding System | Standard | Example Input Code | MediVault Canonical Resolution | Clinical Target |
|---|---|---|---|---|
| **RxNorm** | National Library of Medicine | `161` | `Acetaminophen` | Active Medication |
| **RxNorm** | National Library of Medicine | `5640` | `Ibuprofen` | Active Medication / NSAID |
| **RxNorm** | National Library of Medicine | `6809` | `Metformin` | Biguanide Antidiabetic |
| **RxNorm** | National Library of Medicine | `29046` | `Lisinopril` | ACE Inhibitor |
| **RxNorm** | National Library of Medicine | `11289` | `Warfarin` | Vitamin K Antagonist |
| **RxNorm** | National Library of Medicine | `1364430` | `Apixaban` | DOAC Anticoagulant |
| **RxNorm** | National Library of Medicine | `3498` | `Diphenhydramine` | 1st-Gen Antihistamine |
| **RxNorm** | National Library of Medicine | `39993` | `Zolpidem` | Non-benzodiazepine Z-drug |
| **ICD-10-CM** | WHO / CMS | `N18.6` | `End-Stage Renal Disease` | Chronic Kidney Disease |
| **ICD-10-CM** | WHO / CMS | `I50.9` | `Heart Failure` | Cardiovascular Condition |
| **ICD-10-CM** | WHO / CMS | `K25.9` | `Gastric Ulcer` | Gastrointestinal Pathology |
| **ICD-10-CM** | WHO / CMS | `J45.909` | `Asthma` | Bronchospastic Condition |
| **LOINC** | Regenstrief Institute | `33914-3` | `egfr` | Glomerular Filtration Rate ($\text{mL/min}$) |
| **LOINC** | Regenstrief Institute | `2160-0` | `creatinine` | Serum Creatinine ($\text{mg/dL}$) |
| **LOINC** | Regenstrief Institute | `2823-3` | `potassium` | Serum Potassium ($\text{mEq/L}$) |
| **LOINC** | Regenstrief Institute | `6301-6` | `inr` | International Normalized Ratio |
| **LOINC** | Regenstrief Institute | `777-3` | `platelets` | Platelet Count ($\times 10^3/\mu\text{L}$) |

---

## 4. Ingestion Formats

MediVault Local accepts clinical inputs across four distinct formats via `POST /api/ingest/interop`:

### 1. HL7 FHIR R4 Bundle (`format="fhir"`)
Ingests standard FHIR JSON bundles containing `Patient`, `Condition`, `MedicationRequest`, `MedicationStatement`, `Observation` (labs), and `AllergyIntolerance` resources.
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "gender": "male",
        "birthDate": "1948-03-15"
      }
    },
    {
      "resource": {
        "resourceType": "Condition",
        "code": {
          "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "N18.4"}]
        }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "code": {
          "coding": [{"system": "http://loinc.org", "code": "2160-0"}]
        },
        "valueQuantity": {"value": 1.9, "unit": "mg/dL"}
      }
    }
  ]
}
```

### 2. HL7 v2.x Delimited Pipe Stream (`format="hl7v2"`)
Ingests legacy ER/inpatient HL7 pipe messages containing standard segments:
- `MSH`: Message Header
- `PID`: Patient Identification & Demographics (Field 7: DOB, Field 8: Sex)
- `PV1`: Patient Visit
- `OBX`: Observation / Lab Results (Field 3: LOINC/Test, Field 5: Numeric Value, Field 6: Units)
- `AL1`: Allergy Information (Field 3: Allergen description)
- `RXE`: Pharmacy / Treatment Encoded Order (Field 2: Medication code/name)

```hl7
MSH|^~\&|EPIC|HOSPITAL|MEDIVAULT|LOCAL|20260925120000||ORM^O01|MSG001|P|2.5
PID|1||PT-89412^^^MRN||DOE^JOHN||19450612|M
OBX|1|NM|2160-0^Creatinine^LN||2.1|mg/dL||H|||F
AL1|1|DA|PEN^Penicillin|MO|Hives
RXE|1|6809^Metformin^RXNORM|500|mg|BID
```

### 3. Air-Gap Optical QR Payload (`format="qr"`)
Accepts raw text or de-serializes compressed QR payloads formatted as:
```json
{
  "format": "qr",
  "data": "zlib:eJzLSM3JyVcozy/KSVGsBQAL5wS1..."
}
```

---

## 5. Clinical Decision Support Guardrails

### A. 2023 AGS Beers Criteria Engine (`ai_engine/geriatric_renal.py`)
The American Geriatrics Society (AGS) Beers Criteria provides explicit prescribing guidelines for adults aged 65 and older to prevent severe drug-induced delirium, cognitive decline, falls, fractures, and GI hemorrhage.

When patient age is $\ge 65$, MediVault automatically applies Beers Criteria evaluation rules:
- **First-Generation Antihistamines** (e.g. *Diphenhydramine*, *Hydroxyzine*): Highly anticholinergic; risk of severe confusion, dry mouth, urinary retention, and fall-related fractures.
- **Sedative Hypnotics / Z-Drugs** (e.g. *Zolpidem*, *Eszopiclone*): Increases delirium, motor vehicle crashes, and hip fracture risk with minimal sleep latency improvement.
- **Long-Acting Benzodiazepines** (e.g. *Alprazolam*, *Diazepam*, *Clonazepam*): Prolonged half-life in elderly; high risk of cognitive impairment, ataxia, and falls.
- **Tricyclic Antidepressants** (e.g. *Amitriptyline*, *Nortriptyline*): Orthostatic hypotension, lethal cardiac conduction delays, and strong anticholinergic load.
- **Sulfonylureas with Long Half-Life** (e.g. *Glyburide*): Severe, prolonged hypoglycemia in geriatric populations due to decreased clearance.
- **Digoxin for Atrial Fibrillation**: Increased mortality and toxicity risk; safer rate-control alternatives (beta-blockers) preferred.
- **Chronic NSAIDs** (e.g. *Ibuprofen*, *Naproxen*, *Ketorolac*): Marked escalation in peptic ulcer disease, acute GI bleeding, fluid retention, and accelerated renal decline.

### B. Cockcroft-Gault Creatinine Clearance ($CrCl$) Titration
Estimated glomerular filtration from serum creatinine often overestimates renal reserve in geriatric patients with low muscle mass. MediVault implements the gold-standard pharmacological titration formula:

$$\text{CrCl (mL/min)} = \frac{(140 - \text{Age}) \times \text{Weight (kg)}}{72 \times \text{Serum Creatinine (mg/dL)}} \times [0.85 \text{ if Female}]$$

#### Clinical Titration Rules:
1. **Apixaban (Eliquis)**:
   - If $\text{CrCl} < 15\text{ mL/min}$ or patient is on hemodialysis: **CRITICAL CONTRAINDICATION** due to catastrophic accumulation hemorrhage risk.
   - If $\text{CrCl} \le 50\text{ mL/min}$ AND $\text{Age} \ge 80$ or $\text{Weight} \le 60\text{ kg}$: **WARNING** requiring 50% dose titration to 2.5 mg BID.
2. **Enoxaparin (Lovenox)**:
   - If $\text{CrCl} < 30\text{ mL/min}$: 50% dose reduction required (1 mg/kg once daily instead of BID) or switch to Unfractionated Heparin (UFH) with aPTT monitoring.
3. **Ciprofloxacin (Cipro)**:
   - If $\text{CrCl} < 30\text{ mL/min}$: Max dose 500 mg q24h; neurotoxicity and CNS seizure threshold reduction warning.
4. **Metformin**:
   - If $\text{CrCl} < 30\text{ mL/min}$: **CRITICAL CONTRAINDICATION** (Fatal Lactic Acidosis).
   - If $30 \le \text{CrCl} < 45\text{ mL/min}$: Max dose 1000 mg/day with renal panel surveillance every 3 months.
5. **Digoxin**:
   - If $\text{CrCl} < 30\text{ mL/min}$: Reduce maintenance dose by 50% (0.0625 mg to 0.125 mg daily) and monitor serum digoxin trough levels to prevent fatal arrhythmias.

---

## 6. HL7 CDS Hooks v1.0 Standard Implementation

MediVault Local exposes a fully compliant **HL7 CDS Hooks v1.0** service (`backend/cds_hooks.py`) mounted at `/cds-services`:

### 1. Service Discovery (`GET /cds-services`)
Returns the catalog of registered sovereign decision support hooks:
```json
{
  "services": [
    {
      "hook": "medication-prescribe",
      "name": "medivault-safety-review",
      "id": "medivault-safety-review",
      "title": "MediVault Sovereign Clinical Safety Review",
      "description": "Zero-cloud deterministic check for drug-drug interactions, Beers Criteria, and renal titration.",
      "prefetch": {
        "patient": "Patient/{{context.patientId}}",
        "medications": "MedicationRequest?patient={{context.patientId}}&status=active"
      }
    }
  ]
}
```

### 2. Prescribing Decision Hook (`POST /cds-services/medication-prescribe`)
Triggered automatically inside an EHR when a clinician selects a medication to prescribe.
- **Request Context**: `patientId`, `medications` array (proposed drug).
- **Request Prefetch**: Bundled active conditions, existing medications, and diagnostic observations.
- **Response**: Compliant CDS Hooks Cards with:
  - `summary`: High-level clinical warning headline.
  - `indicator`: Card priority (`critical`, `warning`, or `info`).
  - `detail`: Comprehensive Markdown explaining pharmacological mechanism, CrCl math, and laboratory parameters.
  - `source`: Institutional provenance with `zero-cloud` verification stamp.
  - `suggestions`: "1-Click" formulary swap actions to replace contraindicated drugs with safe alternatives.

---

## 7. Verification & Automated Test Coverage

The entire interoperability and clinical decision support suite is validated through 60 automated unit and integration tests covering all critical clinical pathways:

| Test Module | Test Focus | Status |
|---|---|---|
| `tests/test_interoperability.py` | FHIR R4 Bundle parsing, HL7 v2 pipe parsing, RxNorm/ICD/LOINC ontology mapping, optical QR decompression, clearance QR vector generation, FHIR export | **PASS** |
| `tests/test_geriatric_renal.py` | Cockcroft-Gault CrCl calculations, gender/weight adjustments, Apixaban/Enoxaparin renal titration, 2023 AGS Beers Criteria (Diphenhydramine, Zolpidem, Glyburide) | **PASS** |
| `tests/test_cds_hooks.py` | HL7 CDS Hooks v1.0 discovery (`/cds-services`), prescribing hook evaluation (`medication-prescribe`), card format compliance, suggestions | **PASS** |
| `tests/test_api.py` | Core FastAPI endpoints, multipart extraction, redaction, offline review | **PASS** |
| `tests/test_audit_logger.py` | Immutable SHA-256 hash chaining, concurrency safety, tamper detection | **PASS** |
| `tests/test_auth.py` | PBKDF2-HMAC-SHA256 password hashing, hospital domain whitelist, license verification | **PASS** |
| `tests/test_network_guard.py` | RFC 1918 private IP whitelist, public IP rejection, zero-cloud egress protection | **PASS** |

**Execution Result:**
```
Ran 60 tests in 16.668s
OK (60 passed, 0 failed, 0 errors)
```
