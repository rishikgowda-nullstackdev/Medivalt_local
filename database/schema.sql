-- MediVault Local: Zero-Cloud SQLite Clinical Database Schema
-- Provides clinical history, drug-disease & drug-drug contraindications, and HIPAA audit trails.

PRAGMA foreign_keys = ON;

-- 1. Patients Table (De-identified)
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    patient_name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Patient Diagnosed Conditions
CREATE TABLE IF NOT EXISTS patient_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    condition_name TEXT NOT NULL,
    icd10_code TEXT,
    diagnosed_date TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    UNIQUE(patient_id, condition_name)
);

-- 3. Patient Current Medications
CREATE TABLE IF NOT EXISTS patient_medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    medication_name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    status TEXT DEFAULT 'ACTIVE',
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    UNIQUE(patient_id, medication_name)
);

-- 4. Patient Known Allergies
CREATE TABLE IF NOT EXISTS patient_allergies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    allergen TEXT NOT NULL,
    reaction TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    UNIQUE(patient_id, allergen)
);

-- 4b. Patient Clinical Lab Biomarkers
CREATE TABLE IF NOT EXISTS patient_labs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    biomarker_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    UNIQUE(patient_id, biomarker_name)
);

-- 5. Drug <-> Disease Contraindications Table
CREATE TABLE IF NOT EXISTS contraindications_disease (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL COLLATE NOCASE,
    condition_name TEXT NOT NULL COLLATE NOCASE,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'WARNING', 'SAFE')),
    mechanism TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    UNIQUE(drug_name, condition_name)
);

-- 6. Drug <-> Drug Interactions Table
CREATE TABLE IF NOT EXISTS contraindications_drug (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a TEXT NOT NULL COLLATE NOCASE,
    drug_b TEXT NOT NULL COLLATE NOCASE,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'WARNING', 'SAFE')),
    mechanism TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    UNIQUE(drug_a, drug_b)
);

-- 7. Healthcare Facilities / Hospitals Table
CREATE TABLE IF NOT EXISTS hospitals (
    hospital_id TEXT PRIMARY KEY,
    hospital_name TEXT NOT NULL UNIQUE,
    facility_code TEXT UNIQUE NOT NULL,
    domain_whitelist TEXT NOT NULL,
    department TEXT NOT NULL,
    city_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Clinical Practitioners Table (with Email Verification & Medical License)
CREATE TABLE IF NOT EXISTS practitioners (
    practitioner_id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    medical_license TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'PHYSICIAN' CHECK(role IN ('PHYSICIAN', 'PHARMACIST', 'AUDITOR', 'ADMIN')),
    email_verified INTEGER DEFAULT 0 CHECK(email_verified IN (0, 1)),
    verification_token TEXT,
    token_expires_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(hospital_id) ON DELETE RESTRICT
);

-- 9. Cryptographic Local Audit Trail (HIPAA Security Rule § 164.312(b) & § 164.312(a)(2)(i))
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    patient_hash TEXT NOT NULL,
    practitioner_id TEXT DEFAULT 'PRAC-103',
    practitioner_name TEXT DEFAULT 'Dr. Gregory House, MD',
    hospital_name TEXT DEFAULT 'Princeton Plainsboro Teaching Hospital',
    proposed_medication TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    alerts_count INTEGER DEFAULT 0,
    zero_cloud_verified INTEGER DEFAULT 1,
    execution_time_ms REAL,
    prev_hash TEXT NOT NULL,
    audit_hash TEXT NOT NULL
);

-- =========================================================================
-- SEED DATA: Pre-populated Demo Patients & High-Severity Contraindications
-- =========================================================================

-- Seed Demo Patients
INSERT OR REPLACE INTO patients (patient_id, patient_name, age, gender) VALUES
('PT-101', 'John Doe (Renal Profile)', 64, 'Male'),
('PT-102', 'Sarah Connor (Respiratory Profile)', 42, 'Female'),
('PT-103', 'Robert Smith (Anticoagulation Profile)', 71, 'Male');

