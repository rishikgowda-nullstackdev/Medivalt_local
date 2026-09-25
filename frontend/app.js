/**
 * MediVault Local - Doctor Dashboard Frontend Controller
 * Connects UI to local FastAPI endpoints (127.0.0.1:8000) with zero external network calls.
 */

let currentIntakeMode = 'demo';
let currentPatientId = 'PT-101';
let currentUploadedRecord = null;
let currentReviewEventId = null;

// Sample raw note for demonstration
const SAMPLE_DISCHARGE_NOTE = `ST. JUDE MEMORIAL HOSPITAL — INPATIENT DISCHARGE SUMMARY
PATIENT NAME: Robert Vance | DOB: 08/14/1958 | MRN: 4892014
SSN: 111-22-3333 | PHONE: (555) 432-8765
ATTENDING: Dr. Jonathan Miller, MD

DISCHARGE DIAGNOSES:
1. Stage 3 Chronic Kidney Disease (CKD) — baseline serum creatinine 2.1 mg/dL, baseline eGFR 38 mL/min/1.73m2
2. Essential Hypertension
3. Type 2 Diabetes Mellitus

CURRENT MEDICATIONS:
- Lisinopril 20mg PO daily
- Metformin 500mg PO BID
- Amlodipine 5mg PO daily

ALLERGIES:
- Sulfonamides (anaphylactic urticaria)
- Penicillin (skin rash)

CHIEF COMPLAINT:
Severe bilateral knee osteoarthritis flare-up. Inquiring regarding NSAID prescription for pain management.`;

// ---------------------------------------------------------------------------
// Lifecycle & Initialization
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    initPatientSelector();
    loadPatientProfile(currentPatientId);
    refreshAuditTrail();
    setupFileDropZone();
    checkAiStatus();
    loadAuthProfile();
    loadHospitalsAndDemoDoctors();

    // Listen to patient dropdown changes (both Screen 1 header & Screen 2 intake tab)
    const selectEl = document.getElementById("patient-select");
    if (selectEl) {
        selectEl.addEventListener("change", (e) => {
            selectPatient(e.target.value);
        });
    }
    const selectHeaderEl = document.getElementById("patient-select-header");
    if (selectHeaderEl) {
        selectHeaderEl.addEventListener("change", (e) => {
            selectPatient(e.target.value);
        });
    }
});

// ---------------------------------------------------------------------------
// Drag & Drop File Upload Handler
// ---------------------------------------------------------------------------
function setupFileDropZone() {
    const dropZone = document.getElementById("file-drop-zone");
    const fileInput = document.getElementById("file-upload-input");

    if (!dropZone || !fileInput) return;

    dropZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add("drop-zone--over");
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove("drop-zone--over");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append("file", file);

    const dropZone = document.getElementById("file-drop-zone");
    dropZone.innerHTML = `<p class="text-xs text-teal-400 font-mono"><i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Ingesting & Redacting ${file.name}...</p>`;

    try {
        const res = await fetch("/api/upload-record", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Upload failed");
        }

        const data = await res.json();
        currentUploadedRecord = data;

        // Set raw text into textarea
        document.getElementById("raw-note-input").value = data.redacted_text;

        // Update Patient Card with extracted entities & biomarkers
        renderPatientCard(
            { patient_name: `Ingested: ${file.name}`, patient_id: data.patient_token, age: "Extracted", gender: "Extracted" },
            data.entities.diagnosed_conditions.map(c => ({ condition_name: c })),
            data.entities.current_medications.map(m => ({ medication_name: m, dosage: "" })),
            data.entities.allergies.map(a => ({ allergen: a, reaction: "Extracted" })),
            data.entities.biomarkers || data.entities.clinical_labs
        );

        dropZone.innerHTML = `
            <i class="fa-solid fa-file-circle-check text-emerald-400 text-xl mb-1"></i>
            <p class="text-xs text-emerald-300 font-medium">Ingested: ${file.name}</p>
            <p class="text-[10px] text-slate-400">PHI Redacted: ${data.phi_detected.length} elements</p>
        `;

    } catch (e) {
        console.error("File upload error:", e);
        dropZone.innerHTML = `
            <i class="fa-solid fa-triangle-exclamation text-red-400 text-xl mb-1"></i>
            <p class="text-xs text-red-300 font-medium">Upload Error: ${e.message}</p>
            <p class="text-[10px] text-slate-400">Click to retry</p>
        `;
    }
}

async function checkAiStatus() {
    try {
        const res = await fetch("/api/ai-status");
        if (!res.ok) return;
        const data = await res.json();
        const text = document.getElementById("ai-status-text");
        if (text) {
            if (data.online && data.target_model_ready) {
                text.innerHTML = `<span class="text-emerald-400 font-semibold">Ollama: ${data.active_model} Ready</span>`;
            } else if (data.online) {
                text.innerHTML = `<span class="text-teal-300">Ollama: Online</span>`;
            } else {
                text.innerHTML = `<span class="text-slate-400">Rules Engine Active</span>`;
            }
        }
    } catch (e) {
        console.warn("Could not check AI status");
    }
}

// ---------------------------------------------------------------------------
// Mode Switching
// ---------------------------------------------------------------------------
function switchIntakeMode(mode) {
    currentIntakeMode = mode;
    const tabDemo = document.getElementById("itab-demo") || document.getElementById("tab-demo");
    const tabRaw = document.getElementById("itab-raw") || document.getElementById("tab-raw");
    const tabFhir = document.getElementById("itab-fhir");
    const demoSec = document.getElementById("section-demo") || document.getElementById("demo-patient-section");
    const rawSec = document.getElementById("section-raw") || document.getElementById("raw-note-section");
    const fhirSec = document.getElementById("section-fhir");

    [tabDemo, tabRaw, tabFhir].forEach(t => {
        if (t) {
            t.classList.remove("active");
            t.className = t.className.replace(/\bactive\b/g, "").trim();
        }
    });
    [demoSec, rawSec, fhirSec].forEach(s => {
        if (s) {
            s.style.display = "none";
            s.classList.add("hidden");
        }
    });

    if (mode === 'demo') {
        if (tabDemo) tabDemo.classList.add("active");
        if (demoSec) {
            demoSec.style.display = "block";
            demoSec.classList.remove("hidden");
        }
        loadPatientProfile(currentPatientId);
    } else if (mode === 'raw') {
        if (tabRaw) tabRaw.classList.add("active");
        if (rawSec) {
            rawSec.style.display = "block";
            rawSec.classList.remove("hidden");
        }
    } else if (mode === 'fhir') {
        if (tabFhir) tabFhir.classList.add("active");
        if (fhirSec) {
            fhirSec.style.display = "block";
            fhirSec.classList.remove("hidden");
        }
    }
}

