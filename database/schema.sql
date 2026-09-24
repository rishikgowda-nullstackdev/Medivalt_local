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

-- 7. Cryptographic Local Audit Trail (HIPAA Security Rule § 164.312(b))
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    patient_hash TEXT NOT NULL,
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
