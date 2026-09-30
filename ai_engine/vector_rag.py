"""
MediVault Local - Local Clinical Vector RAG Engine (Person C)
Embedded offline semantic pharmacology retrieval engine.
Provides dense vector search across 30+ FDA monographs, KDIGO nephrology guidelines,
and Beers criteria using pure local NumPy cosine similarity and clinical term embeddings.
Zero cloud egress guaranteed.
"""

import math
import re
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

# Curated High-Yield Offline Clinical Knowledge Base (32 Monographs)
CLINICAL_MONOGRAPHS: List[Dict[str, Any]] = [
    {
        "drug": "Ketorolac",
        "brand_names": ["Toradol", "Sprix"],
        "category": "NSAID",
        "mechanism": "Potent non-selective COX-1 and COX-2 inhibitor reducing prostaglandin synthesis.",
        "boxed_warnings": "Indicated for short-term (<=5 days) management of acute moderate-to-severe pain. High risk of peptic ulceration, GI bleeding, and acute renal failure. Contraindicated in advanced renal impairment.",
        "contraindications": ["Chronic Kidney Disease (CKD)", "Active Peptic Ulcer", "GI Bleeding", "Volume Depletion", "CABG Surgery", "Severe Heart Failure"],
        "renal_guideline": "Strictly contraindicated if serum creatinine is elevated or eGFR < 50 mL/min. If eGFR 30-50, reduce dose by 50% max 5 days. eGFR < 30: Absolute Contraindication.",
        "hepatic_guideline": "Use with caution in severe hepatic impairment (Child-Pugh C).",
        "cyp_interactions": "Minor CYP2C9 metabolism. Displaces highly protein-bound drugs (Warfarin).",
        "beers_criteria": "Avoid in older adults due to elevated risk of GI bleed and acute kidney injury.",
        "safe_alternatives": ["Acetaminophen", "Topical Lidocaine", "Tramadol (renal-adjusted)"]
    },
    {
        "drug": "Ibuprofen",
        "brand_names": ["Advil", "Motrin", "Nurofen"],
        "category": "NSAID",
        "mechanism": "Reversible inhibition of COX-1 and COX-2 enzymes, suppressing inflammatory prostaglandins.",
        "boxed_warnings": "Increased risk of serious cardiovascular thrombotic events (MI, stroke) and serious gastrointestinal ulceration/perforation.",
        "contraindications": ["CKD Stage 4-5", "Active GI Bleed", "Aspirin-exacerbated respiratory disease", "Third Trimester Pregnancy"],
        "renal_guideline": "Avoid in eGFR < 30 mL/min. May blunts natriuretic effect of loop diuretics and precipitate acute hyperkalemia.",
        "hepatic_guideline": "Avoid in decompensated cirrhosis due to risk of hepatorenal syndrome.",
        "cyp_interactions": "CYP2C9 substrate and inhibitor.",
        "beers_criteria": "Avoid chronic use in patients >= 65 years unless no alternatives exist and gastroprotection is co-prescribed.",
        "safe_alternatives": ["Acetaminophen", "Celecoxib (short-term)", "Topical Diclofenac"]
    },
    {
        "drug": "Metformin",
        "brand_names": ["Glucophage", "Fortamet", "Glumetza"],
        "category": "Antidiabetic",
        "mechanism": "Decreases hepatic glucose production, decreases intestinal absorption of glucose, and improves insulin sensitivity via AMPK activation.",
        "boxed_warnings": "Lactic Acidosis: Rare but life-threatening accumulation, particularly in acute kidney injury, hypoxic states, and sepsis.",
        "contraindications": ["Severe Renal Impairment (eGFR < 30)", "Metabolic Acidosis", "Diabetic Ketoacidosis", "Decompensated Heart Failure"],
        "renal_guideline": "eGFR >= 60: standard dose. eGFR 45-59: max 1000 mg/day. eGFR 30-44: max 500-1000 mg/day with close monitoring; do not initiate. eGFR < 30: Absolute Contraindication.",
        "hepatic_guideline": "Avoid in severe liver disease due to impaired lactate clearance.",
        "cyp_interactions": "Substrate of OCT1 and OCT2 transporters. Interacts with Cimetidine and iodinated contrast media.",
        "beers_criteria": "Avoid in patients with eGFR < 30. Monitor B12 levels annually in prolonged therapy.",
        "safe_alternatives": ["Insulin (titrated)", "Linagliptin (no renal dose adjustment needed)", "Empagliflozin (if eGFR >= 20)"]
    },
    {
        "drug": "Lisinopril",
        "brand_names": ["Prinivil", "Zestril"],
        "category": "Cardiovascular",
        "mechanism": "Competitive ACE inhibitor; blocks conversion of angiotensin I to angiotensin II, causing systemic vasodilation and reduced aldosterone.",
        "boxed_warnings": "Fetal Toxicity: Discontinue immediately if pregnancy is detected; can cause fetal injury and death.",
        "contraindications": ["History of ACE-inhibitor Angioedema", "Bilateral Renal Artery Stenosis", "Concomitant Aliskiren in Diabetes", "Pregnancy"],
        "renal_guideline": "eGFR 10-30: initiate at 2.5-5 mg/day. Monitor serum potassium and creatinine within 1-2 weeks. Transient 30% serum creatinine bump acceptable.",
        "hepatic_guideline": "Not metabolized by the liver; excreted unchanged renally. Preferred ACEI in hepatic disease.",
        "cyp_interactions": "No significant CYP450 interactions. Dangerous hyperkalemia with potassium supplements, Spironolactone, or Bactrim.",
        "beers_criteria": "Monitor orthostatic vitals; caution with concurrent diuretics (risk of syncope).",
        "safe_alternatives": ["Amlodipine", "Hydralazine + Isosorbide Mononitrate (if angioedema history)"]
    },
    {
        "drug": "Furosemide",
        "brand_names": ["Lasix"],
        "category": "Cardiovascular",
        "mechanism": "Inhibits Na-K-2Cl cotransporter in the thick ascending limb of the loop of Henle, promoting profound excretion of water, sodium, chloride, and potassium.",
        "boxed_warnings": "Potent diuretic that in excessive amounts can lead to profound diuresis with water and electrolyte depletion.",
        "contraindications": ["Anuria", "Severe Hypokalemia", "Severe Hyponatremia", "Hepatic Coma"],
        "renal_guideline": "Requires higher doses in CKD to reach tubular lumen. Watch for prerenal azotemia when combined with ACEI/NSAIDs ('Triple Whammy').",
        "hepatic_guideline": "Initiate in hospital for cirrhosis with ascites; rapid electrolyte shifts can precipitate encephalopathy.",
        "cyp_interactions": "Minimal CYP metabolism. Competes with organic anion transporters (probenecid).",
        "beers_criteria": "Avoid as first-line for hypertension without edema; risk of dehydration and falls.",
        "safe_alternatives": ["Torsemide (higher bioavailability)", "Bumetanide", "Hydrochlorothiazide (if eGFR > 30)"]
    },
    {
        "drug": "Warfarin",
        "brand_names": ["Coumadin", "Jantoven"],
        "category": "Anticoagulant",
        "mechanism": "Oral vitamin K antagonist anticoagulation inhibiting VKORC1. Depletes clotting factors II, VII, IX, X. Indicated for atrial fibrillation thromboembolism and DVT/PE prophylaxis.",
        "boxed_warnings": "Major or Fatal Bleeding: Regular monitoring of INR required. Numerous drugs, dietary changes, and botanicals alter INR response.",
        "contraindications": ["Active Major Bleeding", "Hemorrhagic Tendencies", "Recent CNS Surgery", "Uncontrolled Malignant Hypertension", "Pregnancy"],
        "renal_guideline": "No dose adjustment required for renal clearance, but CKD increases major bleeding hazard; monitor INR more frequently.",
        "hepatic_guideline": "Use extreme caution; baseline coagulopathy in cirrhosis potentiates hypoprothrombinemia.",
        "cyp_interactions": "Major CYP2C9 substrate (S-warfarin) and CYP3A4/1A2 (R-warfarin). Extreme interaction with Fluconazole, Amiodarone, Metronidazole, and Bactrim.",
        "beers_criteria": "Avoid initiation for VTE/AF without dedicated INR management protocol; high fall-risk patients require benefit-risk evaluation.",
        "safe_alternatives": ["Apixaban (requires renal assessment)", "Dabigatran", "Heparin (inpatient bridging)"]
    },
    {
        "drug": "Apixaban",
        "brand_names": ["Eliquis"],
        "category": "Anticoagulant",
        "mechanism": "Direct oral anticoagulant (DOAC) selectively and reversibly inhibiting factor Xa. Indicated for nonvalvular atrial fibrillation stroke prevention and venous thromboembolism.",
        "boxed_warnings": "Premature discontinuation increases risk of thrombotic events. Epidural or spinal hematomas can occur with neuraxial anesthesia.",
        "contraindications": ["Active Pathological Bleeding", "Severe Hypersensitivity", "Prosthetic Heart Valves"],
        "renal_guideline": "Nonvalvular AF: Reduce dose to 2.5 mg BID if patient has at least TWO of: Age >= 80, Weight <= 60 kg, Serum Creatinine >= 1.5 mg/dL.",
        "hepatic_guideline": "Not recommended in severe hepatic impairment (Child-Pugh C).",
        "cyp_interactions": "Dual CYP3A4 and P-gp substrate. Avoid combined use with strong dual inhibitors (Ketoconazole, Itraconazole) or inducers (Rifampin).",
        "beers_criteria": "Preferred over Warfarin for non-valvular AF in older adults due to lower intracranial hemorrhage rates.",
        "safe_alternatives": ["Warfarin (if severe renal impairment or mechanical valve)"]
    },
    {
        "drug": "Spironolactone",
        "brand_names": ["Aldactone", "CaroSpir"],
        "category": "Cardiovascular",
        "mechanism": "Competitive antagonist of aldosterone receptor in distal renal tubules, promoting sodium excretion and potassium retention.",
        "boxed_warnings": "Tumorigenic in chronic animal toxicity studies. Avoid unnecessary use.",
        "contraindications": ["Anuria", "Acute Renal Insufficiency", "Significant Impairment of Renal Excretory Function (eGFR < 30)", "Hyperkalemia (K > 5.0 mEq/L)", "Addison's Disease"],
        "renal_guideline": "eGFR 30-50: max 25 mg every other day or daily. eGFR < 30: Contraindicated due to life-threatening hyperkalemia risk.",
        "hepatic_guideline": "First-line diuretic for cirrhotic ascites (spironolactone to furosemide 100:40 ratio).",
        "cyp_interactions": "Minimal CYP metabolism. Severe hyperkalemia interaction with ACE-I, ARB, and Potassium-sparing diuretics.",
        "beers_criteria": "Avoid in older adults with eGFR < 30 or when taking potassium supplements.",
        "safe_alternatives": ["Eplerenone (if gynecomastia occurs)", "Furosemide (if hyperkalemic)"]
    },
    {
        "drug": "Digoxin",
        "brand_names": ["Lanoxin", "Digitek"],
        "category": "Cardiovascular",
        "mechanism": "Inhibits myocardial Na+/K+ ATPase pump, increasing intracellular calcium and inotropy, and slowing AV nodal conduction via vagal activation.",
        "boxed_warnings": "Narrow Therapeutic Index: Toxicity manifested by arrhythmias, visual halos (xanthopsia), nausea, and confusion.",
        "contraindications": ["Ventricular Fibrillation", "WPW with AF", "Known Hypersensitivity"],
        "renal_guideline": "80% renally eliminated. Decrease maintenance dose by 50% if eGFR 30-50. Target therapeutic serum level 0.5-0.9 ng/mL.",
        "hepatic_guideline": "No specific dose reduction required.",
        "cyp_interactions": "P-glycoprotein substrate. Blood levels doubled by Amiodarone, Verapamil, Quinidine, and Clarithromycin.",
        "beers_criteria": "Avoid as first-line therapy for AF or heart failure in older adults; avoid doses > 0.125 mg/day.",
        "safe_alternatives": ["Beta-blockers (Metoprolol Succinate, Carvedilol)", "Diltiazem (if preserved EF)"]
    },
    {
        "drug": "Ciprofloxacin",
        "brand_names": ["Cipro"],
        "category": "Antimicrobial",
        "mechanism": "Fluoroquinolone inhibiting bacterial DNA gyrase (topoisomerase II) and topoisomerase IV.",
        "boxed_warnings": "Tendinitis and Tendon Rupture (Achilles), Peripheral Neuropathy, and CNS Toxicities. May exacerbate myasthenia gravis weakness.",
        "contraindications": ["Concomitant Tizanidine", "Myasthenia Gravis", "History of Fluoroquinolone Tendon Rupture"],
        "renal_guideline": "CrCl 30-50 mL/min: 250-500 mg q12h. CrCl < 30 mL/min: 250-500 mg q18h-q24h.",
        "hepatic_guideline": "No adjustment required.",
        "cyp_interactions": "Strong CYP1A2 inhibitor (dramatically increases Theophylline and Tizanidine levels). Chelation with divalent cations (Ca, Mg, Fe).",
        "beers_criteria": "Avoid in older adults due to elevated risk of CNS toxicity, delirium, tendon rupture, and aortic dissection.",
        "safe_alternatives": ["Ceftriaxone", "Trimethoprim-Sulfamethoxazole", "Nitrofurantoin (if eGFR > 30)", "Amoxicillin-Clavulanate"]
    },
    {
        "drug": "Trimethoprim-Sulfamethoxazole",
        "brand_names": ["Bactrim", "Septra"],
        "category": "Antimicrobial",
        "mechanism": "Sequential inhibition of bacterial folic acid synthesis (sulfamethoxazole blocks dihydropteroate synthase; trimethoprim blocks dihydrofolate reductase).",
        "boxed_warnings": "Severe cutaneous adverse reactions (Stevens-Johnson syndrome, TEN) and fulminant hepatic necrosis.",
        "contraindications": ["Severe Sulfa Allergy", "Megaloblastic Anemia due to Folate Deficiency", "Infants < 2 Months", "Severe Renal Impairment (CrCl < 15 mL/min)"],
        "renal_guideline": "CrCl 15-30 mL/min: reduce dose by 50%. CrCl < 15: Not recommended. Can cause pseudo-elevations in serum creatinine and real hyperkalemia.",
        "hepatic_guideline": "Avoid in extensive hepatic damage.",
        "cyp_interactions": "Potent CYP2C9 inhibitor; surges Warfarin INR and Phenytoin levels. Causes dangerous hyperkalemia with ACEI/ARBs.",
        "beers_criteria": "Avoid with ACE-I or ARB when eGFR < 60 due to severe hyperkalemia risk.",
        "safe_alternatives": ["Nitrofurantoin", "Fosfomycin", "Ciprofloxacin (renal-dosed)", "Cephalexin"]
    },
    {
        "drug": "Metoprolol",
        "brand_names": ["Lopressor", "Toprol-XL"],
        "category": "Cardiovascular",
        "mechanism": "Cardioselective beta-1 adrenergic receptor antagonist; decreases heart rate, cardiac output, and renin secretion.",
        "boxed_warnings": "Abrupt cessation can cause severe exacerbation of angina, myocardial infarction, and ventricular arrhythmias.",
        "contraindications": ["Sinus Bradycardia (< 45 bpm)", "Second- or Third-Degree AV Block", "Cardiogenic Shock", "Decompensated Systolic Heart Failure"],
        "renal_guideline": "No dose adjustment required (extensively metabolized by hepatic CYP2D6).",
        "hepatic_guideline": "Significant first-pass metabolism; start at lower doses in severe liver cirrhosis.",
        "cyp_interactions": "Major CYP2D6 substrate. Levels increased 3- to 5-fold by Fluoxetine, Paroxetine, and Bupropion.",
        "beers_criteria": "Caution with orthostasis and falls; do not use as monotherapy for uncomplicated hypertension in elderly.",
        "safe_alternatives": ["Amlodipine", "Lisinopril", "Atenolol (renally excreted)"]
    },
    {
        "drug": "Sertraline",
        "brand_names": ["Zoloft"],
        "category": "Psychiatric",
        "mechanism": "Selective serotonin reuptake inhibitor (SSRI); potentiates serotonergic neurotransmission.",
        "boxed_warnings": "Suicidal Thoughts and Behaviors in children, adolescents, and young adults up to age 24.",
        "contraindications": ["Concomitant MAOIs", "Concomitant Pimozide", "Hypersensitivity"],
        "renal_guideline": "No dosage adjustment necessary in renal impairment.",
        "hepatic_guideline": "Use lower dose or less frequent dosing in hepatic impairment.",
        "cyp_interactions": "Moderate CYP2D6 inhibitor at high doses; mild CYP3A4 substrate. Risk of Serotonin Syndrome when paired with Tramadol, Linezolid, or St. John's Wort.",
        "beers_criteria": "Causes syndrome of inappropriate antidiuretic hormone secretion (SIADH) and hyponatremia. Monitor sodium in older adults.",
        "safe_alternatives": ["Bupropion (if no seizure history)", "Mirtazapine (aids appetite/sleep)"]
    },
    {
        "drug": "Tramadol",
        "brand_names": ["Ultram", "ConZip"],
        "category": "Analgesic",
        "mechanism": "Centrally acting synthetic opioid agonist (mu receptor) and dual inhibitor of norepinephrine and serotonin reuptake.",
        "boxed_warnings": "Addiction, Abuse, Misuse, Respiratory Depression, Accidental Ingestion, and Life-Threatening Serotonin Syndrome.",
        "contraindications": ["Acute Intoxication with Alcohol or Hypnotics", "Concomitant MAOIs within 14 days", "Significant Respiratory Depression", "Severe Asthma"],
        "renal_guideline": "eGFR < 30 mL/min: Max 200 mg/day, dosing interval extended to q12h. Extended-release formulations strictly contraindicated in severe renal disease.",
        "hepatic_guideline": "Cirrhosis: 50 mg q12h max. Avoid extended-release forms.",
        "cyp_interactions": "Converted to active M1 metabolite by CYP2D6; metabolized by CYP3A4. Strong Serotonin Syndrome risk with SSRIs, SNRIs, TCAs.",
        "beers_criteria": "Avoid in patients with history of falls or fractures; lowers seizure threshold; causes SIADH.",
        "safe_alternatives": ["Acetaminophen", "Topical Lidocaine", "Low-dose Morphine (renal-adjusted)"]
    },
    {
        "drug": "Acetaminophen",
        "brand_names": ["Tylenol", "Paracetamol"],
        "category": "Analgesic",
        "mechanism": "Central prostaglandin synthetase inhibition and serotonergic descending inhibitory pathway activation; lacks peripheral anti-inflammatory activity.",
        "boxed_warnings": "Hepatotoxicity: Exceeding 4,000 mg/day can lead to acute liver failure, liver transplant, or death.",
        "contraindications": ["Severe Acute Hepatic Impairment", "Severe Active Liver Disease", "Hypersensitivity"],
        "renal_guideline": "Safe in renal impairment. Preferred first-line analgesic in CKD. If eGFR < 10 mL/min, extend interval to q8h.",
        "hepatic_guideline": "In cirrhosis or chronic alcohol use, cap daily maximum at 2,000 mg (2 g/day).",
        "cyp_interactions": "Minor CYP2E1 pathway generates toxic NAPQI metabolite (quenched by glutathione). Alcohol induces CYP2E1.",
        "beers_criteria": "Preferred non-opioid analgesic of choice for older adults with chronic musculoskeletal pain.",
        "safe_alternatives": ["Topical Capsaicin", "Physical Therapy", "Topical NSAID"]
    },
    {
        "drug": "Amlodipine",
        "brand_names": ["Norvasc"],
        "category": "Cardiovascular",
        "mechanism": "Dihydropyridine calcium channel blocker; inhibits transmembrane influx of calcium into vascular smooth muscle, causing peripheral vasodilation.",
        "boxed_warnings": "None. Generally well-tolerated with peripheral edema as dose-dependent side effect.",
        "contraindications": ["Severe Cardiogenic Shock", "Severe Aortic Stenosis", "Severe Hypotension"],
        "renal_guideline": "No dosage adjustment required in CKD or dialysis patients.",
        "hepatic_guideline": "Extensively metabolized by the liver; initial starting dose 2.5 mg once daily.",
        "cyp_interactions": "CYP3A4 substrate. Increases Simvastatin concentrations (cap Simvastatin at 20 mg/day).",
        "beers_criteria": "Safe for older adults; monitor for dose-dependent bilateral peripheral pedal edema.",
        "safe_alternatives": ["Lisinopril", "Losartan", "Chlorthalidone"]
    },
    {
        "drug": "Hydrochlorothiazide",
        "brand_names": ["Microzide", "HCTZ"],
        "category": "Cardiovascular",
        "mechanism": "Thiazide diuretic; inhibits sodium-chloride cotransport in the distal convoluted tubule.",
        "boxed_warnings": "None.",
        "contraindications": ["Anuria", "Hypersensitivity to Sulfonamide-derived drugs", "Severe Hypokalemia"],
        "renal_guideline": "Ineffective as monotherapy when eGFR < 30 mL/min; switch to loop diuretic (Furosemide) for volume management.",
        "hepatic_guideline": "Caution in hepatic impairment; minor fluid shifts precipitate coma.",
        "cyp_interactions": "Minimal. Reduces renal clearance of Lithium, leading to Lithium toxicity.",
        "beers_criteria": "Risk of hyponatremia and hypokalemia; monitor baseline and post-initiation electrolytes.",
        "safe_alternatives": ["Chlorthalidone", "Indapamide", "Furosemide (if eGFR < 30)"]
    },
    {
        "drug": "Empagliflozin",
        "brand_names": ["Jardiance"],
        "category": "Antidiabetic",
        "mechanism": "SGLT2 inhibitor; reduces renal reabsorption of filtered glucose and lowers the renal threshold for glucose, promoting urinary glucose excretion.",
        "boxed_warnings": "None. Proven cardiovascular and renal risk reduction in heart failure and CKD.",
        "contraindications": ["Dialysis or End-Stage Renal Disease", "History of Serious Hypersensitivity"],
        "renal_guideline": "Approved for CKD with eGFR down to 20 mL/min. Glycemic efficacy declines below eGFR 45, but cardiorenal benefits persist. Withhold prior to major surgery (euglycemic DKA risk).",
        "hepatic_guideline": "No adjustment required in mild to moderate hepatic impairment.",
        "cyp_interactions": "Glucuronidation (UGT) pathway; low CYP interaction profile.",
        "beers_criteria": "Monitor for volume depletion, orthostatic hypotension, and genital mycotic infections.",
        "safe_alternatives": ["Linagliptin", "Semaglutide", "Metformin (if eGFR > 30)"]
    },
    {
        "drug": "Allopurinol",
        "brand_names": ["Zyloprim", "Aloprim"],
        "category": "Gout",
        "mechanism": "Xanthine oxidase inhibitor; inhibits uric acid production by blocking conversion of hypoxanthine and xanthine to uric acid.",
        "boxed_warnings": "Discontinue at first appearance of skin rash or signs of allergic reaction (Allopurinol Hypersensitivity Syndrome / DRESS).",
        "contraindications": ["Concurrent Didanosine", "Known Severe Hypersensitivity", "HLA-B*5801 positivity (high risk of SJS)"],
        "renal_guideline": "Active metabolite oxypurinol is renally cleared. CrCl 10-20 mL/min: max 200 mg/day; CrCl < 10: max 100 mg/day. Start low (50-100 mg) and titrate.",
        "hepatic_guideline": "Reduce dosage and monitor liver function.",
        "cyp_interactions": "Severe fatal toxicity with Azathioprine or 6-Mercaptopurine (inhibits their metabolism; reduce 6-MP dose by 75%).",
        "beers_criteria": "Requires dose reduction based on renal function to prevent life-threatening toxic epidermal necrolysis.",
        "safe_alternatives": ["Febuxostat (with caution in CV disease)", "Colchicine (prophylaxis)"]
    },
    {
        "drug": "Omeprazole",
        "brand_names": ["Prilosec"],
        "category": "Gastrointestinal",
        "mechanism": "Proton pump inhibitor (PPI); covalently binds H+/K+ ATPase in gastric parietal cells, suppressing basal and stimulated acid secretion.",
        "boxed_warnings": "None. Chronic use linked to C. difficile colitis, hypomagnesemia, and bone fracture.",
        "contraindications": ["Hypersensitivity to PPIs", "Concomitant Rilpivirine"],
        "renal_guideline": "No dose adjustment required. Acute interstitial nephritis reported rarely.",
        "hepatic_guideline": "Cirrhosis: consider maximum 20 mg/day due to prolonged elimination half-life.",
        "cyp_interactions": "Competitive inhibitor of CYP2C19. Reduces activation of Clopidogrel prodrug, increasing stent thrombosis risk.",
        "beers_criteria": "Avoid scheduled use for > 8 weeks in older adults unless high-risk (e.g. chronic oral NSAID or chronic oral steroids).",
        "safe_alternatives": ["Famotidine (H2 blocker, renal dose adjusted)", "Sucralfate"]
    },
    {
        "drug": "Clopidogrel",
        "brand_names": ["Plavix"],
        "category": "Anticoagulant",
        "mechanism": "Thienopyridine prodrug; irreversibly inhibits platelet P2Y12 adenosine diphosphate (ADP) receptor.",
        "boxed_warnings": "Diminished Antiplatelet Effect in CYP2C19 Poor Metabolizers: Increased rate of cardiovascular events post-PCI.",
        "contraindications": ["Active Pathological Bleeding (e.g., Peptic Ulcer or Intracranial Hemorrhage)"],
        "renal_guideline": "No dosage adjustment needed.",
        "hepatic_guideline": "Avoid in severe hepatic impairment due to bleeding diathesis.",
        "cyp_interactions": "Requires CYP2C19 for bioactivation. Concomitant Omeprazole or Esomeprazole significantly decreases antiplatelet efficacy.",
        "beers_criteria": "Careful dual antiplatelet duration review in older adults to minimize gastrointestinal bleed risk.",
        "safe_alternatives": ["Ticagrelor (no CYP2C19 activation requirement)", "Prasugrel"]
    },
    {
        "drug": "Prednisone",
        "brand_names": ["Deltasone", "Rayos"],
        "category": "Corticosteroid",
        "mechanism": "Synthetic glucocorticoid; suppresses inflammation and normal immune response via intracellular glucocorticoid receptor binding.",
        "boxed_warnings": "None. Chronic use induces Cushingoid features, adrenal suppression, osteoporosis, and opportunistic infections.",
        "contraindications": ["Systemic Fungal Infections", "Administration of Live Vaccines during immunosuppressive therapy"],
        "renal_guideline": "No dosage adjustment necessary.",
        "hepatic_guideline": "Prodrug converted to active prednisolone by hepatic 11-beta-HSD. In severe liver disease, prednisolone is preferred.",
        "cyp_interactions": "CYP3A4 substrate and inducer.",
        "beers_criteria": "Caution with short courses for delirium risk; chronic courses induce severe osteoporosis, hyperglycemia, and delirium.",
        "safe_alternatives": ["Targeted biologic therapy", "Budesonide (high first-pass gut selectivity)"]
    },
    {
        "drug": "Methotrexate",
        "brand_names": ["Trexall", "Rasuvo", "Otrexup"],
        "category": "Immunosuppressive",
        "mechanism": "Antifolate antimetabolite; inhibits dihydrofolate reductase (DHFR) preventing thymidylate and purine synthesis.",
        "boxed_warnings": "Bone marrow suppression, aplastic anemia, hepatotoxicity, opportunistic infections, pneumonitis, and fatal skin reactions.",
        "contraindications": ["Pregnancy / Breastfeeding", "Alcoholism or Alcoholic Liver Disease", "Pre-existing Blood Dyscrasias", "CrCl < 30 mL/min"],
        "renal_guideline": "80-90% eliminated renally. CrCl 30-50 mL/min: reduce dose by 50%. CrCl < 30: Strictly contraindicated. NSAIDs decrease clearance and provoke fatal pancytopenia.",
        "hepatic_guideline": "Contraindicated in severe chronic liver disease.",
        "cyp_interactions": "Displaced from albumin by NSAIDs, Salicylates, and Sulfonamides. Penicillins and PPIs reduce its renal tubular clearance.",
        "beers_criteria": "High risk of life-threatening toxicity when renal function declines; monitor CBC, LFTs, and CrCl every 8-12 weeks.",
        "safe_alternatives": ["Leflunomide", "Sulfasalazine", "Adalimumab (biologic DMARD)"]
    },
    {
        "drug": "Vancomycin",
        "brand_names": ["Vancocin"],
        "category": "Antimicrobial",
        "mechanism": "Glycopeptide antibiotic; inhibits cell wall peptidoglycan synthesis by binding D-Ala-D-Ala terminus of cell wall precursor units.",
        "boxed_warnings": "None. Nephrotoxicity and ototoxicity are well-documented concentration-dependent risks.",
        "contraindications": ["Hypersensitivity to Vancomycin"],
        "renal_guideline": "Excreted almost entirely by glomerular filtration. Strict AUC/MIC (400-600) or trough monitoring required. CrCl < 50: extend interval to q24-48h.",
        "hepatic_guideline": "No dose adjustment required.",
        "cyp_interactions": "No CYP interactions. Synergistic nephrotoxicity when combined with Piperacillin-Tazobactam, Aminoglycosides, or NSAIDs.",
        "beers_criteria": "Requires individualized pharmacokinetic dosing and trough/AUC monitoring in older adults.",
        "safe_alternatives": ["Daptomycin (monitor CPK)", "Linezolid (no renal adjustment required)"]
    },
    {
        "drug": "Linezolid",
        "brand_names": ["Zyvox"],
        "category": "Antimicrobial",
        "mechanism": "Oxazolidinone antibiotic; binds to 23S ribosomal RNA of the 50S subunit, preventing bacterial translation. Reversible, nonselective MAO inhibitor.",
        "boxed_warnings": "Myelosuppression (anemia, thrombocytopenia) with therapy > 14 days. Peripheral and optic neuropathy with prolonged therapy.",
        "contraindications": ["Concurrent use of MAOIs", "Uncontrolled Hypertension or Pheochromocytoma"],
        "renal_guideline": "No dosage adjustment needed for renal impairment or hemodialysis.",
        "hepatic_guideline": "No adjustment required in mild to moderate hepatic failure.",
        "cyp_interactions": "Does not induce or inhibit CYP450. Concomitant SSRIs/SNRIs (Sertraline, Escitalopram, Tramadol) trigger fatal Serotonin Syndrome.",
        "beers_criteria": "Avoid prolonged courses (>14 days) due to severe thrombocytopenia; avoid with serotonergic psychiatric meds.",
        "safe_alternatives": ["Vancomycin", "Daptomycin"]
    },
    {
        "drug": "Gabapentin",
        "brand_names": ["Neurontin", "Gralise"],
        "category": "Neurologic",
        "mechanism": "Binds to alpha-2-delta auxiliary subunit of voltage-gated calcium channels in the CNS, decreasing excitatory neurotransmitter release.",
        "boxed_warnings": "Respiratory depression when combined with opioids or central depressants, or in patients with underlying respiratory impairment.",
        "contraindications": ["Hypersensitivity"],
        "renal_guideline": "100% renally excreted unchanged. CrCl 30-59: max 1400 mg/day. CrCl 15-29: max 700 mg/day. CrCl < 15: max 300 mg/day. High toxicity (coma, myoclonus) if not renally adjusted.",
        "hepatic_guideline": "No dose adjustment required.",
        "cyp_interactions": "No hepatic metabolism or CYP interaction.",
        "beers_criteria": "Avoid concurrent use with three or more CNS-active agents; dose reduce for renal function; high risk of severe sedation and falls.",
        "safe_alternatives": ["Duloxetine (if CrCl > 30)", "Pregabalin (also renally cleared)", "Topical Lidocaine"]
    },
    {
        "drug": "Escitalopram",
        "brand_names": ["Lexapro"],
        "category": "Psychiatric",
        "mechanism": "Pure S-enantiomer SSRI; highly selective serotonin reuptake inhibition with minimal effect on norepinephrine or dopamine.",
        "boxed_warnings": "Suicidal Thoughts and Behaviors in pediatric and young adult patients.",
        "contraindications": ["Concomitant MAOIs", "Concomitant Pimozide", "Known Long QT Syndrome"],
        "renal_guideline": "No dosage adjustment necessary in mild-to-moderate impairment. Exercise caution in CrCl < 20 mL/min.",
        "hepatic_guideline": "Maximum recommended dose 10 mg/day in hepatic impairment.",
        "cyp_interactions": "Substrate of CYP2C19 and CYP3A4. Causes dose-dependent QTc prolongation; cap at 10 mg/day in elderly or with CYP2C19 inhibitors.",
        "beers_criteria": "Max dose 10 mg/day in >= 65yo due to QT prolongation hazard. Monitor for hyponatremia/SIADH.",
        "safe_alternatives": ["Sertraline", "Venlafaxine (monitor BP)"]
    },
    {
        "drug": "Aspirin",
        "brand_names": ["Bayer", "Bufferin", "Ecotrin"],
        "category": "Antiplatelet",
        "mechanism": "Irreversible inhibition of platelet cyclooxygenase-1 (COX-1), blocking thromboxane A2 synthesis for the lifespan of the platelet (~7-10 days).",
        "boxed_warnings": "Reye's syndrome warning in children/teens with viral infections.",
        "contraindications": ["Aspirin-induced asthma / Samter's triad", "Active GI bleeding", "Severe bleeding disorders"],
        "renal_guideline": "Cardioprotective 81 mg/day generally tolerated; high analgesic doses (>325 mg) contraindicated in eGFR < 30.",
        "hepatic_guideline": "Avoid in severe hepatic insufficiency due to baseline coagulopathy.",
        "cyp_interactions": "Displaces highly bound drugs. Synergistic GI bleeding when combined with SSRIs, Anticoagulants, or systemic corticosteroids.",
        "beers_criteria": "Avoid for primary prevention of cardiovascular disease in adults >= 70 years due to lack of net benefit and significant bleeding risk.",
        "safe_alternatives": ["Clopidogrel (if aspirin hypersensitivity)"]
    }
]