function applySampleDischargeNote() {
    const rawInput = document.getElementById("raw-note-input");
    if (rawInput) {
        rawInput.value = SAMPLE_DISCHARGE_NOTE;
        triggerRedaction();
    }
}

// ---------------------------------------------------------------------------
// Quick Prescribe Helper
// ---------------------------------------------------------------------------
function setProposedMed(drug, dose) {
    document.getElementById("proposed-med-input").value = drug;
    document.getElementById("proposed-dose-input").value = dose;
    runSafetyCheck();
}

// ---------------------------------------------------------------------------
// API Calls: Patient Profile & Redaction
// ---------------------------------------------------------------------------
let cachedPatientsList = [];

async function initPatientSelector() {
    try {
        const res = await fetch("/api/patients");
        if (!res.ok) return;
        const data = await res.json();
        cachedPatientsList = data.patients || [];
        
        ['patient-select', 'patient-select-header'].forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select && cachedPatientsList.length > 0) {
                select.innerHTML = "";
                cachedPatientsList.forEach(p => {
                    const opt = document.createElement("option");
                    opt.value = p.patient_id;
                    opt.textContent = `${p.patient_id}: ${p.patient_name} (${p.age}y, ${p.gender})`;
                    select.appendChild(opt);
                });
                select.value = currentPatientId;
            }
        });

        renderPatientModalList(cachedPatientsList);
    } catch (e) {
        console.warn("Using default patient options (offline fallback)");
    }
}

function selectPatient(patientId) {
    if (!patientId) return;
    currentPatientId = patientId;
    loadPatientProfile(patientId);

    // Synchronize both dropdowns
    const selTab = document.getElementById("patient-select");
    if (selTab) selTab.value = patientId;
    const selHeader = document.getElementById("patient-select-header");
    if (selHeader) selHeader.value = patientId;

    // Refresh modal card active badge and close modal
    if (typeof renderPatientModalList === 'function' && cachedPatientsList.length > 0) {
        renderPatientModalList(cachedPatientsList);
    }
    if (typeof closePatientModal === 'function') {
        closePatientModal();
    }
}
window.selectPatient = selectPatient;

function renderPatientModalList(patients) {
    const list = document.getElementById("switch-patient-list");
    if (!list) return;
    list.innerHTML = "";

    const patientDetails = {
        'PT-101': {
            badge: 'Stage 3a CKD · High Renal Risk',
            badgeClass: 'bg-red-950/80 border-red-500/50 text-red-300',
            labs: 'eGFR 42 mL/min · Cr 1.9 mg/dL · K+ 4.4 mEq/L',
            desc: 'Hypertension, T2DM. Severe contraindication with NSAIDs (Advil, Naproxen, Celebrex).'
        },
        'PT-102': {
            badge: 'Asthma · Severe Bronchospasm Risk',
            badgeClass: 'bg-amber-950/80 border-amber-500/50 text-amber-300',
            labs: 'eGFR 92 mL/min · K+ 4.1 mEq/L · Wheezing PRN',
            desc: 'Allergic Rhinitis, Moderate Asthma. Severe allergy to Aspirin; contraindication with Beta Blockers (Propranolol).'
        },
        'PT-103': {
            badge: 'AFib · Warfarin Bleeding Risk',
            badgeClass: 'bg-purple-950/80 border-purple-500/50 text-purple-300',
            labs: 'INR 2.4 (Anticoagulated) · Digoxin therapy',
            desc: 'Deep Vein Thrombosis. Major hemorrhage risk if paired with NSAIDs or antiplatelet agents.'
        }
    };

    patients.forEach(p => {
        const isActive = p.patient_id === currentPatientId;
        const meta = patientDetails[p.patient_id] || {
            badge: 'Standard Cohort Profile',
            badgeClass: 'bg-slate-800 border-slate-700 text-slate-300',
            labs: 'Vitals in local memory',
            desc: 'De-identified clinical history.'
        };

        const card = document.createElement("div");
        card.className = `p-3.5 rounded-xl border transition cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-3 ${
            isActive ? 'bg-teal-950/40 border-teal-500/60 shadow-lg' : 'bg-slate-900 border-slate-800 hover:border-slate-700'
        }`;
        
        card.innerHTML = `
            <div class="space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="font-bold text-white text-xs">${p.patient_name}</span>
                    <span class="text-[10px] font-mono text-teal-400 bg-teal-950 border border-teal-500/30 px-1.5 py-0.5 rounded">${p.patient_id}</span>
                    <span class="text-[10px] font-mono border px-2 py-0.5 rounded ${meta.badgeClass}">${meta.badge}</span>
                </div>
                <div class="text-[11px] text-slate-400 font-mono">${p.age} years old · ${p.gender} · ${meta.labs}</div>
                <div class="text-[11px] text-slate-300">${meta.desc}</div>
            </div>
            <div class="flex items-center space-x-2 shrink-0">
                ${isActive ? 
                    '<span class="text-xs font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-3 py-1.5 rounded-lg flex items-center"><i class="fa-solid fa-circle-check mr-1.5"></i> ACTIVE</span>' : 
                    `<button type="button" onclick="selectPatient('${p.patient_id}')" class="btn-clinical-primary text-xs py-1.5 px-3">Select Patient</button>`
                }
            </div>
        `;

        if (!isActive) {
            card.onclick = (e) => {
                if (e.target.tagName !== 'BUTTON') {
                    selectPatient(p.patient_id);
                }
            };
        }

        list.appendChild(card);
    });
}
window.renderPatientModalList = renderPatientModalList;
window.refreshPatientModalCards = () => {
    if (cachedPatientsList.length > 0) {
        renderPatientModalList(cachedPatientsList);
    } else {
        initPatientSelector();
    }
};

async function loadPatientProfile(patientId) {
    try {
        const res = await fetch(`/api/patients/${patientId}`);
        if (!res.ok) return;
        const data = await res.json();
        renderPatientCard(data.patient, data.conditions, data.medications, data.allergies, data.biomarkers || data.labs);
    } catch (e) {
        console.error("Failed to load patient profile:", e);
    }
}

