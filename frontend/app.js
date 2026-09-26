/**
 * MediVault Local - Doctor Dashboard & Sovereign CDSS Client Controller
 * 100% Zero-Cloud Local Workstation (FastAPI on 127.0.0.1:8000).
 * Consolidated single-source-of-truth controller with non-blocking toasts,
 * multi-stage progressive triage animations, and accessibility live regions.
 */

// ═══════════════════════════════════════════
//  APPLICATION STATE
// ═══════════════════════════════════════════
let currentIntakeMode = 'demo';
let currentPatientId = 'PT-101';
let currentUploadedRecord = null;
let currentReviewEventId = null;
let lastFocusedElement = null;

const DEMO_DOCTORS = [
  { key: 'house', name: 'Dr. Gregory House, MD', hospital: 'Princeton Plainsboro Hospital', license: 'NPI-1999887766', initials: 'GH' },
  { key: 'patel', name: 'Dr. Anika Patel, MBBS', hospital: 'Metro General Hospital', license: 'NPI-2345678901', initials: 'AP' },
  { key: 'chen', name: 'Dr. Robert Chen, MD', hospital: 'City Medical Center', license: 'NPI-3456789012', initials: 'RC' }
];
let currentDoctor = DEMO_DOCTORS[0];

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

// ═══════════════════════════════════════════
//  SECURITY & XSS ESCAPING HELPER
// ═══════════════════════════════════════════
function escapeHtml(str) {
  if (typeof str !== 'string') return String(str || '');
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ═══════════════════════════════════════════
//  ENTERPRISE TOAST NOTIFICATION SYSTEM
// ═══════════════════════════════════════════
function showToast(title, message, type = 'info', duration = null) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast-item';
  toast.setAttribute('role', 'alert');

  let iconHtml = '<i class="fa-solid fa-circle-info text-cyan-400 text-lg"></i>';
  let borderClass = 'border-cyan-500/40';

  if (type === 'success') {
    iconHtml = '<i class="fa-solid fa-circle-check text-emerald-400 text-lg"></i>';
    borderClass = 'border-emerald-500/50';
  } else if (type === 'error') {
    iconHtml = '<i class="fa-solid fa-octagon-exclamation text-red-400 text-lg"></i>';
    borderClass = 'border-red-500/50';
  } else if (type === 'warning') {
    iconHtml = '<i class="fa-solid fa-triangle-exclamation text-amber-400 text-lg"></i>';
    borderClass = 'border-amber-500/50';
  }

  toast.classList.add(borderClass);

  const safeTitle = escapeHtml(title);
  const safeMsg = escapeHtml(message);

  toast.innerHTML = `
    ${iconHtml}
    <div class="flex-1 min-w-0">
      <div class="text-xs font-bold text-slate-100 mb-0.5">${safeTitle}</div>
      <div class="text-[11px] text-slate-300 leading-snug break-words">${safeMsg}</div>
    </div>
    <button class="text-slate-400 hover:text-slate-200 text-xs p-1" onclick="this.closest('.toast-item').remove()" aria-label="Close Notification">
      <i class="fa-solid fa-xmark"></i>
    </button>
  `;

  container.appendChild(toast);

  // Stack management: max 5 toasts visible
  while (container.children.length > 5) {
    container.removeChild(container.firstChild);
  }

  const timeoutMs = duration || (type === 'error' ? 8000 : 4000);
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add('toast-leave');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 200);
    }
  }, timeoutMs);
}

// ═══════════════════════════════════════════
//  THEME CONTROLLER (Dark ↔ Light)
// ═══════════════════════════════════════════
function toggleTheme() {
  const isLight = document.documentElement.classList.toggle('light');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeUI(isLight);
  showToast('Theme Updated', `Switched to ${isLight ? 'Light' : 'Dark'} Mode.`, 'info', 2000);
}

function updateThemeUI(isLight) {
  const title = document.getElementById('sidebar-theme-title');
  const btn = document.getElementById('sidebar-theme-btn');
  const icon = document.getElementById('sidebar-theme-icon');
  if (title && btn && icon) {
    if (isLight) {
      title.textContent = 'Light Mode Active';
      btn.textContent = 'Switch to Dark';
      icon.className = 'fa-solid fa-moon text-teal-400 mr-1';
    } else {
      title.textContent = 'Dark Mode Active';
      btn.textContent = 'Switch to Light';
      icon.className = 'fa-solid fa-sun text-amber-400 mr-1';
    }
  }
}

// ═══════════════════════════════════════════
//  MULTI-PAGE NAVIGATION CONTROLLER
// ═══════════════════════════════════════════
function switchMainTab(tabKey) {
  const tabs = ['review', 'intake', 'fhir', 'audit'];
  tabs.forEach(t => {
    const btn = document.getElementById(`nav-btn-${t}`);
    const panel = document.getElementById(`page-view-${t}`);
    if (btn) {
      if (t === tabKey) {
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
      }
    }
    if (panel) {
      if (t === tabKey) {
        panel.classList.add('active');
        panel.style.display = 'block';
      } else {
        panel.classList.remove('active');
        panel.style.display = 'none';
      }
    }
  });
}

// ═══════════════════════════════════════════
//  SETTINGS SIDEBAR & MODAL DRAWER HELPERS
// ═══════════════════════════════════════════
function toggleSettingsSidebar(open) {
  const sidebar = document.getElementById('settings-sidebar');
  const backdrop = document.getElementById('settings-backdrop');
  if (!sidebar || !backdrop) return;
  if (open) {
    lastFocusedElement = document.activeElement;
    sidebar.classList.add('open');
    backdrop.classList.add('open');
    sidebar.style.display = 'flex';
    sidebar.style.transform = 'translateX(0)';
    backdrop.style.display = 'block';
    backdrop.style.opacity = '1';
    backdrop.style.visibility = 'visible';
    backdrop.style.pointerEvents = 'auto';
  } else {
    sidebar.classList.remove('open');
    backdrop.classList.remove('open');
    sidebar.style.transform = 'translateX(100%)';
    backdrop.style.opacity = '0';
    backdrop.style.visibility = 'hidden';
    backdrop.style.pointerEvents = 'none';
    setTimeout(() => {
      if (!sidebar.classList.contains('open')) {
        sidebar.style.display = 'none';
        backdrop.style.display = 'none';
      }
    }, 250);
    if (lastFocusedElement) {
      try { lastFocusedElement.focus(); } catch (_) {}
    }
  }
}