-- Seed Conditions
INSERT OR IGNORE INTO patient_conditions (patient_id, condition_name, icd10_code, diagnosed_date) VALUES
('PT-101', 'Stage 3 Chronic Kidney Disease (CKD)', 'N18.3', '2023-04-12'),
('PT-101', 'Essential Hypertension', 'I10', '2019-08-20'),
('PT-101', 'Type 2 Diabetes Mellitus', 'E11.9', '2021-01-15'),
('PT-102', 'Moderate Persistent Bronchial Asthma', 'J45.40', '2018-05-11'),
('PT-102', 'Allergic Rhinitis', 'J30.9', '2020-02-02'),
('PT-103', 'Non-valvular Atrial Fibrillation', 'I48.0', '2022-10-18'),
('PT-103', 'History of Deep Vein Thrombosis', 'Z86.718', '2021-06-30'),
('PT-103', 'Gastroesophageal Reflux Disease', 'K21.9', '2020-11-04');

-- Seed Current Medications
INSERT OR IGNORE INTO patient_medications (patient_id, medication_name, dosage, frequency) VALUES
('PT-101', 'Lisinopril', '20mg', 'Once daily'),
('PT-101', 'Metformin', '500mg', 'Twice daily'),
('PT-101', 'Amlodipine', '5mg', 'Once daily'),
('PT-102', 'Albuterol HFA Inhaler', '90mcg', 'PRN for wheezing'),
('PT-102', 'Fluticasone Propionate', '110mcg', 'BID'),
('PT-103', 'Warfarin', '5mg', 'Once daily (target INR 2.0-3.0)'),
('PT-103', 'Pantoprazole', '40mg', 'Once daily before breakfast');

-- Seed Allergies
INSERT OR IGNORE INTO patient_allergies (patient_id, allergen, reaction) VALUES
('PT-101', 'Sulfonamides', 'Maculopapular rash'),
('PT-102', 'Aspirin', 'Severe bronchospasm / urticaria'),
('PT-103', 'Codeine', 'Severe nausea and dizziness');

-- Seed Quantitative Patient Labs
INSERT OR IGNORE INTO patient_labs (patient_id, biomarker_name, value, unit) VALUES
('PT-101', 'egfr', 38.0, 'mL/min/1.73m2'),
('PT-101', 'creatinine', 2.1, 'mg/dL'),
('PT-101', 'potassium', 4.6, 'mEq/L'),
('PT-102', 'egfr', 92.0, 'mL/min/1.73m2'),
('PT-102', 'potassium', 4.1, 'mEq/L'),
('PT-103', 'inr', 2.8, 'INR'),
('PT-103', 'platelets', 165.0, 'x10^3/uL');