function renderPatientCard(patient, conditions, medications, allergies, biomarkers) {
    document.getElementById("display-patient-name").textContent = patient.patient_name;
    document.getElementById("display-patient-meta").textContent = 
        `ID: ${patient.patient_id} | Age: ${patient.age || 'N/A'} | ${patient.gender || 'N/A'}`;
    const token = patient.patient_id.startsWith("ANON_") ? patient.patient_id : `ANON_${patient.patient_id}`;
    document.getElementById("display-patient-token").textContent = token;

    // Conditions
    const condContainer = document.getElementById("conditions-list");
    condContainer.innerHTML = "";
    if (conditions && conditions.length > 0) {
        conditions.forEach(c => {
            const span = document.createElement("span");
            const isHighRisk = c.condition_name.toLowerCase().includes("kidney") || 
                               c.condition_name.toLowerCase().includes("asthma") ||
                               c.condition_name.toLowerCase().includes("fibrillation");
            span.className = isHighRisk 
                ? "px-2.5 py-1 bg-red-950/60 border border-red-500/40 text-red-200 rounded-md text-xs font-medium"
                : "px-2.5 py-1 bg-slate-700/60 text-slate-200 rounded-md text-xs";
            span.textContent = c.condition_name;
            condContainer.appendChild(span);
        });
    } else {
        condContainer.innerHTML = "<span class='text-xs text-slate-500'>No conditions recorded</span>";
    }

    // Medications
    const medContainer = document.getElementById("medications-list");
    medContainer.innerHTML = "";
    if (medications && medications.length > 0) {
        medications.forEach(m => {
            const span = document.createElement("span");
            span.className = "px-2.5 py-1 bg-slate-700/80 text-slate-200 rounded-md text-xs";
            span.textContent = `${m.medication_name} ${m.dosage || ''}`;
            medContainer.appendChild(span);
        });
    } else {
        medContainer.innerHTML = "<span class='text-xs text-slate-500'>No active medications</span>";
    }

    // Allergies
    const allergyContainer = document.getElementById("allergies-list");
    allergyContainer.innerHTML = "";
    if (allergies && allergies.length > 0) {
        allergies.forEach(a => {
            const span = document.createElement("span");
            span.className = "px-2.5 py-1 bg-amber-950/60 border border-amber-500/40 text-amber-200 rounded-md text-xs";
            span.textContent = `${a.allergen} (${a.reaction || 'Warning'})`;
            allergyContainer.appendChild(span);
        });
    } else {
        allergyContainer.innerHTML = "<span class='text-xs text-slate-500'>NKDA (No Known Drug Allergies)</span>";
    }

    // Quantitative Lab Biomarkers
    const bioContainer = document.getElementById("biomarkers-list");
    if (bioContainer) {
        bioContainer.innerHTML = "";
        if (biomarkers && Object.keys(biomarkers).length > 0) {
            Object.entries(biomarkers).forEach(([bioName, bioData]) => {
                const span = document.createElement("div");
                const label = bioName.toUpperCase();
                let dispVal = typeof bioData === "object" && bioData.display ? bioData.display : (typeof bioData === "object" && bioData.value ? `${bioData.value} ${bioData.unit || ''}` : String(bioData));
                let status = typeof bioData === "object" && bioData.status ? bioData.status : "NORMAL";

                let borderLeft = "border-l-slate-600";
                let textValColor = "text-slate-200";
                let statusBadge = "text-slate-400";

                if (status.includes("CRITICAL") || status.includes("STAGE 3") || status.includes("SEVERE")) {
                    borderLeft = "border-l-red-500";
                    textValColor = "text-red-400";
                    statusBadge = "text-red-300";
                } else if (status.includes("WARNING") || status.includes("ELEVATED") || status === "HIGH" || status.includes("STAGE")) {
                    borderLeft = "border-l-amber-500";
                    textValColor = "text-amber-400";
                    statusBadge = "text-amber-300";
                } else if (status === "NORMAL" || status.includes("OPTIMAL") || status.includes("SAFE") || status.includes("NORM")) {
                    borderLeft = "border-l-emerald-500";
                    textValColor = "text-emerald-400";
                    statusBadge = "text-emerald-300";
                }

                span.className = `bg-slate-900 p-2.5 rounded-lg border-l-2 ${borderLeft} border border-slate-800 flex flex-col justify-between`;
                span.innerHTML = `
                    <div class="text-[10px] text-slate-400 uppercase tracking-wider">${label}</div>
                    <div class="text-sm font-bold ${textValColor} font-mono mt-0.5">${dispVal}</div>
                    <span class="text-[9px] ${statusBadge} font-mono mt-0.5">${status}</span>
                `;
                bioContainer.appendChild(span);
            });
        } else {
            bioContainer.innerHTML = "<span class='text-xs text-slate-500'>No quantitative labs recorded</span>";
        }
    }
}

async function triggerRedaction() {
    const rawText = document.getElementById("raw-note-input").value;
    if (!rawText.trim()) {
        alert("Please enter or paste clinical notes first.");
        return;
    }

    try {
        const res = await fetch("/api/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: rawText })
        });
        const data = await res.json();
        
        // Update patient card with extracted entities and biomarkers
        renderPatientCard(
            { patient_name: "De-identified Note Patient", patient_id: data.patient_token, age: "Extracted", gender: "Extracted" },
            data.entities.diagnosed_conditions.map(c => ({ condition_name: c })),
            data.entities.current_medications.map(m => ({ medication_name: m, dosage: "" })),
            data.entities.allergies.map(a => ({ allergen: a, reaction: "Extracted" })),
            data.entities.biomarkers || data.entities.clinical_labs
        );

    } catch (e) {
        console.error("Redaction error:", e);
    }
}