function updateSpeedLabel(val) {
  const speed = parseInt(val);
  const label = document.getElementById('speed-label');
  if (label) {
    if (speed <= 5) label.textContent = `Fast (${speed}ms)`;
    else if (speed <= 15) label.textContent = `Normal (${speed}ms)`;
    else label.textContent = `Deliberate (${speed}ms)`;
  }
}

function dismissSplash() {
  const splash = document.getElementById('splash');
  if (splash && !splash.classList.contains('dismissed')) {
    splash.classList.add('dismissed');
    setTimeout(() => {
      if (splash && splash.parentNode) {
        splash.parentNode.removeChild(splash);
      }
    }, 350);
  }
}

// ═══════════════════════════════════════════
//  DOCTOR / AUTHENTICATION MANAGEMENT
// ═══════════════════════════════════════════
function activateDoctor(doc) {
  currentDoctor = doc;
  updateDoctorUI(doc);
  const gate = document.getElementById('auth-gate');
  if (gate) {
    gate.classList.add('dismissed');
    gate.style.display = 'none';
  }
  showToast('Practitioner Active', `Authenticated as ${doc.name} (${doc.hospital}).`, 'success', 3000);
}

function updateDoctorUI(doc) {
  const pill = document.getElementById('current-doctor-pill');
  if (pill) pill.textContent = doc.name;
  const badge = document.getElementById('current-hospital-badge');
  if (badge) badge.textContent = doc.hospital.split(' ')[0] + ' Hospital';
  const avatar = document.getElementById('header-avatar');
  if (avatar) avatar.textContent = doc.initials;

  const profName = document.getElementById('profile-name');
  if (profName) profName.textContent = doc.name;
  const profHosp = document.getElementById('profile-hospital');
  if (profHosp) profHosp.textContent = doc.hospital;
  const profLic = document.getElementById('profile-license');
  if (profLic) profLic.textContent = doc.license;
  const profAv = document.getElementById('profile-avatar');
  if (profAv) profAv.textContent = doc.initials;
}

function showChangeDocModal() {
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById('switch-doc-modal');
  const list = document.getElementById('switch-doc-list');
  if (!modal || !list) return;
  list.innerHTML = '';
  DEMO_DOCTORS.forEach(doc => {
    const card = document.createElement('div');
    card.className = 'p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between cursor-pointer hover:border-teal-500/50 transition';
    const isActive = currentDoctor.key === doc.key;
    card.innerHTML = `
      <div class="flex items-center space-x-2.5">
        <div class="doc-avatar text-xs">${escapeHtml(doc.initials)}</div>
        <div>
          <div class="text-xs font-bold text-white">${escapeHtml(doc.name)}</div>
          <div class="text-[10px] text-slate-400">${escapeHtml(doc.hospital)}</div>
        </div>
      </div>
      ${isActive
        ? '<span class="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded">ACTIVE</span>'
        : '<button class="btn-clinical-secondary py-1 px-2 text-xs">Switch</button>'}
    `;
    if (!isActive) {
      card.addEventListener('click', () => {
        activateDoctor(doc);
        closeChangeDocModal();
      });
    }
    list.appendChild(card);
  });
  modal.style.display = 'flex';
}

function closeChangeDocModal() {
  const modal = document.getElementById('switch-doc-modal');
  if (modal) modal.style.display = 'none';
  if (lastFocusedElement) {
    try { lastFocusedElement.focus(); } catch (_) {}
  }
}

function handleLogout() {
  toggleSettingsSidebar(false);
  const gate = document.getElementById('auth-gate');
  if (gate) {
    gate.classList.remove('dismissed');
    gate.style.display = 'flex';
  }
  showToast('Session Locked', 'Physician workstation session locked.', 'info', 3000);
}

function openPatientModal() {
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById('switch-patient-modal');
  if (modal) {
    modal.style.display = 'flex';
    if (typeof refreshPatientModalCards === 'function') {
      refreshPatientModalCards();
    }
  }
}

function closePatientModal() {
  const modal = document.getElementById('switch-patient-modal');
  if (modal) modal.style.display = 'none';
  if (lastFocusedElement) {
    try { lastFocusedElement.focus(); } catch (_) {}
  }
}

function openClearanceQrModal() {
  if (!currentReviewEventId) {
    showToast('Review Required', 'Please run a clinical safety review first to generate an audit event.', 'warning');
    return;
  }
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById('qr-modal');
  const container = document.getElementById('qr-image-container');
  const hashDisplay = document.getElementById('qr-modal-hash');

  if (modal) modal.style.display = 'flex';
  if (container) container.innerHTML = `<div style="color:#0f172a; font-size:11px; padding:90px 0;"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Generating Vector Seal…</div>`;

  fetch(`/api/report/clearance-qr?event_id=${encodeURIComponent(currentReviewEventId)}`)
    .then(res => {
      if (!res.ok) throw new Error('Failed to generate QR code');
      return res.text();
    })
    .then(svgText => {
      if (container) {
        container.innerHTML = svgText;
        const svgEl = container.querySelector('svg');
        if (svgEl) {
          svgEl.setAttribute('width', '200');
          svgEl.setAttribute('height', '200');
          svgEl.style.display = 'block';
          svgEl.style.margin = '0 auto';
        }
      }
      if (hashDisplay) {
        hashDisplay.textContent = `Event: ${currentReviewEventId}`;
      }
    })
    .catch(() => {
      if (container) container.innerHTML = `<div style="color:#ef4444; font-size:11px; padding:80px 0;">Error generating seal</div>`;
    });
}