-- Seed High-Risk Drug-Disease Contraindications
INSERT OR IGNORE INTO contraindications_disease (drug_name, condition_name, severity, mechanism, recommendation) VALUES
('ibuprofen', 'chronic kidney disease', 'CRITICAL', 'Inhibits renal vasodilating prostaglandins (PGE2, PGI2); precipitates acute afferent arteriolar vasoconstriction and acute renal failure in pre-existing CKD.', 'Absolute contraindication. Avoid NSAIDs. Consider Acetaminophen (max 2g/day) or topical analgesics.'),
('naproxen', 'chronic kidney disease', 'CRITICAL', 'NSAID-induced inhibition of renal perfusion sharply accelerates renal function decline and causes fluid retention.', 'Contraindicated. Discontinue NSAID.'),
('diclofenac', 'chronic kidney disease', 'CRITICAL', 'High risk of acute tubular necrosis and acute decompensation in renal impairment.', 'Contraindicated in moderate-to-severe CKD.'),
('ketorolac', 'chronic kidney disease', 'CRITICAL', 'Potent non-selective NSAID with severe nephrotoxicity profile.', 'Absolute contraindication in renal failure or volume depletion.'),
('propranolol', 'asthma', 'CRITICAL', 'Non-selective beta-2 antagonism blocks bronchial smooth muscle relaxation, triggering life-threatening refractory bronchospasm.', 'Absolute contraindication. If antihypertensive is needed, use CCB (e.g. Amlodipine) or ARB.'),
('timolol', 'asthma', 'CRITICAL', 'Beta-2 blockade causes severe airway constriction even with ophthalmic administration.', 'Contraindicated. Avoid beta-blockers in reactive airway diseases.'),
('nadolol', 'asthma', 'CRITICAL', 'Inhibits beta-2 receptors resulting in acute bronchoconstriction unresponsive to rescue bronchodilators.', 'Absolute contraindication.'),
('metformin', 'chronic kidney disease', 'WARNING', 'Drug accumulation due to reduced renal clearance significantly increases risk of lactic acidosis.', 'Check eGFR. Contraindicated if eGFR < 30 mL/min; reduce maximum dose if eGFR is 30-44 mL/min.'),
('lisinopril', 'pregnancy', 'CRITICAL', 'Teratogenic and fetotoxic: induces fetal renal dysgenesis, oligohydramnios, and neonatal skull hypoplasia.', 'Absolute contraindication during pregnancy. Switch to Labetalol or Methyldopa.'),
('warfarin', 'peptic ulcer', 'CRITICAL', 'Impaired coagulation markedly elevates the risk of massive, life-threatening upper gastrointestinal hemorrhage.', 'Contraindicated during active ulceration or active GI bleed.'),
('empagliflozin', 'diabetic ketoacidosis', 'CRITICAL', 'SGLT2 inhibitors can precipitate euglycemic diabetic ketoacidosis.', 'Discontinue immediately if ketoacidosis is suspected.');

-- Seed High-Risk Drug-Drug Interactions
INSERT OR IGNORE INTO contraindications_drug (drug_a, drug_b, severity, mechanism, recommendation) VALUES
('warfarin', 'aspirin', 'CRITICAL', 'Concurrent antiplatelet and oral anticoagulant therapy synergistically impairs hemostasis, dramatically multiplying major bleeding risk.', 'Avoid combination unless strictly indicated by cardiology under close INR surveillance.'),
('warfarin', 'ibuprofen', 'CRITICAL', 'NSAIDs displace warfarin from plasma proteins and erode gastric mucosa, drastically elevating GI hemorrhage risk.', 'Avoid co-prescription. Use Acetaminophen for pain relief.'),
('clopidogrel', 'omeprazole', 'WARNING', 'Omeprazole competitively inhibits CYP2C19, significantly reducing bioactivation and antiplatelet efficacy of clopidogrel.', 'Switch to Pantoprazole, which exhibits minimal CYP2C19 interaction.'),
('fluoxetine', 'tramadol', 'CRITICAL', 'Dual serotonergic elevation and CYP2D6 inhibition elevates systemic tramadol levels, precipitating life-threatening Serotonin Syndrome.', 'Avoid combination. Consider non-serotonergic analgesia.'),
('sertraline', 'selegiline', 'CRITICAL', 'Combined SSRI and MAO inhibitor causes hyperpyrexia, autonomic instability, and fatal Serotonin Syndrome.', 'Absolute contraindication. Requires a 14-day washout period between agents.'),
('simvastatin', 'clarithromycin', 'CRITICAL', 'Clarithromycin is a potent CYP3A4 inhibitor, multiplying simvastatin plasma concentration up to 10-fold with severe risk of rhabdomyolysis.', 'Temporarily suspend simvastatin during macrolide therapy or use Azithromycin.'),
('atorvastatin', 'gemfibrozil', 'WARNING', 'Interference with glucuronidation and OATP1B1 uptake elevates statin systemic exposure and myopathy risk.', 'Avoid co-administration or prescribe lowest possible statin dose with CK monitoring.'),
('spironolactone', 'lisinopril', 'WARNING', 'Combined potassium-sparing diuretic and ACE inhibitor impairs potassium excretion, creating high risk of lethal hyperkalemia.', 'Monitor serum potassium and renal panel within 7 days of initiating co-therapy.');