// ---------------------------------------------------------------------------
// Clinical Safety Cross-Check (Core Review)
// ---------------------------------------------------------------------------
async function runSafetyCheck() {
    const proposedMed = document.getElementById("proposed-med-input").value.trim();
    const dosage = document.getElementById("proposed-dose-input").value.trim();

    if (!proposedMed) {
        alert("Please enter a proposed medication.");
        return;
    }

    const btn = document.getElementById("btn-run-review");
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>ANALYZING LOCALLY...</span>`;
    btn.disabled = true;

    try {
        const payload = {
            proposed_medication: proposedMed,
            dosage: dosage
        };

        if (currentIntakeMode === 'demo') {
            payload.patient_id = currentPatientId;
        } else {
            payload.raw_notes_override = document.getElementById("raw-note-input").value;
        }

        const res = await fetch("/api/review", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("API call failed");
        const data = await res.json();

        renderReviewResults(data);
        refreshAuditTrail();

    } catch (e) {
        console.error("Safety check failed:", e);
    } finally {
        btn.innerHTML = `<i class="fa-solid fa-radar text-base"></i><span>RUN OFFLINE CONTRAINDICATION REVIEW</span>`;
        btn.disabled = false;
    }
}

function renderReviewResults(data) {
    currentReviewEventId = data.event_id;
    const idleHint = document.getElementById("result-idle-hint");
    const resContent = document.getElementById("result-content");
    if (idleHint) idleHint.style.display = "none";
    if (resContent) resContent.style.display = "block";

    const banner = document.getElementById("status-banner");
    const icon = document.getElementById("status-icon");
    const title = document.getElementById("status-title");
    const countBadge = document.getElementById("alerts-count-badge");
    const explanation = document.getElementById("status-explanation");
    const alertsContainer = document.getElementById("alerts-container");
    const polyContainer = document.getElementById("polypharmacy-container");
    const altContainer = document.getElementById("alternatives-container");
    const auditHash = document.getElementById("audit-hash-display");
    const execTime = document.getElementById("exec-time-display");

    if (auditHash && data.audit_hash) {
        auditHash.textContent = `${data.audit_hash.substring(0, 14)}...${data.audit_hash.substring(data.audit_hash.length - 8)}`;
    }
    if (execTime && data.execution_time_ms !== undefined) {
        execTime.textContent = `${data.execution_time_ms} ms`;
    }

    alertsContainer.innerHTML = "";

    // 1. Render Cumulative Polypharmacy Alerts
    if (polyContainer) {
        polyContainer.innerHTML = "";
        if (data.polypharmacy_alerts && data.polypharmacy_alerts.length > 0) {
            polyContainer.classList.remove("hidden");
            data.polypharmacy_alerts.forEach(pa => {
                const cluster = (pa.interacting_drugs || []).map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(" + ");
                const card = document.createElement("div");
                card.className = "bg-gradient-to-r from-red-950 via-slate-900 to-red-950 border-2 border-red-500/80 rounded-xl p-3.5 shadow-lg text-xs";
                card.innerHTML = `
                    <div class="flex items-center justify-between font-extrabold text-red-300 text-xs mb-1.5">
                        <span class="flex items-center space-x-2">
                            <i class="fa-solid fa-radiation text-red-400 text-sm animate-pulse"></i>
                            <span class="uppercase tracking-wide">${pa.rule_name || 'CUMULATIVE POLYPHARMACY TOXICITY'}</span>
                        </span>
                        <span class="text-[10px] bg-red-900 text-red-200 border border-red-400/60 px-2 py-0.5 rounded font-mono uppercase">Multi-Drug Alert</span>
                    </div>
                    <div class="text-slate-200 font-semibold mb-1 text-[11px]">
                        Interacting Regimen Cluster: <span class="text-amber-300 font-mono">${cluster}</span>
                    </div>
                    <p class="text-slate-300 mb-2 leading-relaxed text-[11px]">
                        <strong class="text-slate-200">Pathophysiology:</strong> ${pa.clinical_mechanism}
                    </p>
                    <div class="bg-red-900/40 p-2 rounded border border-red-700/60 text-red-200 font-mono text-[11px]">
                        <strong>Emergency De-escalation:</strong> ${pa.recommendation}
                    </div>
                `;
                polyContainer.appendChild(card);
            });
        } else {
            polyContainer.classList.add("hidden");
        }
    }

    // 2. Status Banner
    if (data.overall_status === "CRITICAL") {
        banner.className = "triage-banner danger";
        icon.className = "text-2xl mt-0.5 text-red-400";
        icon.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i>`;
        title.className = "font-extrabold text-xs tracking-wide uppercase text-red-200 font-heading";
        title.textContent = "CRITICAL CONTRAINDICATION DETECTED";
        countBadge.className = "text-[10px] font-mono bg-red-950 border border-red-500/50 text-red-200 px-2 py-0.5 rounded-full font-bold";
        countBadge.textContent = `${data.total_alerts} Risk Alert${data.total_alerts > 1 ? 's' : ''}`;
    } else if (data.overall_status === "WARNING") {
        banner.className = "triage-banner warning";
        icon.className = "text-2xl mt-0.5 text-amber-400";
        icon.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>`;
        title.className = "font-extrabold text-xs tracking-wide uppercase text-amber-200 font-heading";
        title.textContent = "CLINICAL CAUTION / RELATIVE CONTRAINDICATION";
        countBadge.className = "text-[10px] font-mono bg-amber-950 border border-amber-500/50 text-amber-200 px-2 py-0.5 rounded-full font-bold";
        countBadge.textContent = `${data.total_alerts} Warning${data.total_alerts > 1 ? 's' : ''}`;
    } else {
        banner.className = "triage-banner safe";
        icon.className = "text-2xl mt-0.5 text-emerald-400";
        icon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
        title.className = "font-extrabold text-xs tracking-wide uppercase text-emerald-200 font-heading";
        title.textContent = "PRESCRIPTION CLEARED (SAFE)";
        countBadge.className = "text-[10px] font-mono bg-emerald-950 border border-emerald-500/50 text-emerald-200 px-2 py-0.5 rounded-full font-bold";
        countBadge.textContent = "0 Contraindications";
    }

    explanation.textContent = data.explanation;

    // 3. Render Standard & Lab Threshold Alerts
    const standardAlerts = (data.alerts || []).filter(a => a.interaction_type !== "POLYPHARMACY");
    if (standardAlerts.length > 0) {
        standardAlerts.forEach(a => {
            let badgeColor = 'bg-red-950 border-red-500/40 text-red-300';
            if (a.interaction_type === 'ALLERGY') {
                badgeColor = 'bg-purple-950 border-purple-500/50 text-purple-300';
            } else if (a.interaction_type === 'DRUG_DRUG') {
                badgeColor = 'bg-amber-950 border-amber-500/50 text-amber-300';
            } else if (a.interaction_type === 'LAB_THRESHOLD') {
                badgeColor = 'bg-cyan-950 border-cyan-500/50 text-cyan-300';
            } else if (a.interaction_type === 'BEERS_CRITERIA') {
                badgeColor = 'bg-amber-950 border-yellow-500/60 text-yellow-300';
            } else if (a.interaction_type === 'RENAL_TITRATION') {
                badgeColor = 'bg-orange-950 border-orange-500/60 text-orange-300';
            }

            const card = document.createElement("div");
            card.className = "bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs";
            card.innerHTML = `
                <div class="flex items-center justify-between font-semibold text-slate-100 mb-1.5">
                    <span class="flex items-center space-x-1.5"><i class="fa-solid fa-triangle-exclamation text-amber-400"></i> <span>${a.conflicting_factor}</span></span>
                    <span class="text-[10px] ${badgeColor} border px-2 py-0.5 rounded uppercase font-mono font-semibold">${a.interaction_type}</span>
                </div>
                <p class="text-slate-300 mb-2 leading-relaxed text-[11.5px]">
                    <strong class="text-slate-200">Pathophysiology:</strong> ${a.clinical_mechanism}
                </p>
                <div class="bg-slate-950 p-2.5 rounded border border-slate-800 text-teal-300 font-mono text-[11px] leading-relaxed">
                    <strong class="text-slate-300 font-sans">Recommendation:</strong> ${a.recommendation}
                </div>
            `;
            alertsContainer.appendChild(card);
        });
    } else if (!data.polypharmacy_alerts || data.polypharmacy_alerts.length === 0) {
        const safeCard = document.createElement("div");
        safeCard.className = "bg-slate-900 border border-emerald-500/30 rounded-lg p-3 text-xs text-slate-300 text-center";
        safeCard.innerHTML = `<i class="fa-solid fa-shield-check text-emerald-400 mr-1.5"></i> Verified against 30+ high-severity contraindication rules, quantitative lab thresholds, and polypharmacy matrices. No adverse drug interactions identified.`;
        alertsContainer.appendChild(safeCard);
    }

    // 4. Clinical Safe Alternatives Formulary (with 1-Click Swap)
    if (altContainer) {
        altContainer.innerHTML = "";
        if (data.recommended_alternatives && data.recommended_alternatives.length > 0) {
            altContainer.classList.remove("hidden");
            const header = document.createElement("div");
            header.className = "flex items-center justify-between text-xs font-bold text-teal-300 mb-2 px-1";
            header.innerHTML = `
                <span class="flex items-center space-x-1.5">
                    <i class="fa-solid fa-pills text-teal-400"></i>
                    <span>Formulary Safe Alternatives (Non-Contraindicated)</span>
                </span>
                <span class="text-[10px] text-slate-400 font-mono">1-Click Swap &amp; Re-Verify</span>
            `;
            altContainer.appendChild(header);

            const grid = document.createElement("div");
            grid.className = "grid grid-cols-1 md:grid-cols-2 gap-2";

            data.recommended_alternatives.forEach(alt => {
                const altCard = document.createElement("div");
                altCard.className = "p-3 bg-slate-900 border border-teal-500/30 hover:border-teal-400/60 rounded-lg text-xs flex flex-col justify-between transition group";
                altCard.innerHTML = `
                    <div>
                        <div class="flex items-center justify-between mb-1">
                            <strong class="text-teal-200 text-xs">${alt.alternative_drug}</strong>
                            <span class="text-[9px] bg-teal-950 text-teal-300 border border-teal-500/30 px-1.5 py-0.5 rounded font-mono">${alt.target_indication}</span>
                        </div>
                        <div class="text-[10px] text-slate-300 font-mono mb-1.5">${alt.dosage_guide}</div>
                        <p class="text-[11px] text-slate-400 leading-snug mb-2">${alt.rationale}</p>
                    </div>
                    <button onclick="swapAndVerify('${alt.alternative_drug}', '${alt.dosage_guide}')" class="btn-clinical-secondary w-full py-1.5 text-xs font-semibold flex items-center justify-center space-x-1.5">
                        <i class="fa-solid fa-repeat"></i>
                        <span>Swap to ${alt.alternative_drug} &amp; Verify</span>
                    </button>
                `;
                grid.appendChild(altCard);
            });
            altContainer.appendChild(grid);
        } else {
            altContainer.classList.add("hidden");
        }
    }
}

function swapAndVerify(drug, dose) {
    const medInput = document.getElementById("proposed-med-input");
    const doseInput = document.getElementById("proposed-dose-input");
    if (medInput) medInput.value = drug;
    if (doseInput && dose) {
        doseInput.value = dose.split(" ")[0] || dose;
    }
    runSafetyCheck();
}

function exportClinicalCertificate() {
    if (!currentReviewEventId) {
        alert("Please run a clinical safety review first to generate an audit event.");
        return;
    }
    window.open(`/api/report/clearance?event_id=${encodeURIComponent(currentReviewEventId)}`, '_blank');
}

// ---------------------------------------------------------------------------
// Sovereign Optical QR Air-Gap Transfer & FHIR Sandbox Helpers
// ---------------------------------------------------------------------------
async function openClearanceQrModal() {
    if (!currentReviewEventId) {
        alert("Please run a clinical safety review first to generate an audit event.");
        return;
    }
    const modal = document.getElementById("qr-modal");
    const container = document.getElementById("qr-image-container");
    const hashDisplay = document.getElementById("qr-modal-hash");

    if (modal) modal.style.display = "flex";
    if (container) container.innerHTML = `<div style="color:#0f172a; font-size:11px; padding:90px 0;"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Generating Vector Seal…</div>`;

    try {
        const res = await fetch(`/api/report/clearance-qr?event_id=${encodeURIComponent(currentReviewEventId)}`);
        if (!res.ok) throw new Error("Failed to generate QR code");
        const svgText = await res.text();
        if (container) {
            container.innerHTML = svgText;
            const svgEl = container.querySelector("svg");
            if (svgEl) {
                svgEl.setAttribute("width", "200");
                svgEl.setAttribute("height", "200");
                svgEl.style.display = "block";
                svgEl.style.margin = "0 auto";
            }
        }
        if (hashDisplay) {
            hashDisplay.textContent = `Event: ${currentReviewEventId}`;
        }
    } catch (err) {
        if (container) container.innerHTML = `<div style="color:#ef4444; font-size:11px; padding:80px 0;">Error generating seal</div>`;
    }
}

function closeClearanceQrModal() {
    const modal = document.getElementById("qr-modal");
    if (modal) modal.style.display = "none";
}

function loadFhirPreset(type) {
    if (type === 'geriatric') {
        const rawNote = `PATIENT CLINICAL DISCHARGE SUMMARY (EHR INGESTION)
PATIENT: Eleanor Vance (De-identified)
AGE: 76  GENDER: Female  WEIGHT: 50.0 kg
DIAGNOSES: Stage 3 Chronic Kidney Disease (CKD), Moderate Osteoarthritis, Essential Hypertension
ACTIVE MEDICATIONS: Lisinopril 20mg daily, Hydrochlorothiazide 25mg daily
ALLERGIES: NKDA
LABORATORY RESULTS:
Serum Creatinine: 1.8 mg/dL
eGFR: 24 mL/min/1.73m2
Potassium: 4.5 mEq/L
Body Weight: 50.0 kg
PROPOSED NEW ORDER: Gabapentin 600mg TID and Diphenhydramine 50mg PO at bedtime for sleep`;

        const rawInput = document.getElementById("raw-note-input");
        if (rawInput) rawInput.value = rawNote;

        const medInput = document.getElementById("proposed-med-input");
        const doseInput = document.getElementById("proposed-dose-input");
        if (medInput) medInput.value = "Gabapentin";
        if (doseInput) doseInput.value = "600mg TID";

        const pName = document.getElementById("display-patient-name");
        const pMeta = document.getElementById("display-patient-meta");
        const pToken = document.getElementById("display-patient-token");
        if (pName) pName.textContent = "Eleanor Vance (Geriatric ER Encounter)";
        if (pMeta) pMeta.textContent = "ID: EHR-7782 · Age: 76y · Female · Weight: 50kg (CrCl 18.5 mL/min)";
        if (pToken) pToken.textContent = "ANON_EHR7782";

        runSafetyCheck();
    } else if (type === 'optical_qr') {
        const samplePayload = {
            "patient_id": "OPT-449",
            "age": 78,
            "gender": "female",
            "weight": 48.0,
            "conditions": ["chronic kidney disease", "insomnia"],
            "medications": ["lisinopril"],
            "allergies": [],
            "labs": {
                "creatinine": {"value": 1.7, "unit": "mg/dL"},
                "egfr": {"value": 26.0, "unit": "mL/min"}
            }
        };
        const fhirInput = document.getElementById("fhir-raw-input");
        if (fhirInput) {
            fhirInput.value = JSON.stringify(samplePayload, null, 2);
        }
        triggerFhirIngestion();
    }
}

async function handleFhirFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/api/ingest/interop", { method: "POST", body: formData });
        if (!res.ok) throw new Error("Failed to parse interop file");
        const data = await res.json();
        applyParsedInteropData(data);
    } catch (err) {
        alert("Interop parse error: " + err.message);
    }
}

async function triggerFhirIngestion() {
    const raw = (document.getElementById("fhir-raw-input") || {}).value;
    if (!raw || !raw.trim()) {
        alert("Please paste FHIR JSON, HL7 v2, or Optical QR payload.");
        return;
    }

    const formData = new FormData();
    formData.append("raw_payload", raw.trim());

    try {
        const res = await fetch("/api/ingest/interop", { method: "POST", body: formData });
        if (!res.ok) throw new Error("Failed to parse interop payload");
        const data = await res.json();
        applyParsedInteropData(data);
    } catch (err) {
        alert("Interop ingestion error: " + err.message);
    }
}

function applyParsedInteropData(data) {
    const pName = document.getElementById("display-patient-name");
    const pMeta = document.getElementById("display-patient-meta");
    const pToken = document.getElementById("display-patient-token");

    const demo = data.demographics || {};
    const ageStr = demo.age ? `${demo.age}y` : "Age Unspecified";
    const sexStr = demo.gender ? demo.gender : "";
    const wtStr = demo.weight_kg ? ` · ${demo.weight_kg}kg` : "";

    if (pName) pName.textContent = `Interoperable Patient (${data.format || 'FHIR'})`;
    if (pMeta) pMeta.textContent = `Format: ${data.format || 'FHIR R4'} · ${ageStr} ${sexStr}${wtStr}`;
    if (pToken) pToken.textContent = data.patient_token || "ANON_INTEROP";

    // Populate conditions, meds, allergies
    const entities = data.entities || {};
    const condList = document.getElementById("conditions-list");
    if (condList) {
        condList.innerHTML = "";
        (entities.diagnosed_conditions || []).forEach(c => {
            const span = document.createElement("span");
            span.className = "tag-cond";
            span.textContent = c;
            condList.appendChild(span);
        });
    }

    const medList = document.getElementById("medications-list");
    if (medList) {
        medList.innerHTML = "";
        (entities.current_medications || []).forEach(m => {
            const span = document.createElement("span");
            span.className = "tag-med";
            span.textContent = m;
            medList.appendChild(span);
        });
    }

    const bioList = document.getElementById("biomarkers-list");
    if (bioList) {
        bioList.innerHTML = "";
        const bios = entities.biomarkers || {};
        if (Object.keys(bios).length > 0) {
            Object.entries(bios).forEach(([name, b]) => {
                const span = document.createElement("span");
                span.className = "px-2 py-0.5 bg-teal-950/70 border border-teal-500/40 text-teal-300 rounded text-xs font-mono";
                span.textContent = `${name.toUpperCase()}: ${b.display || b.value}`;
                bioList.appendChild(span);
            });
        }
    }

    // Set proposed med if available
    const meds = entities.current_medications || [];
    if (meds.length > 0) {
        const medInput = document.getElementById("proposed-med-input");
        if (medInput) medInput.value = meds[0];
    }

    runSafetyCheck();
}

// ---------------------------------------------------------------------------
// Cryptographic Audit Trail
// ---------------------------------------------------------------------------
async function refreshAuditTrail() {
    try {
        const res = await fetch("/api/audit-logs?limit=8");
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.getElementById("audit-table-body");
        if (!tbody || !data.audit_trail) return;

        tbody.innerHTML = "";
        data.audit_trail.forEach(log => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-800/50 transition";
            const statusClass = log.overall_status === 'CRITICAL' ? 'text-red-400 font-bold' :
                               (log.overall_status === 'WARNING' ? 'text-amber-400' : 'text-emerald-400');
            const doctorName = log.practitioner_name || "Dr. Gregory House, MD";
            const hospitalName = log.hospital_name || "Princeton Plainsboro";

            tr.innerHTML = `
                <td class="py-2.5 px-3.5 text-slate-400 font-mono text-[11px]">${log.timestamp.substring(11, 19)}</td>
                <td class="py-2.5 px-3.5">
                    <div class="font-medium text-teal-300 text-xs">${doctorName}</div>
                    <div class="text-[10px] text-slate-400 font-sans truncate max-w-[140px]">${hospitalName}</div>
                </td>
                <td class="py-2.5 px-3.5 text-teal-400 font-mono text-[11px] font-semibold">${log.event_id}</td>
                <td class="py-2.5 px-3.5 text-slate-300 font-mono text-[11px]">${log.patient_hash}</td>
                <td class="py-2.5 px-3.5 text-slate-100 font-medium text-xs">${log.proposed_medication}</td>
                <td class="py-2.5 px-3.5 ${statusClass} text-xs uppercase font-mono font-bold">${log.overall_status}</td>
                <td class="py-2.5 px-3.5 text-slate-400 font-mono text-[10.5px] truncate max-w-[120px]" title="${log.audit_hash}">
                  <span class="hover:text-teal-300 cursor-pointer" onclick="navigator.clipboard.writeText('${log.audit_hash}')">${log.audit_hash.substring(0, 16)}...</span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.warn("Could not refresh audit trail:", e);
    }
}