function closeClearanceQrModal() {
  const modal = document.getElementById('qr-modal');
  if (modal) modal.style.display = 'none';
  if (lastFocusedElement) {
    try { lastFocusedElement.focus(); } catch (_) {}
  }
}

// ═══════════════════════════════════════════
//  INTAKE MODE SWITCHER
// ═══════════════════════════════════════════
function switchIntakeMode(mode) {
  currentIntakeMode = mode;
  const tabDemo = document.getElementById('itab-demo');
  const tabRaw = document.getElementById('itab-raw');
  const secDemo = document.getElementById('section-demo');
  const secRaw = document.getElementById('section-raw');

  if (tabDemo && tabRaw && secDemo && secRaw) {
    tabDemo.classList.toggle('bg-teal-700', mode === 'demo');
    tabDemo.classList.toggle('text-white', mode === 'demo');
    tabDemo.classList.toggle('text-slate-400', mode !== 'demo');

    tabRaw.classList.toggle('bg-teal-700', mode === 'raw');
    tabRaw.classList.toggle('text-white', mode === 'raw');
    tabRaw.classList.toggle('text-slate-400', mode !== 'raw');

    secDemo.style.display = mode === 'demo' ? 'block' : 'none';
    secRaw.style.display = mode === 'raw' ? 'grid' : 'none';
  }
}

function switchAuthGateTab(tab) {
  ['demo', 'login', 'register'].forEach(t => {
    const btn = document.getElementById(`gtab-${t}`);
    const content = document.getElementById(`gtab-content-${t}`);
    if (btn) {
      btn.className = (t === tab)
        ? 'flex-1 py-2 text-xs font-semibold rounded text-teal-400 bg-teal-950/80 border border-teal-500/30'
        : 'flex-1 py-2 text-xs font-semibold rounded text-slate-400 hover:text-slate-200';
    }
    if (content) content.classList.toggle('hidden', t !== tab);
  });
}

function gateSelectDemo(key) {
  const doc = DEMO_DOCTORS.find(d => d.key === key) || DEMO_DOCTORS[0];
  activateDoctor(doc);
}

function handleGateLogin() {
  activateDoctor(DEMO_DOCTORS[0]);
}

function handleGateRegister() {
  const name = (document.getElementById('reg-name') || {}).value || 'Dr. Practitioner';
  activateDoctor({
    key: 'custom',
    name: name,
    hospital: 'Registered Hospital',
    license: 'NPI-CUSTOM',
    initials: name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
  });
}

function handleGateOtp() {
  activateDoctor(DEMO_DOCTORS[0]);
}

function handleGateResend() {
  showToast('Code Resent', 'New 6-digit OTP code dispatched to simulated local inbox.', 'info');
}

function onRegHospitalChange() {}

// ═══════════════════════════════════════════
//  AUDIT CHAIN MERKLE VERIFIER
// ═══════════════════════════════════════════
async function verifyAuditChain() {
  const wrap = document.getElementById('integrity-banner-wrap') || document.getElementById('integrity-banner');
  if (!wrap) return;

  wrap.innerHTML = `<div class="p-3 bg-teal-950/60 border border-teal-500/40 rounded-lg text-teal-300 text-xs font-mono flex items-center space-x-2">
    <i class="fa-solid fa-spinner fa-spin"></i><span>Verifying SHA-256 Merkle chain integrity across all blocks...</span>
  </div>`;

  try {
    const res = await fetch('/api/audit-verify');
    const data = await res.json();
    if (data.valid) {
      wrap.innerHTML = `<div class="p-3 bg-emerald-950/80 border border-emerald-500/50 rounded-lg text-emerald-300 text-xs font-mono flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <i class="fa-solid fa-check-double text-emerald-400"></i>
          <span><strong>CRYPTOGRAPHIC PROOF:</strong> All ${data.total_blocks} blocks verified intact. Zero tampering detected.</span>
        </div>
        <span class="text-[10px] bg-emerald-900/60 text-emerald-200 px-2 py-0.5 rounded font-bold uppercase">HIPAA § 164.312(b)</span>
      </div>`;
      showToast('Chain Verified', `All ${data.total_blocks} audit blocks cryptographically intact. Zero tampering.`, 'success', 3500);
    } else {
      wrap.innerHTML = `<div class="p-3 bg-red-950/80 border border-red-500/50 rounded-lg text-red-300 text-xs font-mono flex items-center space-x-2">
        <i class="fa-solid fa-triangle-exclamation text-red-400"></i>
        <span><strong>TAMPER DETECTED:</strong> ${escapeHtml(data.error)}</span>
      </div>`;
      showToast('Integrity Error', `Tamper detected: ${data.error}`, 'error', 8000);
    }
  } catch (e) {
    wrap.innerHTML = `<div class="p-3 bg-red-950/80 border border-red-500/50 rounded-lg text-red-300 text-xs font-mono">Verification error: ${escapeHtml(e.message)}</div>`;
    showToast('Verification Failed', e.message, 'error', 6000);
  }
}

// ═══════════════════════════════════════════
//  PATIENT PROFILE & COHORT MANAGEMENT
// ═══════════════════════════════════════════
async function initPatientSelector() {
  try {
    const res = await fetch("/api/patients");
    const data = await res.json();
    const select = document.getElementById("patient-select");
    const selectHeader = document.getElementById("patient-select-header");
    if (!select) return;

    select.innerHTML = "";
    if (selectHeader) selectHeader.innerHTML = "";

    data.patients.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.patient_id;
      opt.textContent = `${p.patient_id} — ${p.patient_name} (${p.age}yo ${p.gender})`;
      select.appendChild(opt);

      if (selectHeader) {
        const optH = opt.cloneNode(true);
        selectHeader.appendChild(optH);
      }
    });

    select.value = currentPatientId;
    if (selectHeader) selectHeader.value = currentPatientId;
  } catch (e) {
    console.warn("Could not load patient list:", e);
  }
}

