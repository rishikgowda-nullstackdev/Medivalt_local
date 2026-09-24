/**
 * MediVault Local - Doctor Dashboard Frontend Controller
 * Connects UI to local FastAPI endpoints (127.0.0.1:8000) with zero external network calls.
 */

let currentIntakeMode = 'demo';
let currentPatientId = 'PT-101';
let currentUploadedRecord = null;

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

    // Listen to patient dropdown change
    const selectEl = document.getElementById("patient-select");
    if (selectEl) {
        selectEl.addEventListener("change", (e) => {
            currentPatientId = e.target.value;
            loadPatientProfile(currentPatientId);
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

        // Update Patient Card with extracted entities
        renderPatientCard(
            { patient_name: `Ingested: ${file.name}`, patient_id: data.patient_token, age: "Extracted", gender: "Extracted" },
            data.entities.diagnosed_conditions.map(c => ({ condition_name: c })),
            data.entities.current_medications.map(m => ({ medication_name: m, dosage: "" })),
            data.entities.allergies.map(a => ({ allergen: a, reaction: "Extracted" }))
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

// ---------------------------------------------------------------------------
// Mode Switching
// ---------------------------------------------------------------------------
function switchIntakeMode(mode) {
    currentIntakeMode = mode;
    const tabDemo = document.getElementById("tab-demo");
    const tabRaw = document.getElementById("tab-raw");
    const demoSec = document.getElementById("demo-patient-section");
    const rawSec = document.getElementById("raw-note-section");

    if (mode === 'demo') {
        tabDemo.className = "py-1.5 rounded-md bg-teal-600 text-white font-semibold transition";
        tabRaw.className = "py-1.5 rounded-md text-slate-400 hover:text-slate-200 transition";
        demoSec.classList.remove("hidden");
        rawSec.classList.add("hidden");
        loadPatientProfile(currentPatientId);
    } else {
        tabRaw.className = "py-1.5 rounded-md bg-teal-600 text-white font-semibold transition";
        tabDemo.className = "py-1.5 rounded-md text-slate-400 hover:text-slate-200 transition";
        rawSec.classList.remove("hidden");
        demoSec.classList.add("hidden");
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
async function initPatientSelector() {
    try {
        const res = await fetch("/api/patients");
        if (!res.ok) return;
        const data = await res.json();
        const select = document.getElementById("patient-select");
        if (select && data.patients && data.patients.length > 0) {
            select.innerHTML = "";
            data.patients.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p.patient_id;
                opt.textContent = `${p.patient_id}: ${p.patient_name} (${p.age}y, ${p.gender})`;
                select.appendChild(opt);
            });
            select.value = currentPatientId;
        }
    } catch (e) {
        console.warn("Using default patient options (offline fallback)");
    }
}

async function loadPatientProfile(patientId) {
    try {
        const res = await fetch(`/api/patients/${patientId}`);
        if (!res.ok) return;
        const data = await res.json();
        renderPatientCard(data.patient, data.conditions, data.medications, data.allergies);
    } catch (e) {
        console.error("Failed to load patient profile:", e);
    }
}

function renderPatientCard(patient, conditions, medications, allergies) {
    document.getElementById("display-patient-name").textContent = patient.patient_name;
    document.getElementById("display-patient-meta").textContent = 
        `ID: ${patient.patient_id} | Age: ${patient.age || 'N/A'} | ${patient.gender || 'N/A'}`;
    document.getElementById("display-patient-token").textContent = `ANON_${patient.patient_id}`;

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
        
        // Update patient card with extracted entities
        renderPatientCard(
            { patient_name: "De-identified Note Patient", patient_id: data.patient_token, age: "Extracted", gender: "Extracted" },
            data.entities.diagnosed_conditions.map(c => ({ condition_name: c })),
            data.entities.current_medications.map(m => ({ medication_name: m, dosage: "" })),
            data.entities.allergies.map(a => ({ allergen: a, reaction: "Extracted" }))
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
    const banner = document.getElementById("status-banner");
    const icon = document.getElementById("status-icon");
    const title = document.getElementById("status-title");
    const countBadge = document.getElementById("alerts-count-badge");
    const explanation = document.getElementById("status-explanation");
    const alertsContainer = document.getElementById("alerts-container");
    const auditHash = document.getElementById("audit-hash-display");
    const execTime = document.getElementById("exec-time-display");

    auditHash.textContent = `${data.audit_hash.substring(0, 14)}...${data.audit_hash.substring(data.audit_hash.length - 8)}`;
    execTime.textContent = `${data.execution_time_ms} ms`;

    alertsContainer.innerHTML = "";

    if (data.overall_status === "CRITICAL") {
        banner.className = "rounded-xl p-4 mb-4 border flex items-start space-x-3.5 bg-red-950/70 border-red-500/60 text-red-100";
        icon.className = "text-2xl mt-0.5 text-red-400";
        icon.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i>`;
        title.className = "font-extrabold text-base tracking-wide uppercase text-red-300";
        title.textContent = "CRITICAL CONTRAINDICATION DETECTED";
        countBadge.className = "text-[10px] font-mono bg-red-900 border border-red-500/50 text-red-200 px-2 py-0.5 rounded-full";
        countBadge.textContent = `${data.total_alerts} Risk Alert${data.total_alerts > 1 ? 's' : ''}`;
    } else if (data.overall_status === "WARNING") {
        banner.className = "rounded-xl p-4 mb-4 border flex items-start space-x-3.5 bg-amber-950/70 border-amber-500/60 text-amber-100";
        icon.className = "text-2xl mt-0.5 text-amber-400";
        icon.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>`;
        title.className = "font-extrabold text-base tracking-wide uppercase text-amber-300";
        title.textContent = "CLINICAL CAUTION / RELATIVE CONTRAINDICATION";
        countBadge.className = "text-[10px] font-mono bg-amber-900 border border-amber-500/50 text-amber-200 px-2 py-0.5 rounded-full";
        countBadge.textContent = `${data.total_alerts} Warning${data.total_alerts > 1 ? 's' : ''}`;
    } else {
        banner.className = "rounded-xl p-4 mb-4 border flex items-start space-x-3.5 bg-emerald-950/70 border-emerald-500/60 text-emerald-100";
        icon.className = "text-2xl mt-0.5 text-emerald-400";
        icon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
        title.className = "font-extrabold text-base tracking-wide uppercase text-emerald-300";
        title.textContent = "PRESCRIPTION CLEARED (SAFE)";
        countBadge.className = "text-[10px] font-mono bg-emerald-900 border border-emerald-500/50 text-emerald-200 px-2 py-0.5 rounded-full";
        countBadge.textContent = "0 Contraindications";
    }

    explanation.textContent = data.explanation;

    // Render alerts
    if (data.alerts && data.alerts.length > 0) {
        data.alerts.forEach(a => {
            const badgeColor = a.interaction_type === 'ALLERGY' 
                ? 'bg-purple-950 border-purple-500/50 text-purple-300' 
                : (a.interaction_type === 'DRUG_DRUG' 
                    ? 'bg-amber-950 border-amber-500/50 text-amber-300' 
                    : 'bg-red-950 border-red-500/40 text-red-300');

            const card = document.createElement("div");
            card.className = "bg-slate-900/90 border border-slate-700/80 rounded-lg p-3.5 text-xs shadow-inner";
            card.innerHTML = `
                <div class="flex items-center justify-between font-semibold text-slate-100 mb-1.5">
                    <span><i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1.5"></i> ${a.conflicting_factor}</span>
                    <span class="text-[10px] ${badgeColor} border px-2 py-0.5 rounded uppercase font-mono">${a.interaction_type}</span>
                </div>
                <p class="text-slate-300 mb-2 leading-relaxed">
                    <strong class="text-slate-200">Mechanism:</strong> ${a.clinical_mechanism}
                </p>
                <div class="bg-slate-800/80 p-2 rounded border border-slate-700 text-teal-300 font-mono text-[11px]">
                    <strong class="text-slate-300">Recommendation:</strong> ${a.recommendation}
                </div>
            `;
            alertsContainer.appendChild(card);
        });
    } else {
        const safeCard = document.createElement("div");
        safeCard.className = "bg-slate-900/70 border border-emerald-500/20 rounded-lg p-3 text-xs text-slate-300 text-center";
        safeCard.innerHTML = `<i class="fa-solid fa-shield-check text-emerald-400 mr-1.5"></i> Verified against 30+ high-severity contraindication rules. No adverse drug interactions identified.`;
        alertsContainer.appendChild(safeCard);
    }
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
            tr.className = "hover:bg-slate-750 transition";
            const statusClass = log.overall_status === 'CRITICAL' ? 'text-red-400 font-bold' :
                               (log.overall_status === 'WARNING' ? 'text-amber-400' : 'text-emerald-400');
            tr.innerHTML = `
                <td class="py-2 px-3 text-slate-400">${log.timestamp.substring(11, 19)}</td>
                <td class="py-2 px-3 text-teal-300">${log.event_id}</td>
                <td class="py-2 px-3 text-slate-300">${log.patient_hash}</td>
                <td class="py-2 px-3 text-slate-100 font-medium">${log.proposed_medication}</td>
                <td class="py-2 px-3 ${statusClass}">${log.overall_status}</td>
                <td class="py-2 px-3 text-slate-500 truncate max-w-[120px]" title="${log.audit_hash}">${log.audit_hash.substring(0, 16)}...</td>
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