async function verifyAuditChain() {
    const banner = document.getElementById("integrity-banner");
    banner.classList.remove("hidden");
    banner.className = "mt-3 p-2.5 rounded-lg text-xs font-mono bg-slate-900 border border-teal-500/40 text-teal-300 flex items-center space-x-2";
    banner.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Mathematically verifying SHA-256 hash chaining across all blocks...</span>`;

    try {
        const res = await fetch("/api/audit-verify");
        const data = await res.json();

        if (data.valid) {
            banner.className = "mt-3 p-2.5 rounded-lg text-xs font-mono bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 flex items-center justify-between";
            banner.innerHTML = `
                <div class="flex items-center space-x-2">
                    <i class="fa-solid fa-check-double text-emerald-400"></i>
                    <span><strong>CRYPTOGRAPHIC PROOF:</strong> All ${data.total_blocks} audit blocks verified intact (Zero Tampering Detected).</span>
                </div>
                <span class="text-[10px] text-emerald-400 font-bold uppercase">HIPAA § 164.312(b) Certified</span>
            `;
        } else {
            banner.className = "mt-3 p-2.5 rounded-lg text-xs font-mono bg-red-950/80 border border-red-500/50 text-red-300";
            banner.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1.5"></i><strong>TAMPER DETECTED:</strong> ${data.error}`;
        }
    } catch (e) {
        banner.className = "mt-3 p-2.5 rounded-lg text-xs font-mono bg-red-950/80 border border-red-500/50 text-red-300";
        banner.innerHTML = `Verification call failed: ${e.message}`;
    }
}