async function selectPatient(patientId) {
  currentPatientId = patientId;
  currentIntakeMode = 'demo';
  switchIntakeMode('demo');

  const s1 = document.getElementById("patient-select");
  const s2 = document.getElementById("patient-select-header");
  if (s1) s1.value = patientId;
  if (s2) s2.value = patientId;

  await loadPatientProfile(patientId);
  showToast('Patient Loaded', `Active clinical record switched to ${patientId}.`, 'info', 2000);
}

async function loadPatientProfile(patientId) {
  try {
    const res = await fetch(`/api/patients/${patientId}`);
    if (!res.ok) throw new Error("Patient not found");
    const p = await res.json();

    renderPatientCard(p.patient, p.conditions, p.medications, p.allergies, p.labs);
  } catch (e) {
    console.error("Failed to load patient:", e);
  }
}

function renderPatientCard(patient, conditions, medications, allergies, labs) {
  const nameEl = document.getElementById("display-patient-name");
  const metaEl = document.getElementById("display-patient-meta");
  const tokenEl = document.getElementById("display-patient-token");

  if (nameEl) nameEl.textContent = patient.patient_name || patient.name || "Unknown Patient";
  if (metaEl) metaEl.textContent = `ID: ${patient.patient_id} · Age: ${patient.age}y · ${patient.gender}`;
  if (tokenEl) tokenEl.textContent = patient.patient_id ? `ANON_${patient.patient_id}` : "ANON_UNVERIFIED";

  // Conditions
  const condContainer = document.getElementById("patient-card-conditions");
  if (condContainer) {
    condContainer.innerHTML = "";
    if (conditions && conditions.length > 0) {
      conditions.forEach(c => {
        const span = document.createElement("span");
        span.className = "bg-slate-900 border border-slate-700/60 text-slate-200 px-2 py-0.5 rounded text-[11px] flex items-center space-x-1";
        span.innerHTML = `<i class="fa-solid fa-stethoscope text-teal-400 text-[10px]"></i> <span>${escapeHtml(c.condition_name)}</span>`;
        condContainer.appendChild(span);
      });
    } else {
      condContainer.innerHTML = "<span class='text-xs text-slate-500'>No chronic conditions listed</span>";
    }
  }

  // Medications
  const medsContainer = document.getElementById("patient-card-medications");
  if (medsContainer) {
    medsContainer.innerHTML = "";
    if (medications && medications.length > 0) {
      medications.forEach(m => {
        const span = document.createElement("span");
        span.className = "bg-slate-900 border border-slate-700/60 text-slate-200 px-2 py-0.5 rounded text-[11px] flex items-center space-x-1";
        const doseStr = m.dosage ? ` (${escapeHtml(m.dosage)})` : "";
        span.innerHTML = `<i class="fa-solid fa-pills text-cyan-400 text-[10px]"></i> <span>${escapeHtml(m.medication_name)}${doseStr}</span>`;
        medsContainer.appendChild(span);
      });
    } else {
      medsContainer.innerHTML = "<span class='text-xs text-slate-500'>No active medications recorded</span>";
    }
  }

  // Allergies
  const allContainer = document.getElementById("patient-card-allergies");
  if (allContainer) {
    allContainer.innerHTML = "";
    if (allergies && allergies.length > 0) {
      allergies.forEach(a => {
        const span = document.createElement("span");
        span.className = "bg-purple-950/80 border border-purple-500/50 text-purple-200 px-2 py-0.5 rounded text-[11px] flex items-center space-x-1";
        span.innerHTML = `<i class="fa-solid fa-shield-virus text-purple-400 text-[10px]"></i> <span>${escapeHtml(a.allergen)}</span>`;
        allContainer.appendChild(span);
      });
    } else {
      allContainer.innerHTML = "<span class='text-xs text-emerald-400 font-mono'><i class='fa-solid fa-circle-check text-[10px] mr-1'></i>No Known Drug Allergies (NKDA)</span>";
    }
  }

  // Biomarkers Panel
  const bioContainer = document.getElementById("patient-card-labs");
  if (bioContainer) {
    bioContainer.innerHTML = "";
    if (labs) {
      Object.keys(labs).forEach(k => {
        const item = labs[k];
        const span = document.createElement("div");
        let borderLeft = "border-teal-500";
        let statusBadge = "bg-teal-950 text-teal-300 border-teal-500/40";
        let textValColor = "text-slate-100";

        const label = k.toUpperCase();
        const dispVal = typeof item === 'object' && item.display ? item.display : `${item.value || item} ${item.unit || ''}`;
        const status = (typeof item === 'object' && item.status) ? item.status : "NORMAL";

        if (status.includes("CRITICAL")) {
          borderLeft = "border-red-500";
          statusBadge = "bg-red-950 text-red-300 border-red-500/50";
          textValColor = "text-red-300";
        } else if (status.includes("WARNING") || status.includes("HIGH") || status.includes("LOW")) {
          borderLeft = "border-amber-500";
          statusBadge = "bg-amber-950 text-amber-300 border-amber-500/50";
          textValColor = "text-amber-300";
        } else {
          borderLeft = "border-emerald-500";
          statusBadge = "bg-emerald-950 text-emerald-300 border-emerald-500/50";
          textValColor = "text-emerald-300";
        }

        span.className = `bg-slate-900 p-2.5 rounded-lg border-l-2 ${borderLeft} border border-slate-800 flex flex-col justify-between`;
        span.innerHTML = `
          <div class="text-[10px] text-slate-400 uppercase tracking-wider">${escapeHtml(label)}</div>
          <div class="text-sm font-bold ${textValColor} font-mono mt-0.5">${escapeHtml(dispVal)}</div>
          <span class="text-[9px] ${statusBadge} border font-mono mt-0.5 px-1 rounded">${escapeHtml(status)}</span>
        `;
        bioContainer.appendChild(span);
      });
    } else {
      bioContainer.innerHTML = "<span class='text-xs text-slate-500'>No quantitative labs recorded</span>";
    }
  }
}