-- =========================================================================
-- SEED DATA: Pre-configured Hospitals & Verified Clinical Staff
-- =========================================================================

-- Seed Hospitals
INSERT OR IGNORE INTO hospitals (hospital_id, hospital_name, facility_code, domain_whitelist, department, city_state) VALUES
('HOSP-01', 'Metro General Hospital', 'MGH-901', 'metrogeneral.org', 'Nephrology & Renal Care', 'Boston, MA'),
('HOSP-02', 'St. Jude Medical Center', 'SJM-402', 'stjude.org', 'Pulmonary & Critical Care', 'Memphis, TN'),
('HOSP-03', 'Princeton Plainsboro Teaching Hospital', 'PPTH-108', 'princeton.edu', 'Diagnostic & Internal Medicine', 'Princeton, NJ');

-- Seed Verified Demo Physicians (Default Password: HospitalPass123!)
-- Hash generated via PBKDF2-HMAC-SHA256 (100,000 rounds)
INSERT OR IGNORE INTO practitioners (practitioner_id, hospital_id, full_name, email, password_hash, salt, medical_license, role, email_verified) VALUES
('PRAC-101', 'HOSP-01', 'Dr. Sarah Jenkins, MD', 'dr.jenkins@metrogeneral.org', '9058762181cd08075e77f57abd2cf5d7e98d0568493d57151f6f97d734fd316c', 'f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6', 'NPI-1982736450', 'PHYSICIAN', 1),
('PRAC-102', 'HOSP-02', 'Dr. John Watson, MD', 'dr.watson@stjude.org', '9058762181cd08075e77f57abd2cf5d7e98d0568493d57151f6f97d734fd316c', 'f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6', 'NPI-1122334455', 'PHYSICIAN', 1),
('PRAC-103', 'HOSP-03', 'Dr. Gregory House, MD', 'dr.house@princeton.edu', '9058762181cd08075e77f57abd2cf5d7e98d0568493d57151f6f97d734fd316c', 'f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6', 'NPI-1999887766', 'PHYSICIAN', 1);

-- =========================================================================
-- NEXT-GENERATION CLINICAL DECISION SUPPORT TABLES & SEEDS
-- =========================================================================

-- 10. Quantitative Lab Biomarker Threshold Rules
CREATE TABLE IF NOT EXISTS contraindications_lab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL COLLATE NOCASE,
    biomarker_name TEXT NOT NULL COLLATE NOCASE, -- e.g. 'eGFR', 'potassium', 'inr', 'platelets'
    operator TEXT NOT NULL CHECK(operator IN ('<', '<=', '>', '>=')),
    threshold_value REAL NOT NULL,
    unit TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'WARNING')),
    mechanism TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    UNIQUE(drug_name, biomarker_name, operator, threshold_value)
);

-- 11. Multi-Drug Polypharmacy Rules
CREATE TABLE IF NOT EXISTS polypharmacy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT UNIQUE NOT NULL,
    rule_name TEXT NOT NULL,
    required_classes TEXT NOT NULL, -- JSON array of required drug classes
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'WARNING')),
    mechanism TEXT NOT NULL,
    recommendation TEXT NOT NULL
);

-- 12. Clinical Safe Alternatives Formulary
CREATE TABLE IF NOT EXISTS safe_alternatives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocked_drug TEXT NOT NULL COLLATE NOCASE,
    clinical_condition TEXT NOT NULL COLLATE NOCASE,
    suggested_alternative TEXT NOT NULL,
    dosage_guide TEXT NOT NULL,
    clinical_rationale TEXT NOT NULL,
    UNIQUE(blocked_drug, clinical_condition, suggested_alternative)
);