function toggleAuditDrawer() {
    const drawer = document.getElementById("audit-drawer");
    const icon = document.getElementById("audit-toggle-icon");
    const text = document.getElementById("audit-toggle-text");

    if (drawer.classList.contains("hidden")) {
        drawer.classList.remove("hidden");
        icon.className = "fa-solid fa-chevron-up transition";
        text.textContent = "Collapse Audit Trail";
        refreshAuditTrail();
    } else {
        drawer.classList.add("hidden");
        icon.className = "fa-solid fa-chevron-down transition";
        text.textContent = "Show Logs";
    }
}

// ---------------------------------------------------------------------------
// Institutional Physician Authentication & Verification Controller
// ---------------------------------------------------------------------------
let currentDoctor = null;
let hospitalsList = [];
let pendingVerificationEmail = "";

async function loadAuthProfile() {
    try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
            const data = await res.json();
            if (data.practitioner) {
                updateDoctorHeader(data.practitioner);
            }
        }
    } catch (e) {
        console.warn("Could not load doctor profile:", e);
    }
}

function updateDoctorHeader(doctor) {
    currentDoctor = doctor;
    const pill = document.getElementById("current-doctor-pill");
    const badge = document.getElementById("current-hospital-badge");
    if (pill) pill.textContent = doctor.full_name || "Dr. Gregory House, MD";
    if (badge) {
        badge.textContent = doctor.hospital_name || "Princeton Plainsboro";
        badge.title = `${doctor.role || 'PHYSICIAN'} • ${doctor.medical_license || 'NPI-1999887766'}`;
    }
}