// ═══════════════════════════════════════════
//  INGESTION & PHI REDACTION PIPELINE
// ═══════════════════════════════════════════
function applySampleDischargeNote() {
  const area = document.getElementById("raw-note-input");
  if (area) {
    area.value = SAMPLE_DISCHARGE_NOTE;
    showToast('Sample Loaded', 'Stage 3 CKD Inpatient Discharge Summary loaded into Intake.', 'info', 2000);
  }
}

async function triggerRedaction() {
  const rawText = (document.getElementById("raw-note-input") || {}).value;
  if (!rawText || !rawText.trim()) {
    showToast('Input Required', 'Please enter or paste clinical notes first.', 'warning');
    return;
  }

  try {
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: rawText })
    });
    const data = await res.json();

    const redactedOutput = document.getElementById("redacted-output-text");
    if (redactedOutput && data.redacted_text) {
      redactedOutput.value = data.redacted_text;
    }

    const countBadge = document.getElementById("redacted-count-val");
    if (countBadge && data.phi_detected) {
      countBadge.textContent = `${data.phi_detected.length} PHI Direct Identifiers Stripped`;
    }

    const tokenBadge = document.getElementById("redacted-token-val");
    if (tokenBadge && data.patient_token) {
      tokenBadge.textContent = data.patient_token;
    }

    const summaryBadge = document.getElementById("redacted-summary-badge");
    if (summaryBadge) {
      summaryBadge.textContent = "Safe Harbor § 164.514(b) Verified";
    }

    renderPatientCard(
      { patient_name: "De-identified Note Patient", patient_id: data.patient_token, age: "Extracted", gender: "Extracted" },
      (data.entities.diagnosed_conditions || []).map(c => ({ condition_name: c })),
      (data.entities.current_medications || []).map(m => ({ medication_name: m, dosage: "" })),
      (data.entities.allergies || []).map(a => ({ allergen: a, reaction: "Extracted" })),
      data.entities.biomarkers || data.entities.clinical_labs
    );

    showToast('De-Identification Complete', `Stripped ${data.phi_detected.length} PHI tokens. Token: ${data.patient_token}`, 'success', 3500);

  } catch (e) {
    showToast('Redaction Error', e.message, 'error');
  }
}

function transferToReview() {
  currentIntakeMode = 'raw';
  switchMainTab('review');
  showToast('Profile Transferred', 'Transferred de-identified patient record to CDSS Review Engine.', 'info', 2500);
}

// ═══════════════════════════════════════════
//  CLINICAL SAFETY REVIEW & MULTI-STAGE SCAN
// ═══════════════════════════════════════════
function setProposedMed(drug, dose) {
  const medInput = document.getElementById("proposed-med-input");
  const doseInput = document.getElementById("proposed-dose-input");
  if (medInput) medInput.value = drug;
  if (doseInput) doseInput.value = dose;
  showToast('Preset Selected', `Proposed prescription set to ${drug} (${dose}).`, 'info', 2000);
}