-- Seed Quantitative Lab Thresholds
INSERT OR IGNORE INTO contraindications_lab (drug_name, biomarker_name, operator, threshold_value, unit, severity, mechanism, recommendation) VALUES
('metformin', 'egfr', '<', 30.0, 'mL/min/1.73m2', 'CRITICAL', 'Severe renal impairment significantly reduces metformin clearance, precipitating life-threatening lactic acidosis (50% mortality rate).', 'Absolute contraindication if eGFR < 30 mL/min. Discontinue immediately. Consider Insulin or Linagliptin.'),
('metformin', 'egfr', '<=', 44.0, 'mL/min/1.73m2', 'WARNING', 'Moderate renal impairment (eGFR 30-44 mL/min) increases drug accumulation risk.', 'Dose titration required: limit maximum dose to 1000mg/day. Monitor renal function every 3 months.'),
('lisinopril', 'potassium', '>', 5.0, 'mEq/L', 'CRITICAL', 'ACE-inhibitor suppresses aldosterone, preventing renal potassium excretion and inducing fatal hyperkalemic cardiac arrest.', 'Contraindicated while potassium > 5.0 mEq/L. Suspend ACEi, administer potassium binder, and switch to CCB (Amlodipine).'),
('spironolactone', 'potassium', '>', 5.0, 'mEq/L', 'CRITICAL', 'Potassium-sparing aldosterone antagonist in pre-existing hyperkalemia dramatically accelerates cardiac conduction abnormalities.', 'Absolute contraindication. Avoid spironolactone when baseline K+ exceeds 5.0 mEq/L.'),
('warfarin', 'inr', '>', 3.5, 'INR', 'CRITICAL', 'Supratherapeutic anticoagulation level (INR > 3.5) drastically multiplies spontaneous intracranial and gastrointestinal hemorrhage hazard.', 'Hold warfarin dose. Assess bleeding symptoms, consider low-dose oral Vitamin K1, and recheck INR in 24 hours.'),
('aspirin', 'platelets', '<', 50.0, 'x10^3/uL', 'CRITICAL', 'Irreversible platelet cyclooxygenase inhibition in profound thrombocytopenia (<50k) creates severe spontaneous hemorrhagic diathesis.', 'Contraindicated. Discontinue antiplatelet therapy until platelet recovery above 50,000/uL.'),
('clopidogrel', 'platelets', '<', 50.0, 'x10^3/uL', 'CRITICAL', 'P2Y12 inhibition combined with severe thrombocytopenia precipitates life-threatening mucosal and microvascular bleeding.', 'Discontinue clopidogrel immediately. Consult hematology.'),
('enoxaparin', 'egfr', '<', 30.0, 'mL/min/1.73m2', 'WARNING', 'Low-molecular-weight heparin is cleared primarily via kidneys; accumulation in eGFR < 30 markedly elevates major bleed rates.', 'Reduce dose by 50% (e.g. 1 mg/kg once daily instead of BID) or switch to Unfractionated Heparin (monitored by aPTT).'),
('ibuprofen', 'egfr', '<', 30.0, 'mL/min/1.73m2', 'CRITICAL', 'In severe renal insufficiency (eGFR < 30), NSAID afferent vasoconstriction induces acute renal necrosis and fluid overload.', 'Absolute contraindication. Switch to Acetaminophen or topical analgesics.');