async function loadHospitalsAndDemoDoctors() {
    try {
        const [hospRes, pracRes] = await Promise.all([
            fetch("/api/auth/hospitals"),
            fetch("/api/auth/practitioners")
        ]);

        if (hospRes.ok) {
            const hospData = await hospRes.json();
            hospitalsList = hospData.hospitals || [];
            populateHospitalDropdown(hospitalsList);
        }

        if (pracRes.ok) {
            const pracData = await pracRes.json();
            populateDemoDoctorsList(pracData.practitioners || []);
        }
    } catch (e) {
        console.warn("Could not load hospital lists:", e);
    }
}

function populateHospitalDropdown(hospitals) {
    const select = document.getElementById("reg-hospital-select");
    if (!select) return;
    select.innerHTML = "";
    hospitals.forEach(h => {
        const opt = document.createElement("option");
        opt.value = h.hospital_id;
        opt.textContent = `${h.hospital_name} (${h.city_state})`;
        opt.dataset.domain = h.domain_whitelist;
        select.appendChild(opt);
    });
    onHospitalSelectChange();
}

function onHospitalSelectChange() {
    const select = document.getElementById("reg-hospital-select");
    const hint = document.getElementById("reg-domain-hint");
    if (!select || !hint) return;
    const selectedOpt = select.options[select.selectedIndex];
    if (selectedOpt && selectedOpt.dataset.domain) {
        hint.textContent = `Required email domain: @${selectedOpt.dataset.domain}`;
    }
}