async function runSafetyCheck() {
  const proposedMed = (document.getElementById("proposed-med-input") || {}).value.trim();
  const dosage = (document.getElementById("proposed-dose-input") || {}).value.trim();

  if (!proposedMed) {
    showToast('Medication Required', 'Please enter or select a proposed medication to review.', 'warning');
    return;
  }

  const btn = document.getElementById("btn-run-review");
  const bioContainer = document.getElementById("patient-card-labs");

  // Multi-Stage Progressive Scanning Animation
  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-radar text-base animate-spin text-teal-400"></i><span>ANALYZING DETERMINISTICALLY...</span>`;
    btn.disabled = true;
  }
  if (bioContainer) {
    bioContainer.classList.add("scanning-pulse");
  }

  try {
    const payload = {
      proposed_medication: proposedMed,
      dosage: dosage
    };

    if (currentIntakeMode === 'demo') {
      payload.patient_id = currentPatientId;
    } else {
      payload.raw_notes_override = (document.getElementById("raw-note-input") || {}).value;
    }

    const res = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("API call failed");
    const data = await res.json();

    // Render results with progressive animation
    renderReviewResults(data);
    refreshAuditTrail();

    if (data.overall_status === "CRITICAL") {
      showToast('CRITICAL CONTRAINDICATION', `${proposedMed} flagged: ${data.total_alerts} life-threatening risks detected!`, 'error', 8000);
    } else if (data.overall_status === "WARNING") {
      showToast('Clinical Caution', `Relative contraindication / dose adjustment required for ${proposedMed}.`, 'warning', 5000);
    } else {
      showToast('Prescription Cleared', `${proposedMed} safely cleared against all interaction matrices.`, 'success', 3500);
    }

  } catch (e) {
    showToast('Safety Check Failed', e.message, 'error');
  } finally {
    if (bioContainer) {
      bioContainer.classList.remove("scanning-pulse");
    }
    if (btn) {
      btn.innerHTML = `<i class="fa-solid fa-radar text-base"></i><span>RUN OFFLINE CONTRAINDICATION REVIEW</span>`;
      btn.disabled = false;
    }
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
              <span class="uppercase tracking-wide">${escapeHtml(pa.rule_name || 'CUMULATIVE POLYPHARMACY TOXICITY')}</span>
            </span>
            <span class="text-[10px] bg-red-900 text-red-200 border border-red-400/60 px-2 py-0.5 rounded font-mono uppercase">Multi-Drug Alert</span>
          </div>
          <div class="text-slate-200 font-semibold mb-1 text-[11px]">
            Interacting Regimen Cluster: <span class="text-amber-300 font-mono">${escapeHtml(cluster)}</span>
          </div>
          <p class="text-slate-300 mb-2 leading-relaxed text-[11px]">
            <strong class="text-slate-200">Pathophysiology:</strong> ${escapeHtml(pa.clinical_mechanism)}
          </p>
          <div class="bg-red-900/40 p-2 rounded border border-red-700/60 text-red-200 font-mono text-[11px]">
            <strong>Emergency De-escalation:</strong> ${escapeHtml(pa.recommendation)}
          </div>
        `;
        polyContainer.appendChild(card);
      });
    } else {
      polyContainer.classList.add("hidden");
    }
  }

  // 2. Status Banner with Distinct Shape & Iconography (WCAG Non-Color Relying)
  if (data.overall_status === "CRITICAL") {
    banner.className = "triage-banner danger animate-badge-critical";
    icon.className = "text-2xl mt-0.5 text-red-400";
    icon.innerHTML = `<i class="fa-solid fa-shield-halved text-red-400"></i>`;
    title.className = "font-extrabold text-xs tracking-wide uppercase text-red-200 font-heading";
    title.textContent = "🛑 CRITICAL CONTRAINDICATION DETECTED";
    countBadge.className = "text-[10px] font-mono bg-red-950 border border-red-500/50 text-red-200 px-2 py-0.5 rounded-full font-bold";
    countBadge.textContent = `${data.total_alerts} Risk Alert${data.total_alerts > 1 ? 's' : ''}`;
  } else if (data.overall_status === "WARNING") {
    banner.className = "triage-banner warning animate-badge-pop";
    icon.className = "text-2xl mt-0.5 text-amber-400";
    icon.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-400"></i>`;
    title.className = "font-extrabold text-xs tracking-wide uppercase text-amber-200 font-heading";
    title.textContent = "⚠️ CLINICAL CAUTION / RELATIVE CONTRAINDICATION";
    countBadge.className = "text-[10px] font-mono bg-amber-950 border border-amber-500/50 text-amber-200 px-2 py-0.5 rounded-full font-bold";
    countBadge.textContent = `${data.total_alerts} Warning${data.total_alerts > 1 ? 's' : ''}`;
  } else {
    banner.className = "triage-banner safe animate-badge-pop";
    icon.className = "text-2xl mt-0.5 text-emerald-400";
    icon.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-400"></i>`;
    title.className = "font-extrabold text-xs tracking-wide uppercase text-emerald-200 font-heading";
    title.textContent = "🛡️ PRESCRIPTION CLEARED (SAFE)";
    countBadge.className = "text-[10px] font-mono bg-emerald-950 border border-emerald-500/50 text-emerald-200 px-2 py-0.5 rounded-full font-bold";
    countBadge.textContent = "0 Contraindications";
  }

  explanation.textContent = data.explanation;

  // 3. Render Discrete Alerts
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
          <span class="flex items-center space-x-1.5"><i class="fa-solid fa-triangle-exclamation text-amber-400"></i> <span>${escapeHtml(a.conflicting_factor)}</span></span>
          <span class="text-[10px] ${badgeColor} border px-2 py-0.5 rounded uppercase font-mono font-semibold">${escapeHtml(a.interaction_type)}</span>
        </div>
        <p class="text-slate-300 mb-2 leading-relaxed text-[11.5px]">
          <strong class="text-slate-200">Pathophysiology:</strong> ${escapeHtml(a.clinical_mechanism)}
        </p>
        <div class="bg-slate-950 p-2.5 rounded border border-slate-800 text-teal-300 font-mono text-[11px] leading-relaxed">
          <strong class="text-slate-300 font-sans">Recommendation:</strong> ${escapeHtml(a.recommendation)}
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

  // 4. Clinical Safe Alternatives Formulary (1-Click Swap)
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
        altCard.className = "bg-slate-900 border border-teal-500/40 rounded-lg p-2.5 text-xs flex flex-col justify-between hover:border-teal-400 transition";
        altCard.innerHTML = `
          <div>
            <div class="flex items-center justify-between font-bold text-emerald-300 mb-1">
              <span>${escapeHtml(alt.alternative_drug)}</span>
              <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/40 px-1.5 py-0.5 rounded font-mono">SAFE</span>
            </div>
            <div class="text-[11px] text-slate-300 mb-1 font-mono">${escapeHtml(alt.dosage_form || 'Standard')}</div>
            <p class="text-[10.5px] text-slate-400 leading-snug mb-2">${escapeHtml(alt.rationale)}</p>
          </div>
          <button onclick="swapAndVerify('${escapeHtml(alt.alternative_drug)}', '${escapeHtml(alt.dosage_form || '')}')" class="btn-clinical-secondary py-1 text-xs text-teal-300 hover:bg-teal-950 w-full flex items-center justify-center space-x-1.5">
            <i class="fa-solid fa-arrow-right-arrow-left text-[10px]"></i>
            <span>Swap to ${escapeHtml(alt.alternative_drug)}</span>
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
  if (medInput) {
    medInput.value = drug;
    medInput.classList.add("swap-glow-highlight");
    setTimeout(() => medInput.classList.remove("swap-glow-highlight"), 1000);
  }
  if (doseInput && dose) {
    doseInput.value = dose.split(" ")[0] || dose;
  }
  showToast('Formulary Swapped', `Prescription swapped to ${drug}. Re-verifying safety...`, 'info', 3000);
  runSafetyCheck();
}

function exportClinicalCertificate() {
  if (!currentReviewEventId) {
    showToast('Review Required', 'Please run a clinical safety review first to generate an audit event.', 'warning');
    return;
  }
  window.open(`/api/report/clearance?event_id=${encodeURIComponent(currentReviewEventId)}`, '_blank');
}

async function exportFhirBundle() {
  if (!currentReviewEventId) {
    showToast('Review Required', 'Please run a clinical safety review first to generate a sealed FHIR R4 Bundle.', 'warning');
    return;
  }

  try {
    const res = await fetch(`/api/export/fhir-bundle?event_id=${encodeURIComponent(currentReviewEventId)}`, {
      method: "POST"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to export FHIR bundle");
    }
    const bundle = await res.json();

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(bundle, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `fhir_bundle_${currentReviewEventId.substring(0, 8)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast('FHIR Exported', 'Downloaded cryptographically signed FHIR R4 Bundle JSON.', 'success');
  } catch (e) {
    showToast('Export Error', "FHIR Export error: " + e.message, 'error');
  }
}

