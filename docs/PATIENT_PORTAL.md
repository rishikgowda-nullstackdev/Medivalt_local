# MediVault Local — Sovereign Patient Portal & AI Dietary Guide
> **ASYNC'26 — Track 1: Sovereign AI**  
> **Team:** Void_coders (Person A: Rishikgowda SM, Person B: Rakshith DA, Person C: Kushal M, Person D: Sujan MB)  
> **Standards:** HIPAA Safe Harbor § 164.514(b) & Security Rule § 164.312(a)(2)(i) | DPDP Act 2023 | 100% Zero-Cloud Offline Execution

---

## 1. Executive Summary & Healthcare Impact

In traditional hospital workflows, clinical decision support systems (CDSS) are built exclusively for doctors. Patients leave the clinic with opaque paper prescriptions and complex lab values (`eGFR: 38 mL/min`, `Creatinine: 2.1 mg/dL`, `INR: 2.8`) that cause extreme anxiety and confusion. Furthermore, patients often consume contraindicated everyday foods (e.g. potassium-rich bananas in kidney disease, high-sodium broths in heart failure, or cranberry juice while on Warfarin) because they never receive clear, personalized dietary advice.

**MediVault Local Patient Portal** bridges this critical clinical gap by providing a **zero-cloud, air-gapped patient kiosk and tablet interface** directly at:
```
http://127.0.0.1:8000/patient-portal
```

### Key Capabilities:
1. **Plain-English Medical Translation**: Converts terrifying lab acronyms into reassuring, easy-to-understand explanations (e.g. *"Your kidney filtration is at 38% — this is below normal, and your care team is actively monitoring this"*).
2. **Personalized AI Dietary & Wellness Narrative**: Utilizes the local on-device SLM (`llama3.2:3b` via Ollama) to generate a warm, compassionate nutritionist guide tailored to the patient's exact active conditions, medications, and organ function labs.
3. **Deterministic Condition-Specific Food Matrix**: 100% reliable fallback tables for Chronic Kidney Disease, Diabetes, Hypertension, Bronchial Asthma, and Atrial Fibrillation/Anticoagulation.
4. **Cryptographic Role Isolation**: Patient accounts exist in a separate `patient_users` table with distinct JWT claims (`"role": "patient"`), mathematically preventing patients from ever accessing practitioner endpoints or administrative logs.

---

## 2. Architecture & Data Flow

```
   ┌────────────────────────────────────────────────────────────┐
   │        Patient Kiosk / Bedside Tablet (/patient-portal)    │
   └───────────────┬────────────────────────────▲───────────────┘
                   │                            │
             Register / Login             Personalized Guide +
           (PBKDF2-HMAC-SHA256)           Plain-English Labs
                   │                            │
                   ▼                            │
 ╔═══════════════════════════════════════════════════════════════╗
 ║                MEDIVAULT LOCAL PATIENT ROUTER                 ║
 ║                                                               ║
 ║  1. Sovereign Auth Barrier (`backend/patient_portal.py`)      ║
 ║     • Validates Patient ID against clinical record            ║
 ║     • Issues offline JWT (`role: patient`, 8-hr shift expiry) ║
 ║                                                               ║
 ║  2. Plain-English Lab Translation Engine                      ║
 ║     • eGFR, Creatinine, Potassium, INR, Platelets             ║
 ║     • Multi-level status: NORMAL / WARNING / CRITICAL         ║
 ║                                                               ║
 ║  3. Multi-Layer Dietary Recommendation Synthesis              ║
 ║     • Primary: On-device Ollama SLM (llama3.2:3b, 8s timeout) ║
 ║     • Fallback: SQLite `dietary_guidelines` matrix            ║
 ╚═══════════════════════════════════════════════════════════════╝
```

---

## 3. Condition-Specific Dietary Guidelines

| Condition | Recommended Foods | Foods to Avoid | Rationale |
|---|---|---|---|
| **Chronic Kidney Disease (CKD)** | Low-sodium vegetables (cucumbers, bell peppers, cabbage), egg whites, skinless chicken, blueberries | Bananas, oranges, potatoes (high potassium); processed meats, canned soups (excess sodium); dark colas (phosphorus) | High potassium causes lethal cardiac arrhythmias in reduced filtration; sodium accelerates nephron loss |
| **Type 2 Diabetes Mellitus** | Non-starchy vegetables, legumes, whole grains, raw almonds/walnuts, wild salmon | White bread, white rice, fruit juices, sugary sodas, trans fats | Low glycemic index prevents postprandial hyperglycemia; Omega-3s protect against diabetic cardiomyopathy |
| **Essential Hypertension** | Spinach, kale, berries, oats, low-fat yogurt, garlic, beetroot | Pickles, soy sauce, cured/deli meats, excessive alcohol | Nitrates and potassium relax vascular smooth muscle; high sodium induces fluid retention and arterial stiffness |
| **Bronchial Asthma** | Salmon, mackerel, ginger, turmeric, apples, tomatoes | Sulfite-containing wines, dried fruits, frozen shrimp, cold ice cream | Antioxidants (quercetin, lycopene) reduce airway hyper-reactivity; sulfites trigger bronchospasm |
| **Atrial Fibrillation / Warfarin** | Consistent daily servings of leafy green vegetables, lean poultry | Cranberry juice, grapefruit, energy drinks, binge alcohol | Consistent vitamin K stabilizes INR; grapefruit and cranberries inhibit CYP metabolism, risking major bleeding |

---

## 4. Pre-Configured Demo Patient Accounts

Hackathon judges and evaluators can instantly test the portal using pre-seeded accounts:

| Patient ID | Clinical Profile | Username | Default Password | Primary Clinical Challenge |
|---|---|---|---|---|
| **PT-101** | John Doe (Renal Profile) | `john.doe` | `Patient123!` | Stage 3 CKD, eGFR 38, Potassium 4.6 (Avoid bananas, high potassium) |
| **PT-102** | Sarah Connor (Respiratory) | `sarah.connor` | `Patient123!` | Severe Asthma, Aspirin Allergy (Avoid sulfites, anti-inflammatory diet) |
| **PT-103** | Robert Smith (Anticoagulation) | `robert.smith` | `Patient123!` | Atrial Fibrillation on Warfarin, INR 2.8 (Consistent Vit K, avoid cranberries) |

---

## 5. Live Demo Script (2 Minutes for Judges)

1. **The Hook (Doctor View)**:
   - On the doctor dashboard (`http://127.0.0.1:8000`), show patient **PT-101 John Doe**.
   - Show how prescribing *Ibuprofen* triggers a **CRITICAL CONTRAINDICATION** due to Stage 3 CKD.
2. **The Pivot (Patient Empowerment)**:
   - Click the new **"Patient Portal"** button in the header (or open `http://127.0.0.1:8000/patient-portal`).
   - Log in as `john.doe` / `Patient123!`.
3. **The Reveal (Plain Language & AI Nutrition)**:
   - Show how the scary lab value `eGFR: 38 mL/min` is translated into warm, understandable language: *"Your kidney filtration rate is 38% of normal — this means your kidneys are working harder than they should."*
   - Scroll to **🥗 My Food & Diet Guide**: show the compassionate narrative generated by local `llama3.2:3b`.
   - Point out the specific warnings: *"Notice how John is explicitly advised to avoid bananas and high-sodium broths because his kidneys cannot eliminate potassium."*
4. **The Regulatory Clincher**:
   - Point to the footer: *"Both the doctor CDSS and the patient AI nutritionist are running 100% locally on this machine. Zero cloud APIs, zero patient telemetry, 100% sovereign."*