function populateDemoDoctorsList(doctors) {
    const container = document.getElementById("demo-doctors-list");
    if (!container) return;
    container.innerHTML = "";

    doctors.forEach(doc => {
        const card = document.createElement("div");
        card.className = "p-3 bg-slate-900 border border-slate-700/80 hover:border-teal-500/60 rounded-xl flex items-center justify-between transition cursor-pointer group";
        card.onclick = () => switchDemoDoctor(doc.practitioner_id);

        const isCurrent = currentDoctor && currentDoctor.practitioner_id === doc.practitioner_id;
        const activeBadge = isCurrent ? `<span class="text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 px-2 py-0.5 rounded font-mono">ACTIVE</span>` : "";

        card.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-full bg-teal-500/20 text-teal-400 border border-teal-500/30 flex items-center justify-center font-bold text-sm">
                    ${doc.full_name.replace("Dr. ", "").substring(0, 2).toUpperCase()}
                </div>
                <div>
                    <div class="text-xs font-bold text-white group-hover:text-teal-300 transition flex items-center space-x-2">
                        <span>${doc.full_name}</span>
                        ${activeBadge}
                    </div>
                    <div class="text-[11px] text-slate-400">${doc.hospital_name} • <span class="font-mono text-slate-500">${doc.medical_license}</span></div>
                </div>
            </div>
            <button class="text-xs bg-slate-800 group-hover:bg-teal-600 group-hover:text-white text-slate-300 px-3 py-1.5 rounded-lg border border-slate-600 transition font-medium">
                Switch
            </button>
        `;
        container.appendChild(card);
    });
}

function openAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) {
        modal.classList.remove("hidden");
        switchAuthTab('demo');
        hideAuthAlert();
    }
}

function closeAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) modal.classList.add("hidden");
}

function switchAuthTab(tab) {
    hideAuthAlert();
    const header = document.getElementById("modal-tabs-header");
    if (header) header.classList.remove("hidden");

    const tabs = ['demo', 'login', 'register'];
    tabs.forEach(t => {
        const content = document.getElementById(`auth-tab-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (content) content.classList.add("hidden");
        if (btn) {
            btn.className = "flex-1 py-3 px-4 text-center border-b-2 border-transparent hover:text-slate-200 cursor-pointer";
        }
    });

    const activeContent = document.getElementById(`auth-tab-${tab}`);
    const activeBtn = document.getElementById(`tab-btn-${tab}`);
    const otpScreen = document.getElementById("auth-screen-otp");

    if (otpScreen) otpScreen.classList.add("hidden");

    if (activeContent) activeContent.classList.remove("hidden");
    if (activeBtn) {
        activeBtn.className = "flex-1 py-3 px-4 text-center border-b-2 border-teal-400 text-teal-300 font-semibold cursor-pointer";
    }
}

function showAuthAlert(msg, type = "error") {
    const alert = document.getElementById("auth-alert");
    if (!alert) return;
    alert.classList.remove("hidden");
    if (type === "success") {
        alert.className = "mb-4 p-3 rounded-lg text-xs font-mono bg-emerald-950 border border-emerald-500/50 text-emerald-300";
    } else {
        alert.className = "mb-4 p-3 rounded-lg text-xs font-mono bg-red-950 border border-red-500/50 text-red-300";
    }
    alert.innerHTML = msg;
}

function hideAuthAlert() {
    const alert = document.getElementById("auth-alert");
    if (alert) alert.classList.add("hidden");
}

async function switchDemoDoctor(pracId) {
    try {
        const res = await fetch("/api/auth/switch-demo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ practitioner_id: pracId })
        });
        const data = await res.json();
        if (res.ok) {
            updateDoctorHeader(data.practitioner);
            closeAuthModal();
            refreshAuditTrail();
            loadHospitalsAndDemoDoctors();
        } else {
            showAuthAlert(data.detail || "Failed to switch doctor.", "error");
        }
    } catch (e) {
        showAuthAlert(e.message, "error");
    }
}

async function handleLogin() {
    hideAuthAlert();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    if (!email || !password) {
        showAuthAlert("Please enter both institutional email and password.", "error");
        return;
    }

    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();

        if (res.status === 403) {
            // Unverified account -> trigger OTP verification screen
            pendingVerificationEmail = email;
            showOtpScreen(email, null);
            showAuthAlert(data.detail, "error");
            return;
        }

        if (!res.ok) {
            showAuthAlert(data.detail || "Login failed.", "error");
            return;
        }

        updateDoctorHeader(data.practitioner);
        closeAuthModal();
        refreshAuditTrail();
    } catch (e) {
        showAuthAlert(e.message, "error");
    }
}

async function handleRegister() {
    hideAuthAlert();
    const full_name = document.getElementById("reg-name").value.trim();
    const hospital_id = document.getElementById("reg-hospital-select").value;
    const email = document.getElementById("reg-email").value.trim();
    const medical_license = document.getElementById("reg-license").value.trim();
    const password = document.getElementById("reg-password").value;

    if (!full_name || !email || !medical_license || !password) {
        showAuthAlert("All clinical credentials and institutional details are required.", "error");
        return;
    }

    try {
        const res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name, hospital_id, email, medical_license, password })
        });
        const data = await res.json();

        if (!res.ok) {
            showAuthAlert(data.detail || "Registration rejected.", "error");
            return;
        }

        pendingVerificationEmail = email;
        showOtpScreen(email, data.simulated_code);
    } catch (e) {
        showAuthAlert(e.message, "error");
    }
}

function showOtpScreen(email, simulatedCode) {
    ['demo', 'login', 'register'].forEach(t => {
        const el = document.getElementById(`auth-tab-${t}`);
        if (el) el.classList.add("hidden");
    });
    const header = document.getElementById("modal-tabs-header");
    if (header) header.classList.add("hidden");

    const otpScreen = document.getElementById("auth-screen-otp");
    if (otpScreen) otpScreen.classList.remove("hidden");

    const emailLabel = document.getElementById("otp-target-email");
    if (emailLabel) emailLabel.textContent = email;

    const simCodeLabel = document.getElementById("simulated-otp-code");
    if (simCodeLabel) {
        simCodeLabel.textContent = simulatedCode ? `${simulatedCode.substring(0,3)}-${simulatedCode.substring(3,6)}` : "DISPATCHED";
    }

    const input = document.getElementById("otp-input");
    if (input) {
        input.value = "";
        input.focus();
    }
}

async function handleVerifyOtp() {
    hideAuthAlert();
    const code = document.getElementById("otp-input").value.trim();
    if (!code || code.length !== 6) {
        showAuthAlert("Please enter the complete 6-digit verification code.", "error");
        return;
    }

    try {
        const res = await fetch("/api/auth/verify-email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: pendingVerificationEmail, verification_code: code })
        });
        const data = await res.json();

        if (!res.ok) {
            showAuthAlert(data.detail || "Verification failed.", "error");
            return;
        }

        updateDoctorHeader(data.practitioner);
        closeAuthModal();
        refreshAuditTrail();
    } catch (e) {
        showAuthAlert(e.message, "error");
    }
}

async function handleResendOtp() {
    hideAuthAlert();
    try {
        const res = await fetch("/api/auth/resend-code", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: pendingVerificationEmail })
        });
        const data = await res.json();
        if (res.ok) {
            const simCodeLabel = document.getElementById("simulated-otp-code");
            if (simCodeLabel && data.simulated_code) {
                simCodeLabel.textContent = `${data.simulated_code.substring(0,3)}-${data.simulated_code.substring(3,6)}`;
            }
            showAuthAlert("New 6-digit code dispatched to local hospital inbox.", "success");
        } else {
            showAuthAlert(data.detail || "Could not resend code.", "error");
        }
    } catch (e) {
        showAuthAlert(e.message, "error");
    }
}