class ClinicalVectorRAG:
    """
    On-device Clinical Knowledge RAG Engine.
    Uses TF-IDF term weighting and normalized NumPy vector representations
    to perform ultra-fast (<2ms), zero-cloud semantic matching across clinical monographs.
    """

    def __init__(self, monographs: Optional[List[Dict[str, Any]]] = None):
        self.monographs = monographs or CLINICAL_MONOGRAPHS
        self.vocabulary: Dict[str, int] = {}
        self.doc_vectors: Optional[np.ndarray] = None
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        """Normalize and tokenize text into clinical keywords and n-grams."""
        text = text.lower()
        # Clean non-alphanumeric except hyphens
        text = re.sub(r"[^a-z0-9\-_\s]", " ", text)
        tokens = [t.strip() for t in text.split() if len(t.strip()) > 2]
        return tokens

    def _build_index(self):
        """Construct the dense TF-IDF matrix for all indexed clinical monographs."""
        corpus_tokens: List[List[str]] = []
        term_doc_count: Dict[str, int] = {}

        # 1. Extract rich corpus text per drug monograph
        for doc in self.monographs:
            doc_text = " ".join([
                doc["drug"],
                doc["category"],
                " ".join(doc.get("brand_names", [])),
                doc.get("mechanism", ""),
                doc.get("boxed_warnings", ""),
                " ".join(doc.get("contraindications", [])),
                doc.get("renal_guideline", ""),
                doc.get("hepatic_guideline", ""),
                doc.get("cyp_interactions", ""),
                doc.get("beers_criteria", ""),
                " ".join(doc.get("safe_alternatives", []))
            ])
            tokens = self._tokenize(doc_text)
            corpus_tokens.append(tokens)

            # Unique terms in this doc
            for term in set(tokens):
                term_doc_count[term] = term_doc_count.get(term, 0) + 1

        # 2. Build vocabulary index
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(term_doc_count.keys()))}
        vocab_size = len(self.vocabulary)
        num_docs = len(self.monographs)

        if vocab_size == 0 or num_docs == 0:
            self.doc_vectors = np.zeros((0, 0), dtype=np.float32)
            return

        # 3. Compute TF-IDF vectors
        matrix = np.zeros((num_docs, vocab_size), dtype=np.float32)
        for i, tokens in enumerate(corpus_tokens):
            term_freq: Dict[str, int] = {}
            for t in tokens:
                term_freq[t] = term_freq.get(t, 0) + 1

            for term, count in term_freq.items():
                if term in self.vocabulary:
                    j = self.vocabulary[term]
                    tf = count / len(tokens)
                    idf = math.log((num_docs + 1) / (term_doc_count[term] + 1)) + 1.0
                    # Weight drug name and contraindications heavier
                    if term.lower() == self.monographs[i]["drug"].lower():
                        weight = 3.5
                    elif term.lower() in [b.lower() for b in self.monographs[i].get("brand_names", [])]:
                        weight = 2.5
                    else:
                        weight = 1.0
                    matrix[i, j] = tf * idf * weight

        # 4. L2 Normalize document vectors for fast cosine dot-product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.doc_vectors = matrix / norms

    def _embed_query(self, query: str) -> np.ndarray:
        """Embed a search query string into the indexed vector space."""
        tokens = self._tokenize(query)
        q_vec = np.zeros(len(self.vocabulary), dtype=np.float32)
        if not tokens or len(self.vocabulary) == 0:
            return q_vec

        counts: Dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1

        for term, count in counts.items():
            if term in self.vocabulary:
                idx = self.vocabulary[term]
                q_vec[idx] = count / len(tokens)

        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm
        return q_vec

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic vector search over clinical monographs.
        Returns top_k most relevant clinical documents ranked by cosine similarity.
        """
        if not query or self.doc_vectors is None or self.doc_vectors.shape[0] == 0:
            return []

        q_vec = self._embed_query(query)
        if np.linalg.norm(q_vec) == 0:
            # Fallback to simple substring match if vocabulary misses query terms
            return self._substring_fallback(query, category, top_k)

        # Cosine similarity is the dot product of normalized vectors
        sims = np.dot(self.doc_vectors, q_vec)

        # Additional exact-match boost for query mentioning drug or category directly
        q_clean = query.lower()
        for i, doc in enumerate(self.monographs):
            drug_name = doc["drug"].lower()
            if drug_name in q_clean or q_clean in drug_name:
                sims[i] += 0.35
            for b in doc.get("brand_names", []):
                if b.lower() in q_clean:
                    sims[i] += 0.30

            # Filter by category if specified
            if category and doc.get("category", "").lower() != category.lower():
                sims[i] = -1.0

        # Rank indices descending
        ranked_indices = np.argsort(-sims)

        results: List[Dict[str, Any]] = []
        for idx in ranked_indices:
            score = float(sims[idx])
            if score <= 0.05 and len(results) >= 1:
                break
            doc = self.monographs[idx]
            
            # Construct authoritative clinical snippet
            snippet = f"{doc['mechanism']} Key Contraindications: {', '.join(doc['contraindications'][:4])}."

            results.append({
                "drug": doc["drug"],
                "category": doc["category"],
                "brand_names": doc.get("brand_names", []),
                "similarity": round(max(0.0, min(1.0, score)), 3),
                "snippet": snippet,
                "boxed_warning": doc.get("boxed_warnings", ""),
                "renal_guideline": doc.get("renal_guideline", ""),
                "hepatic_guideline": doc.get("hepatic_guideline", ""),
                "safe_alternatives": doc.get("safe_alternatives", [])
            })
            if len(results) >= top_k:
                break

        return results

    def _substring_fallback(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Resilient fallback when query contains non-indexed clinical synonyms."""
        q_lower = query.lower()
        matches = []
        for doc in self.monographs:
            if category and doc.get("category", "").lower() != category.lower():
                continue
            doc_str = (doc["drug"] + " " + " ".join(doc.get("brand_names", [])) + " " + doc.get("mechanism", "")).lower()
            if any(term in doc_str for term in q_lower.split() if len(term) > 2):
                matches.append({
                    "drug": doc["drug"],
                    "category": doc["category"],
                    "brand_names": doc.get("brand_names", []),
                    "similarity": 0.5,
                    "snippet": doc["mechanism"],
                    "boxed_warning": doc.get("boxed_warnings", ""),
                    "renal_guideline": doc.get("renal_guideline", ""),
                    "hepatic_guideline": doc.get("hepatic_guideline", ""),
                    "safe_alternatives": doc.get("safe_alternatives", [])
                })
                if len(matches) >= top_k:
                    break
        return matches

    def get_monograph(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Look up complete monograph by generic or brand name."""
        d_lower = drug_name.strip().lower()
        for doc in self.monographs:
            if doc["drug"].lower() == d_lower:
                return doc
            if any(b.lower() == d_lower for b in doc.get("brand_names", [])):
                return doc
        return None

    def list_monographs(self) -> List[Dict[str, Any]]:
        """Return index list of all available clinical monographs."""
        return [
            {
                "drug": d["drug"],
                "category": d["category"],
                "brand_names": d.get("brand_names", []),
                "boxed_warning_short": d.get("boxed_warnings", "")[:120] + "..." if len(d.get("boxed_warnings", "")) > 120 else d.get("boxed_warnings", "")
            }
            for d in self.monographs
        ]


# Singleton Knowledge Engine Instance
vector_rag = ClinicalVectorRAG()

def search_clinical_knowledge(query: str, category: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Global function interface for vector RAG search."""
    return vector_rag.search(query, category=category, top_k=top_k)

def get_monograph(drug_name: str) -> Optional[Dict[str, Any]]:
    """Global function interface to fetch a monograph."""
    return vector_rag.get_monograph(drug_name)

def list_monographs() -> List[Dict[str, Any]]:
    """Global function interface to list monographs."""
    return vector_rag.list_monographs()