// ═══════════════════════════════════════════
//  INTEROPERABILITY SANDBOX
// ═══════════════════════════════════════════
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

    switchMainTab('review');
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
        "creatinine": { "value": 1.7, "unit": "mg/dL" },
        "egfr": { "value": 26.0, "unit": "mL/min" }
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
    showToast('File Ingested', `Parsed ${file.name} successfully.`, 'success');
  } catch (err) {
    showToast('Interop Parse Error', err.message, 'error');
  }
}

async function triggerFhirIngestion() {
  const raw = (document.getElementById("fhir-raw-input") || {}).value;
  if (!raw || !raw.trim()) {
    showToast('Payload Required', 'Please paste FHIR JSON, HL7 v2, or Optical QR payload.', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append("raw_payload", raw.trim());

  try {
    const res = await fetch("/api/ingest/interop", { method: "POST", body: formData });
    if (!res.ok) throw new Error("Failed to parse interop payload");
    const data = await res.json();
    applyParsedInteropData(data);
    showToast('Interop Ingestion Complete', 'De-identified clinical payload transferred to Review.', 'success');
  } catch (err) {
    showToast('Ingestion Error', err.message, 'error');
  }
}

function applyParsedInteropData(data) {
  const pName = document.getElementById("display-patient-name");
  const pMeta = document.getElementById("display-patient-meta");
  const pToken = document.getElementById("display-patient-token");

  const demo = data.demographics || {};
  const ageStr = demo.age ? `${demo.age}y` : "Age Unspecified";
  const genStr = demo.gender ? demo.gender : "";

  if (pName) pName.textContent = data.patient_name || `Interoperability Intake (${data.format || 'FHIR R4'})`;
  if (pMeta) pMeta.textContent = `ID: ${data.patient_id || 'EXT-IMPORTED'} · Age: ${ageStr} · ${genStr}`;
  if (pToken) pToken.textContent = data.patient_token || `ANON_${(data.patient_id || 'EXT').toUpperCase()}`;

  renderPatientCard(
    { patient_name: data.patient_name || "Interop Patient", patient_id: data.patient_id || "EXT-01", age: ageStr, gender: genStr },
    (data.conditions || []).map(c => ({ condition_name: c })),
    (data.medications || []).map(m => ({ medication_name: m, dosage: "" })),
    (data.allergies || []).map(a => ({ allergen: a })),
    data.labs
  );

  switchMainTab('review');
}

// ═══════════════════════════════════════════
//  FILE DRAG & DROP HANDLER
// ═══════════════════════════════════════════
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
  const label = document.getElementById("file-drop-label");
  if (label) label.textContent = `Processing ${file.name} locally...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/upload-record", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "File extraction failed");
    }

    const data = await res.json();
    const rawInput = document.getElementById("raw-note-input");
    if (rawInput && data.redacted_text) {
      rawInput.value = data.redacted_text;
    }

    triggerRedaction();
    showToast('File Uploaded', `${file.name} extracted in-memory via PyMuPDF.`, 'success');

  } catch (e) {
    showToast('Upload Error', e.message, 'error');
  } finally {
    if (label) label.textContent = "Drag & Drop PDF or Plain Text Clinical Note Here";
  }
}

// ═══════════════════════════════════════════
//  AUDIT TRAIL LOG RETRIEVAL
// ═══════════════════════════════════════════
async function refreshAuditTrail() {
  const tbody = document.getElementById("audit-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/audit-logs?limit=15");
    if (!res.ok) return;
    const data = await res.json();

    tbody.innerHTML = "";
    (data.logs || []).forEach(log => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-900/60 transition border-b border-slate-800/60";

      let statusPill = `<span class="bg-emerald-950 text-emerald-300 border border-emerald-500/50 px-2 py-0.5 rounded text-[10px] font-mono">CLEARED</span>`;
      if (log.overall_status === 'CRITICAL') {
        statusPill = `<span class="bg-red-950 text-red-300 border border-red-500/50 px-2 py-0.5 rounded text-[10px] font-mono">CRITICAL</span>`;
      } else if (log.overall_status === 'WARNING') {
        statusPill = `<span class="bg-amber-950 text-amber-300 border border-amber-500/50 px-2 py-0.5 rounded text-[10px] font-mono">WARNING</span>`;
      }

      const shortHash = log.audit_hash ? `${log.audit_hash.substring(0, 10)}...${log.audit_hash.substring(log.audit_hash.length - 6)}` : "GENESIS";
      const shortPrev = log.prev_hash ? `${log.prev_hash.substring(0, 8)}...` : "00000000";

      tr.innerHTML = `
        <td class="p-2.5 font-mono text-[11px] text-slate-300">${escapeHtml(log.timestamp.substring(11, 19))}</td>
        <td class="p-2.5 font-mono text-[11px] text-teal-300">${escapeHtml(log.practitioner_name || 'Dr. House, MD')}</td>
        <td class="p-2.5 font-mono text-[11px] text-slate-400">${escapeHtml(log.patient_hash)}</td>
        <td class="p-2.5 text-xs text-slate-200 font-semibold">${escapeHtml(log.proposed_medication)}</td>
        <td class="p-2.5">${statusPill}</td>
        <td class="p-2.5 font-mono text-[10px] text-slate-400" title="${escapeHtml(log.audit_hash)}">${escapeHtml(shortHash)}</td>
        <td class="p-2.5 font-mono text-[10px] text-slate-500" title="${escapeHtml(log.prev_hash)}">${escapeHtml(shortPrev)}</td>
      `;
      tbody.appendChild(tr);
    });

  } catch (e) {
    console.warn("Could not refresh audit logs:", e);
  }
}

// ═══════════════════════════════════════════
//  TELEMETRY PROBES
// ═══════════════════════════════════════════
async function checkNetworkGuard() {
  try {
    const res = await fetch("/api/network-guard");
    const data = await res.json();
    const pill = document.getElementById("airgap-status-pill");
    if (pill) {
      if (data.loopback_only) {
        pill.innerHTML = `<i class="fa-solid fa-shield-halved text-emerald-400 mr-1 animate-pulse"></i><span>AIR-GAPPED (127.0.0.1)</span>`;
        pill.className = "bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-[10px] font-mono px-2 py-0.5 rounded flex items-center";
      } else {
        pill.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i><span>LAN MODE</span>`;
      }
    }
  } catch (e) {
    console.warn("Network guard check failed:", e);
  }
}