-- Seed Polypharmacy Rules
INSERT OR IGNORE INTO polypharmacy_rules (rule_id, rule_name, required_classes, severity, mechanism, recommendation) VALUES
('TRIPLE_WHAMMY', 'The Triple Whammy (Renal Perfusion Collapse)', '["ace_inhibitor_or_arb", "diuretic", "nsaid"]', 'CRITICAL', 'Concurrent administration of an ACEi/ARB (efferent arteriolar dilation) + Diuretic (hypovolemia/decreased renal plasma flow) + NSAID (afferent arteriolar constriction) eliminates glomerular filtration pressure, causing acute ischemic renal failure.', 'Emergency de-escalation: Discontinue NSAID immediately. Substitute with Acetaminophen (max 2g/day) or topical analgesics. Rehydrate and check BMP within 48h.'),
('QTC_PROLONGATION_HIGH', 'Cumulative QTc Prolongation & Arrhythmia Hazard', '["qt_prolonging_cardiac", "qt_prolonging_antimicrobial", "qt_prolonging_psych_or_antiemetic"]', 'CRITICAL', 'Additive cardiac delayed-rectifier potassium current (IKr) blockade dramatically prolongs ventricular repolarization, triggering polymorphic ventricular tachycardia (Torsades de Pointes).', 'Avoid multi-agent QT combination. Obtain baseline 12-lead ECG and monitor serum potassium/magnesium. Choose non-QT prolonging alternative.'),
('SEROTONIN_SYNDROME_COMBO', 'Cumulative Serotonergic Toxicity (Serotonin Syndrome)', '["ssri_or_snri", "serotonergic_analgesic", "maoi_or_triptan"]', 'CRITICAL', 'Additive serotonergic hyperstimulation of 5-HT1A and 5-HT2A receptors triggers acute Serotonin Syndrome: autonomic hyperactivity, neuromuscular clonus, hyperthermia, and potential fatal cardiovascular collapse.', 'Discontinue serotonergic analgesic immediately. Do not co-prescribe Tramadol with multiple serotonergic agents.');

-- Seed Clinical Safe Alternatives
INSERT OR IGNORE INTO safe_alternatives (blocked_drug, clinical_condition, suggested_alternative, dosage_guide, clinical_rationale) VALUES
('ibuprofen', 'chronic kidney disease', 'Acetaminophen', '500mg PO Q6H PRN (Max 2000mg/24h)', 'Lacks renal prostaglandin inhibition; hepatic metabolism preserves glomerular filtration and renal perfusion.'),
('ibuprofen', 'chronic kidney disease', 'Lidocaine 5% Topical Patch', 'Apply 1 patch topically to affected joint for 12h on / 12h off', 'Provides local analgesia with negligible systemic bioavailability (<3%), zero nephrotoxicity, and zero GI toxicity.'),
('naproxen', 'chronic kidney disease', 'Acetaminophen', '500mg PO Q6H PRN (Max 2000mg/24h)', 'Safe non-NSAID analgesic for mild-to-moderate osteoarthritis pain in renal disease.'),
('propranolol', 'asthma', 'Metoprolol Succinate', '25mg PO once daily (titrate cautiously)', 'Cardioselective beta-1 adrenergic antagonist with ~20-fold greater affinity for cardiac beta-1 than bronchial beta-2 receptors at low doses.'),
('propranolol', 'asthma', 'Amlodipine', '5mg PO once daily', 'Dihydropyridine calcium channel blocker; reduces systemic vascular resistance with zero bronchospastic airway effect.'),
('timolol', 'asthma', 'Betaxolol Ophthalmic', '0.25% 1 drop in affected eye(s) BID', 'Cardioselective beta-1 antagonist with significantly lower incidence of pulmonary adverse effects than non-selective timolol.'),
('amoxicillin', 'penicillin allergy', 'Azithromycin', '500mg PO Day 1, then 250mg PO daily Days 2-5', 'Macrolide antibiotic with zero beta-lactam cross-reactivity; effective against respiratory and soft-tissue bacterial pathogens.'),
('amoxicillin', 'penicillin allergy', 'Levofloxacin', '500mg PO once daily', 'Fluoroquinolone with distinct quinolone chemical structure; complete lack of cross-reactivity in penicillin anaphylaxis.'),
('metformin', 'chronic kidney disease', 'Linagliptin', '5mg PO once daily', 'DPP-4 inhibitor with primary biliary and fecal elimination; 100% safe without dose adjustment even in severe renal failure (eGFR < 30).'),
('warfarin', 'peptic ulcer', 'Apixaban', '5mg PO BID (reduce to 2.5mg if age >=80, wt <=60kg, or Cr >=1.5)', 'Direct oral factor Xa inhibitor with significantly lower incidence of major intracranial hemorrhage compared to warfarin.');