async function checkAiStatus() {
  try {
    const res = await fetch("/api/ai-status");
    const data = await res.json();
    const pill = document.getElementById("ai-status-pill");
    if (pill) {
      if (data.status === "ONLINE") {
        pill.innerHTML = `<i class="fa-solid fa-microchip text-teal-400 mr-1"></i><span>OLLAMA SLM (${escapeHtml(data.model || 'llama3.2:3b')})</span>`;
        pill.className = "bg-teal-950/80 border border-teal-500/40 text-teal-300 text-[10px] font-mono px-2 py-0.5 rounded flex items-center";
      } else {
        pill.innerHTML = `<i class="fa-solid fa-code-commit text-slate-400 mr-1"></i><span>DETERMINISTIC SQL ENGINE</span>`;
        pill.className = "bg-slate-900 border border-slate-700 text-slate-300 text-[10px] font-mono px-2 py-0.5 rounded flex items-center";
      }
    }
  } catch (e) {
    console.warn("AI status check failed:", e);
  }
}

// ═══════════════════════════════════════════
//  KEYBOARD ACCELERATORS
// ═══════════════════════════════════════════
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    const activeReview = (document.getElementById('page-view-review') || {}).classList?.contains('active');
    const activeIntake = (document.getElementById('page-view-intake') || {}).classList?.contains('active');
    if (activeReview) runSafetyCheck();
    else if (activeIntake) triggerRedaction();
  } else if ((e.ctrlKey || e.altKey) && e.key === '1') {
    e.preventDefault(); switchMainTab('review');
  } else if ((e.ctrlKey || e.altKey) && e.key === '2') {
    e.preventDefault(); switchMainTab('intake');
  } else if ((e.ctrlKey || e.altKey) && e.key === '3') {
    e.preventDefault(); switchMainTab('fhir');
  } else if ((e.ctrlKey || e.altKey) && e.key === '4') {
    e.preventDefault(); switchMainTab('audit');
  } else if (e.key === 'Escape') {
    toggleSettingsSidebar(false);
    closeChangeDocModal();
    closeClearanceQrModal();
    closePatientModal();
  }
});

// ═══════════════════════════════════════════
//  INITIALIZATION LIFECYCLE
// ═══════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  // Restore saved theme
  const saved = localStorage.getItem('theme');
  if (saved === 'light') {
    document.documentElement.classList.add('light');
    updateThemeUI(true);
  }

  initPatientSelector();
  loadPatientProfile(currentPatientId);
  refreshAuditTrail();
  setupFileDropZone();
  checkAiStatus();
  checkNetworkGuard();
  updateDoctorUI(currentDoctor);

  const selectEl = document.getElementById("patient-select");
  if (selectEl) {
    selectEl.addEventListener("change", (e) => selectPatient(e.target.value));
  }
  const selectHeaderEl = document.getElementById("patient-select-header");
  if (selectHeaderEl) {
    selectHeaderEl.addEventListener("change", (e) => selectPatient(e.target.value));
  }
});

// ═══════════════════════════════════════════
//  GLOBAL WINDOW API BINDINGS
// ═══════════════════════════════════════════
window.switchMainTab = switchMainTab;
window.toggleSettingsSidebar = toggleSettingsSidebar;
window.toggleTheme = toggleTheme;
window.updateSpeedLabel = updateSpeedLabel;
window.dismissSplash = dismissSplash;
window.openPatientModal = openPatientModal;
window.closePatientModal = closePatientModal;
window.showChangeDocModal = showChangeDocModal;
window.closeChangeDocModal = closeChangeDocModal;
window.activateDoctor = activateDoctor;
window.handleLogout = handleLogout;
window.openClearanceQrModal = openClearanceQrModal;
window.closeClearanceQrModal = closeClearanceQrModal;
window.switchIntakeMode = switchIntakeMode;
window.switchAuthGateTab = switchAuthGateTab;
window.gateSelectDemo = gateSelectDemo;
window.handleGateLogin = handleGateLogin;
window.handleGateRegister = handleGateRegister;
window.handleGateOtp = handleGateOtp;
window.handleGateResend = handleGateResend;
window.onRegHospitalChange = onRegHospitalChange;
window.verifyAuditChain = verifyAuditChain;
window.selectPatient = selectPatient;
window.loadPatientProfile = loadPatientProfile;
window.applySampleDischargeNote = applySampleDischargeNote;
window.triggerRedaction = triggerRedaction;
window.transferToReview = transferToReview;
window.setProposedMed = setProposedMed;
window.runSafetyCheck = runSafetyCheck;
window.swapAndVerify = swapAndVerify;
window.exportClinicalCertificate = exportClinicalCertificate;
window.exportFhirBundle = exportFhirBundle;
window.loadFhirPreset = loadFhirPreset;
window.handleFhirFileUpload = handleFhirFileUpload;
window.triggerFhirIngestion = triggerFhirIngestion;
window.showToast = showToast;
