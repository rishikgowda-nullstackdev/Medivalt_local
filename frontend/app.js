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
  const tabs = ['review', 'intake', 'fhir', 'audit', 'analytics'];
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

  if (tabKey === 'analytics') {
    loadClinicalAnalytics();
  }
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
  const attestationHash = document.getElementById('modal-attestation-hash');

  // Reset 3D flip card to front
  toggleQrFlipCard(false);

  if (modal) modal.style.display = 'flex';
  if (container) container.innerHTML = `<div style="color:#0f172a; font-size:11px; padding:90px 0;"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Generating Vector Seal…</div>`;

  const currentSeal = (document.getElementById('audit-hash-display') || {}).textContent || currentReviewEventId;
  if (attestationHash) {
    attestationHash.textContent = currentSeal.length > 10 ? currentSeal : `0x${currentReviewEventId}..ENCLAVE_VALIDATED`;
  }

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
        hashDisplay.textContent = `SHA-256 Digest: ${currentSeal}`;
      }
    })
    .catch(() => {
      if (container) container.innerHTML = `<div style="color:#ef4444; font-size:11px; padding:80px 0;">Error generating seal</div>`;
    });
}

function toggleQrFlipCard(flipToBack) {
  const mesh = document.getElementById('qr-flip-mesh');
  if (!mesh) return;
  if (typeof flipToBack === 'boolean') {
    mesh.classList.toggle('is-flipped', flipToBack);
  } else {
    mesh.classList.toggle('is-flipped');
  }
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

  // Sync 3D Hologram Target with Patient Profile
  if (patientId === 'PT-101') {
    switchHologramTarget('renal');
    updateHologramStatus('HAZARD', 'CONTRAINDICATION HAZARD', 'Renal Glomerular Microvasculature', 'Afferent Arteriolar Vasoconstriction Risk');
  } else if (patientId === 'PT-102') {
    switchHologramTarget('cardiac');
    updateHologramStatus('WARNING', 'BRONCHOSPASM ALERT', 'Bronchopulmonary & Cardiac B2 Receptors', 'Beta-Blocker Airway Resistance');
  } else if (patientId === 'PT-103') {
    switchHologramTarget('cardiac');
    updateHologramStatus('WARNING', 'COAGULATION INTERCEPT', 'Cardiovascular & Hepatic CYP2C9', 'Bleeding Risk / INR Potentiation');
  } else {
    switchHologramTarget('shield');
  }

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
// ═══════════════════════════════════════════
//  MULTI-MEDICINE PRESCRIPTION & FILE INTAKE
// ═══════════════════════════════════════════
let currentPrescriptionMode = 'text';

function switchPrescriptionMode(mode) {
  currentPrescriptionMode = mode;
  const btnText = document.getElementById('presc-mode-text');
  const btnFile = document.getElementById('presc-mode-file');
  const btnSingle = document.getElementById('presc-mode-single');

  const boxText = document.getElementById('presc-box-text');
  const boxFile = document.getElementById('presc-box-file');
  const boxSingle = document.getElementById('presc-box-single');

  if (btnText && btnFile && btnSingle) {
    btnText.className = (mode === 'text') ? 'flex-1 py-1.5 rounded bg-teal-700 text-white transition text-center' : 'flex-1 py-1.5 rounded text-slate-400 hover:text-slate-200 transition text-center';
    btnFile.className = (mode === 'file') ? 'flex-1 py-1.5 rounded bg-teal-700 text-white transition text-center' : 'flex-1 py-1.5 rounded text-slate-400 hover:text-slate-200 transition text-center';
    btnSingle.className = (mode === 'single') ? 'flex-1 py-1.5 rounded bg-teal-700 text-white transition text-center' : 'flex-1 py-1.5 rounded text-slate-400 hover:text-slate-200 transition text-center';
  }

  if (boxText) boxText.style.display = (mode === 'text') ? 'block' : 'none';
  if (boxFile) boxFile.style.display = (mode === 'file') ? 'block' : 'none';
  if (boxSingle) boxSingle.style.display = (mode === 'single') ? 'grid' : 'none';
}

function setMultiPrescriptionPreset(label, text) {
  switchPrescriptionMode('text');
  const prescText = document.getElementById("proposed-prescription-text");
  if (prescText) {
    prescText.value = text;
    const lines = text.split('\n').filter(l => l.trim().length > 0);
    const countBadge = document.getElementById("presc-parsed-count");
    if (countBadge) countBadge.textContent = `${lines.length} orders parsed`;
  }
  showToast('Challenge Preset Loaded', `Loaded ${label} into evaluation suite.`, 'info', 2500);
}

async function handlePrescriptionFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  showToast('Processing Document', `De-identifying and extracting medications from ${file.name}...`, 'info', 3000);

  try {
    const res = await fetch("/api/upload-prescription", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Prescription parsing failed");
    }

    const data = await res.json();
    const statusBox = document.getElementById("presc-file-status");
    const filenameSpan = document.getElementById("presc-file-filename");
    const countSpan = document.getElementById("presc-file-count");

    if (statusBox) statusBox.classList.remove("hidden");
    if (filenameSpan) filenameSpan.innerHTML = `<i class="fa-solid fa-file-lines mr-1.5"></i> ${escapeHtml(file.name)}`;
    if (countSpan) countSpan.textContent = `${(data.prescriptions || []).length} drugs extracted`;

    // Populate the text box
    const prescText = document.getElementById("proposed-prescription-text");
    if (prescText && data.prescriptions && data.prescriptions.length > 0) {
      const formattedLines = data.prescriptions.map((p, idx) => {
        return `${idx + 1}. ${p.medication} ${p.dosage || ''} ${p.route || 'PO'} ${p.frequency || 'QD'}`.trim();
      }).join("\n");
      prescText.value = formattedLines;
    } else if (prescText && data.raw_text) {
      prescText.value = data.raw_text;
    }

    switchPrescriptionMode('text');
    showToast('Prescription Extracted', `Successfully parsed ${(data.prescriptions || []).length} medication order(s).`, 'success', 3500);

  } catch (e) {
    showToast('Upload Error', e.message, 'error', 6000);
  }
}

function setProposedMed(drug, dose) {
  switchPrescriptionMode('single');
  const medInput = document.getElementById("proposed-med-input");
  const doseInput = document.getElementById("proposed-dose-input");
  if (medInput) medInput.value = drug;
  if (doseInput) doseInput.value = dose;
  showToast('Preset Selected', `Proposed prescription set to ${drug} (${dose}).`, 'info', 2000);
}

async function runSafetyCheck() {
  let payload = {};

  if (currentPrescriptionMode === 'single') {
    const proposedMed = (document.getElementById("proposed-med-input") || {}).value.trim();
    const dosage = (document.getElementById("proposed-dose-input") || {}).value.trim();
    if (!proposedMed) {
      showToast('Medication Required', 'Please enter a proposed medication to review.', 'warning');
      return;
    }
    payload.proposed_medication = proposedMed;
    payload.dosage = dosage;
  } else {
    const rawPresc = (document.getElementById("proposed-prescription-text") || {}).value.trim();
    if (!rawPresc) {
      showToast('Prescription Required', 'Please enter or upload a prescription note.', 'warning');
      return;
    }
    payload.prescription_text = rawPresc;
  }

  const btn = document.getElementById("btn-run-review");
  const bioContainer = document.getElementById("patient-card-labs");

  // Multi-Stage Progressive Scanning Animation
  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-radar text-base animate-spin text-teal-400"></i><span>ANALYZING MULTI-DRUG MATRIX...</span>`;
    btn.disabled = true;
  }
  if (bioContainer) {
    bioContainer.classList.add("scanning-pulse");
  }

  try {
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

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "API evaluation failed");
    }
    const data = await res.json();

    // Render results
    renderReviewResults(data);
    refreshAuditTrail();

    if (data.overall_status === "CRITICAL") {
      showToast('CRITICAL CONTRAINDICATION', `Prescription flagged: ${data.total_alerts} severe risks detected!`, 'error', 8000);
    } else if (data.overall_status === "WARNING") {
      showToast('Clinical Caution', `Relative contraindications / adjustments identified.`, 'warning', 5000);
    } else {
      showToast('Prescription Cleared', `All prescribed medications cleared safely!`, 'success', 3500);
    }

  } catch (e) {
    showToast('Safety Check Failed', e.message, 'error');
  } finally {
    if (bioContainer) {
      bioContainer.classList.remove("scanning-pulse");
    }
    if (btn) {
      btn.innerHTML = `<i class="fa-solid fa-stethoscope"></i><span>RUN OFFLINE CONTRAINDICATION REVIEW</span><span class="text-[10px] opacity-75 font-mono ml-1">[Ctrl+Enter]</span>`;
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
  const itemizedContainer = document.getElementById("itemized-medications-cards");
  const summarySpan = document.getElementById("prescribed-bundle-summary");
  const auditHash = document.getElementById("audit-hash-display");
  const execTime = document.getElementById("exec-time-display");

  if (auditHash && data.audit_hash) {
    auditHash.textContent = `${data.audit_hash.substring(0, 14)}...${data.audit_hash.substring(data.audit_hash.length - 8)}`;
  }
  if (execTime && data.execution_time_ms !== undefined) {
    execTime.textContent = `${data.execution_time_ms} ms`;
  }

  // 1. Render Itemized Per-Medication Cards
  if (itemizedContainer) {
    itemizedContainer.innerHTML = "";
    const evals = data.medication_evaluations || [];
    if (summarySpan) {
      summarySpan.textContent = `${evals.length} Prescribed Item${evals.length > 1 ? 's' : ''}`;
    }

    if (evals.length > 0) {
      evals.forEach(ev => {
        const itemCard = document.createElement("div");
        let borderClass = "border-emerald-500/40 bg-slate-900/90";
        let statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-bold"><i class="fa-solid fa-check mr-1"></i>CLEARED</span>`;
        
        if (ev.status === "CRITICAL") {
          borderClass = "border-red-500/80 bg-red-950/20";
          statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-red-950 text-red-200 border border-red-500/80 font-bold animate-pulse"><i class="fa-solid fa-triangle-exclamation mr-1"></i>CRITICAL</span>`;
        } else if (ev.status === "WARNING") {
          borderClass = "border-amber-500/70 bg-amber-950/20";
          statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950 text-amber-200 border border-amber-500/70 font-bold"><i class="fa-solid fa-circle-exclamation mr-1"></i>CAUTION</span>`;
        }

        let alertsHtml = "";
        if (ev.alerts && ev.alerts.length > 0) {
          alertsHtml = `<div class="mt-2 space-y-1.5 border-t border-slate-800/80 pt-2">` + ev.alerts.map(a => `
            <div class="text-[11px] bg-slate-950/80 p-2 rounded border border-slate-800">
              <div class="flex items-center justify-between text-slate-200 font-semibold mb-0.5">
                <span><i class="fa-solid fa-circle-radiation text-amber-400 mr-1"></i> ${escapeHtml(a.conflicting_factor)}</span>
                <span class="text-[9px] uppercase px-1.5 py-0.2 rounded font-mono ${a.is_intra_prescription ? 'bg-purple-950 text-purple-300 border border-purple-500/40' : 'bg-slate-800 text-slate-300'}">${escapeHtml(a.interaction_type)}</span>
              </div>
              <p class="text-[10.5px] text-slate-400 leading-snug m-0">${escapeHtml(a.clinical_mechanism)}</p>
            </div>
          `).join("") + `</div>`;
        }

        let altsHtml = "";
        if (ev.recommended_alternatives && ev.recommended_alternatives.length > 0) {
          altsHtml = `<div class="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between">
            <span class="text-[10.5px] text-teal-300"><i class="fa-solid fa-pills mr-1"></i> Safe Switch: <strong>${escapeHtml(ev.recommended_alternatives[0].alternative_drug)}</strong></span>
            <button type="button" onclick="swapMedicationInPrescription('${escapeHtml(ev.medication)}', '${escapeHtml(ev.recommended_alternatives[0].alternative_drug)}')" class="px-2 py-0.5 bg-teal-950 hover:bg-teal-900 border border-teal-500/40 text-teal-200 text-[10px] rounded font-semibold transition">
              Swap Drug
            </button>
          </div>`;
        }

        itemCard.className = `border ${borderClass} rounded-xl p-3 text-xs shadow-sm transition`;
        itemCard.innerHTML = `
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <span class="font-bold text-slate-100 text-xs font-heading">${escapeHtml(ev.medication)}</span>
              <span class="text-[10px] text-slate-400 font-mono">(${escapeHtml(ev.dosage || 'Std dose')}, ${escapeHtml(ev.route || 'PO')}, ${escapeHtml(ev.frequency || 'QD')})</span>
              ${ev.slm_evaluated ? '<span class="text-[9px] bg-indigo-950 text-indigo-300 border border-indigo-500/40 px-1.5 py-0.2 rounded font-mono">SLM Reasoned</span>' : ''}
            </div>
            ${statusBadge}
          </div>
          ${alertsHtml}
          ${altsHtml}
        `;
        itemizedContainer.appendChild(itemCard);
      });
    }
  }

  // 2. Cumulative Polypharmacy Alerts
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

  // 3. Status Banner with Distinct Shape & Iconography
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

  explanation.textContent = data.summary_explanation || data.explanation;

  // Synchronize 3D Holographic Physiological Target Matrix
  if (data.overall_status === "CRITICAL") {
    updateHologramStatus('HAZARD', 'CONTRAINDICATION HAZARD', 'Renal Glomerular Microvasculature', data.summary_explanation || 'Afferent Arteriolar Vasoconstriction & eGFR Drop');
  } else if (data.overall_status === "WARNING") {
    updateHologramStatus('WARNING', 'CLINICAL WARNING', 'Target Organ Receptors Monitored', data.summary_explanation || 'Relative Contraindication / Titration Required');
  } else {
    updateHologramStatus('SAFE', 'CLEARANCE APPROVED', 'Physiological Target Stabilized', 'Zero contraindications detected across local SQLite matrices');
  }

  // 4. Standalone discrete alerts if no itemized cards or for backward compatibility
  alertsContainer.innerHTML = "";
  const standardAlerts = (data.alerts || []).filter(a => a.interaction_type !== "POLYPHARMACY");
  if (!data.medication_evaluations && standardAlerts.length > 0) {
    standardAlerts.forEach(a => {
      let badgeColor = 'bg-red-950 border-red-500/40 text-red-300';
      if (a.interaction_type === 'ALLERGY') badgeColor = 'bg-purple-950 border-purple-500/50 text-purple-300';
      else if (a.interaction_type === 'DRUG_DRUG') badgeColor = 'bg-amber-950 border-amber-500/50 text-amber-300';
      else if (a.interaction_type === 'LAB_THRESHOLD') badgeColor = 'bg-cyan-950 border-cyan-500/50 text-cyan-300';
      else if (a.interaction_type === 'BEERS_CRITERIA') badgeColor = 'bg-amber-950 border-yellow-500/60 text-yellow-300';
      else if (a.interaction_type === 'RENAL_TITRATION') badgeColor = 'bg-orange-950 border-orange-500/60 text-orange-300';

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
  }

  // 5. Global Safe Alternatives Formulary
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
        <span class="text-[10px] text-slate-400 font-mono">1-Click Swap</span>
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

function swapMedicationInPrescription(oldDrug, newDrug) {
  const prescText = document.getElementById("proposed-prescription-text");
  if (prescText && prescText.value) {
    const reg = new RegExp(oldDrug, "gi");
    prescText.value = prescText.value.replace(reg, newDrug);
    showToast('Prescription Updated', `Swapped ${oldDrug} -> ${newDrug} in prescription bundle. Re-evaluating...`, 'info', 3000);
    runSafetyCheck();
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
  } else if ((e.ctrlKey || e.altKey) && e.key === '5') {
    e.preventDefault(); switchMainTab('analytics');
  } else if ((e.ctrlKey || e.altKey) && (e.key === '6' || e.key === 'd' || e.key === 'D')) {
    e.preventDefault(); openJudgeDemoModal();
  } else if (e.key === 'Escape') {
    toggleSettingsSidebar(false);
    closeChangeDocModal();
    closeClearanceQrModal();
    closePatientModal();
    closeJudgeDemoModal();
  }

  // Hotkeys 1-4 when Judge Demo Modal is active
  const demoModal = document.getElementById('modal-judge-demo');
  if (demoModal && demoModal.style.display !== 'none' && !e.ctrlKey && !e.altKey && !e.metaKey) {
    if (e.key === '1') { e.preventDefault(); executeDemoScenario('renal_collapse'); }
    else if (e.key === '2') { e.preventDefault(); executeDemoScenario('triple_whammy'); }
    else if (e.key === '3') { e.preventDefault(); executeDemoScenario('hidden_anaphylaxis'); }
    else if (e.key === '4') { e.preventDefault(); executeDemoScenario('anticoagulant_hemorrhage'); }
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

  // Initialize 3D Holographic Matrix and 3D Hover Tilt Physics
  initHologramMatrix();
  init3DCardTilt();

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

// ═══════════════════════════════════════════
//  CLINICAL ANALYTICS & INSIGHTS CONTROLLER
// ═══════════════════════════════════════════
let currentAnalyticsDays = null;
let chartTriageInstance = null;
let chartDrugsInstance = null;
let chartTrendsInstance = null;

function setAnalyticsDays(days) {
  currentAnalyticsDays = days;
  
  // Update button active styling
  const allBtn = document.getElementById("filter-analytics-all");
  const d30Btn = document.getElementById("filter-analytics-30");
  const d7Btn = document.getElementById("filter-analytics-7");

  const activeClass = "px-2.5 py-1 rounded text-teal-300 font-semibold bg-teal-950/80 border border-teal-500/30";
  const inactiveClass = "px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 border-0 bg-transparent";

  if (allBtn) allBtn.className = (days === null) ? activeClass : inactiveClass;
  if (d30Btn) d30Btn.className = (days === 30) ? activeClass : inactiveClass;
  if (d7Btn) d7Btn.className = (days === 7) ? activeClass : inactiveClass;

  loadClinicalAnalytics();
}

async function loadClinicalAnalytics() {
  const refreshIcon = document.getElementById("btn-refresh-analytics-icon");
  if (refreshIcon) refreshIcon.classList.add("fa-spin");

  try {
    const url = currentAnalyticsDays ? `/api/analytics/summary?days=${currentAnalyticsDays}` : '/api/analytics/summary';
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Analytics fetch failed: ${res.status}`);
    const data = await res.json();

    // 1. Update KPI Stat Cards
    const kpiTotal = document.getElementById("analytics-kpi-total");
    const kpiPrevented = document.getElementById("analytics-kpi-prevented");
    const kpiSafe = document.getElementById("analytics-kpi-safe");
    const kpiFlagRate = document.getElementById("analytics-kpi-flagrate");
    const kpiEgress = document.getElementById("analytics-kpi-egress");
    const latencyVal = document.getElementById("analytics-latency-val");

    if (kpiTotal) kpiTotal.textContent = data.total_reviews || 0;
    if (kpiPrevented) kpiPrevented.textContent = data.flagged_reviews || 0;
    if (kpiSafe) kpiSafe.textContent = data.clear_reviews || 0;
    if (kpiFlagRate) kpiFlagRate.textContent = `${data.flag_rate_pct || 0}% Intercept Rate`;
    if (kpiEgress) kpiEgress.textContent = `${data.sovereign_egress_bytes || 0} Bytes`;
    if (latencyVal) latencyVal.textContent = `${data.avg_execution_latency_ms || 18.5}ms`;

    // 2. Update Triage Legend Numbers
    const alerts = data.alert_distribution || {};
    const critEl = document.getElementById("legend-critical-count");
    const warnEl = document.getElementById("legend-warning-count");
    const safeEl = document.getElementById("legend-safe-count");

    if (critEl) critEl.textContent = alerts.CRITICAL || 0;
    if (warnEl) warnEl.textContent = alerts.WARNING || 0;
    if (safeEl) safeEl.textContent = alerts.SAFE || 0;

    // 3. Render Triage Doughnut Chart
    renderTriageChart(alerts);

    // 4. Render Top Flagged Drugs Horizontal Bar Chart
    renderFlaggedDrugsChart(data.top_flagged_drugs || []);

    // 5. Render High-Risk Leaderboard Table
    renderLeaderboard(data.dangerous_combinations_leaderboard || []);

    // 6. Fetch Trends & Render Time-Series
    await loadTrendsChart();

  } catch (err) {
    console.error("Clinical analytics loading error:", err);
    showToast("Analytics Error", "Failed to retrieve local clinical analytics.", "warning", 3000);
  } finally {
    if (refreshIcon) refreshIcon.classList.remove("fa-spin");
  }
}

function renderTriageChart(alerts) {
  const canvas = document.getElementById("chart-triage-distribution");
  if (!canvas || typeof Chart === 'undefined') return;

  const ctx = canvas.getContext("2d");
  if (chartTriageInstance) {
    chartTriageInstance.destroy();
  }

  const critical = alerts.CRITICAL || 0;
  const warning = alerts.WARNING || 0;
  const safe = alerts.SAFE || 0;
  const total = critical + warning + safe;

  chartTriageInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Critical Contraindications', 'Warning Thresholds', 'Safe Clearances'],
      datasets: [{
        data: total > 0 ? [critical, warning, safe] : [1, 1, 1],
        backgroundColor: [
          '#ef4444', // Red-500
          '#f59e0b', // Amber-500
          '#10b981', // Emerald-500
        ],
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#cbd5e1',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              const val = context.parsed;
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${context.label}: ${val} (${pct}%)`;
            }
          }
        }
      },
      cutout: '72%'
    }
  });
}

function renderFlaggedDrugsChart(topDrugs) {
  const canvas = document.getElementById("chart-flagged-drugs");
  if (!canvas || typeof Chart === 'undefined') return;

  const ctx = canvas.getContext("2d");
  if (chartDrugsInstance) {
    chartDrugsInstance.destroy();
  }

  // Fallback if empty
  const drugs = topDrugs.length > 0 ? topDrugs : [
    { drug: "Ibuprofen", count: 8, severity: "CRITICAL" },
    { drug: "Warfarin", count: 5, severity: "CRITICAL" },
    { drug: "Metformin", count: 3, severity: "WARNING" },
    { drug: "Diphenhydramine", count: 3, severity: "CRITICAL" },
    { drug: "Propranolol", count: 2, severity: "CRITICAL" }
  ];

  const labels = drugs.map(d => d.drug);
  const counts = drugs.map(d => d.count);
  const colors = drugs.map(d => (d.severity === 'WARNING') ? 'rgba(245, 158, 11, 0.85)' : 'rgba(239, 68, 68, 0.85)');
  const borderColors = drugs.map(d => (d.severity === 'WARNING') ? '#f59e0b' : '#ef4444');

  chartDrugsInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Fatal / Adverse Interceptions',
        data: counts,
        backgroundColor: colors,
        borderColor: borderColors,
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#cbd5e1',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 8
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          ticks: { color: '#94a3b8', font: { family: 'monospace', size: 10 }, stepSize: 1 }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f1f5f9', font: { family: 'sans-serif', size: 11, weight: '600' } }
        }
      }
    }
  });
}

async function loadTrendsChart() {
  const canvas = document.getElementById("chart-trends-volume");
  if (!canvas || typeof Chart === 'undefined') return;

  try {
    const res = await fetch('/api/analytics/trends?limit=10');
    if (!res.ok) return;
    const data = await res.json();

    const ctx = canvas.getContext("2d");
    if (chartTrendsInstance) {
      chartTrendsInstance.destroy();
    }

    const labels = data.labels || [];
    const totals = data.datasets?.total_reviews || [];
    const flagged = data.datasets?.flagged_reviews || [];
    const egress = data.datasets?.sovereign_egress_bytes || [];

    chartTrendsInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Total Review Volume',
            data: totals,
            borderColor: '#0d9488', // Teal
            backgroundColor: 'rgba(13, 148, 136, 0.1)',
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#14b8a6',
            pointRadius: 3
          },
          {
            label: 'Contraindications Flagged',
            data: flagged,
            borderColor: '#f43f5e', // Rose
            backgroundColor: 'rgba(244, 63, 94, 0.08)',
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#f43f5e',
            pointRadius: 3
          },
          {
            label: 'Cloud Egress Bytes (0 Bytes Strict)',
            data: egress,
            borderColor: '#10b981', // Emerald
            borderDash: [5, 5],
            pointRadius: 0,
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1e293b',
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            borderColor: '#334155',
            borderWidth: 1,
            padding: 8
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: { color: '#94a3b8', font: { family: 'monospace', size: 10 } }
          },
          y: {
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: { color: '#94a3b8', font: { family: 'monospace', size: 10 }, stepSize: 1 },
            beginAtZero: true
          }
        }
      }
    });
  } catch (e) {
    console.error("Trends chart error:", e);
  }
}

function renderLeaderboard(combos) {
  const tbody = document.getElementById("analytics-leaderboard-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  combos.forEach(c => {
    const sevBadge = (c.severity === 'WARNING')
      ? '<span class="status-pill status-pill-warning text-[10px]"><i class="fa-solid fa-triangle-exclamation mr-1"></i> WARNING</span>'
      : '<span class="status-pill status-pill-critical text-[10px]"><i class="fa-solid fa-circle-exclamation mr-1"></i> CRITICAL</span>';

    tbody.innerHTML += `
      <tr class="hover:bg-slate-900/60 transition">
        <td class="p-2.5 text-center font-mono font-bold text-teal-400">#${c.rank}</td>
        <td class="p-2.5 font-bold text-white">${c.drugs}</td>
        <td class="p-2.5 text-slate-300 font-medium">${c.name}</td>
        <td class="p-2.5">${sevBadge}</td>
        <td class="p-2.5 text-slate-400 text-[11px] leading-relaxed">${c.mechanism}</td>
        <td class="p-2.5 text-emerald-300 text-[11px] font-medium">${c.safe_alternative}</td>
      </tr>
    `;
  });
}

window.setAnalyticsDays = setAnalyticsDays;
window.loadClinicalAnalytics = loadClinicalAnalytics;

// ═══════════════════════════════════════════
//  🌌 SOVEREIGN 3D HOLOGRAPHIC VECTOR ENGINE
//  Pure HTML5 Canvas 2D/3D Matrix Projection
//  100% Offline · 0 Network Overhead · 60 FPS
// ═══════════════════════════════════════════
let globalHologram3DInstance = null;

class HolographicMatrix3D {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.target = 'renal'; // 'renal' | 'cardiac' | 'hepatic' | 'shield'
    this.status = 'HAZARD'; // 'HAZARD' | 'WARNING' | 'SAFE' | 'NEUTRAL'
    
    this.pitch = 0.25;
    this.yaw = 0.6;
    this.targetPitch = 0.25;
    this.targetYaw = 0.6;
    this.autoSpinSpeed = 0.007;
    
    this.isDragging = false;
    this.lastX = 0;
    this.lastY = 0;
    this.pulsePhase = 0;
    this.animFrameId = null;

    this.particles = [];
    this.initParticles(35);
    this.initEvents();
    this.resize();
    this.startLoop();
  }

  initParticles(count) {
    this.particles = [];
    for (let i = 0; i < count; i++) {
      const radius = 90 + Math.random() * 50;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI;
      this.particles.push({
        x: radius * Math.cos(phi) * Math.cos(theta),
        y: radius * Math.sin(phi),
        z: radius * Math.cos(phi) * Math.sin(theta),
        size: Math.random() * 1.5 + 0.8,
        speed: (Math.random() * 0.008 + 0.004) * (Math.random() > 0.5 ? 1 : -1)
      });
    }
  }

  initEvents() {
    window.addEventListener('resize', () => this.resize());

    // Mouse Controls
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastX = e.clientX;
      this.lastY = e.clientY;
      this.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.lastX;
      const dy = e.clientY - this.lastY;
      this.targetYaw += dx * 0.012;
      this.targetPitch += dy * 0.012;
      this.targetPitch = Math.max(-1.3, Math.min(1.3, this.targetPitch));
      this.lastX = e.clientX;
      this.lastY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        if (this.canvas) this.canvas.style.cursor = 'grab';
      }
    });

    // Touch Controls
    this.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.lastX = e.touches[0].clientX;
        this.lastY = e.touches[0].clientY;
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (!this.isDragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - this.lastX;
      const dy = e.touches[0].clientY - this.lastY;
      this.targetYaw += dx * 0.015;
      this.targetPitch += dy * 0.015;
      this.targetPitch = Math.max(-1.3, Math.min(1.3, this.targetPitch));
      this.lastX = e.touches[0].clientX;
      this.lastY = e.touches[0].clientY;
    }, { passive: true });

    window.addEventListener('touchend', () => {
      this.isDragging = false;
    });
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 600;
    this.height = rect.height || 190;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.scale(dpr, dpr);
  }

  setTarget(targetKey) {
    this.target = targetKey;
    ['renal', 'cardiac', 'hepatic', 'shield'].forEach(k => {
      const btn = document.getElementById(`organ-tab-${k}`);
      if (btn) {
        if (k === targetKey) {
          btn.className = 'px-2.5 py-1 rounded bg-teal-500/25 border border-teal-400/60 text-teal-200 font-bold transition';
        } else {
          btn.className = 'px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-400 hover:text-slate-200 transition';
        }
      }
    });
  }

  setStatus(statusKey, title, targetName, loadName) {
    this.status = statusKey;
    const hudBadge = document.getElementById('hologram-hud-status-badge');
    const hudText = document.getElementById('hologram-hud-status-text');
    const hudTarget = document.getElementById('hologram-hud-target');
    const hudLoad = document.getElementById('hologram-hud-load');

    if (hudTarget && targetName) hudTarget.textContent = targetName;
    if (hudLoad && loadName) hudLoad.textContent = loadName;

    if (hudBadge && hudText) {
      if (statusKey === 'HAZARD') {
        hudBadge.className = 'px-2.5 py-1 rounded-full bg-red-950/80 border border-red-500/70 text-red-300 text-[10px] font-mono font-bold flex items-center space-x-1.5 shadow-lg glow-critical-pulse';
        hudText.textContent = title || 'CONTRAINDICATION HAZARD';
      } else if (statusKey === 'WARNING') {
        hudBadge.className = 'px-2.5 py-1 rounded-full bg-amber-950/80 border border-amber-500/70 text-amber-300 text-[10px] font-mono font-bold flex items-center space-x-1.5 shadow-lg';
        hudText.textContent = title || 'CLINICAL WARNING';
      } else {
        hudBadge.className = 'px-2.5 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/70 text-emerald-300 text-[10px] font-mono font-bold flex items-center space-x-1.5 shadow-lg glow-safe-pulse';
        hudText.textContent = title || 'CLEARANCE APPROVED';
      }
    }
  }

  generateMesh() {
    const nodes = [];
    const edges = [];

    if (this.target === 'renal') {
      // 3D Kidney Lobule & Glomerular Capillary Mesh
      const count = 16;
      for (let i = 0; i < count; i++) {
        const u = (i / count) * Math.PI * 2;
        // Kidney contour equation in 3D
        const r = 48 + 12 * Math.cos(u);
        const x = r * Math.sin(u) * 0.9 - 10;
        const y = r * Math.cos(u) * 1.35;
        const z = Math.sin(u * 2) * 16;
        nodes.push({ x, y, z, isAlert: this.status === 'HAZARD' && i % 3 === 0 });
      }
      for (let i = 0; i < count; i++) {
        edges.push([i, (i + 1) % count]);
        if (i % 2 === 0) edges.push([i, (i + 8) % count]);
      }
      // Glomerular Capillary Core
      for (let j = 0; j < 8; j++) {
        const a = (j / 8) * Math.PI * 2;
        nodes.push({
          x: Math.cos(a) * 18 - 8,
          y: Math.sin(a) * 22,
          z: Math.sin(a * 3) * 12,
          isGlomerulus: true
        });
      }
      for (let j = 0; j < 8; j++) {
        edges.push([count + j, count + ((j + 1) % 8)]);
        edges.push([count + j, j * 2]);
      }
    } else if (this.target === 'cardiac') {
      // 3D Cardiac 4-Chamber Wireframe
      const rings = 4;
      const ptsPerRing = 10;
      for (let r = 0; r < rings; r++) {
        const y = (r - 1.5) * 32;
        const rad = Math.sin((r / (rings - 1)) * Math.PI) * 55 + 12;
        for (let p = 0; p < ptsPerRing; p++) {
          const theta = (p / ptsPerRing) * Math.PI * 2;
          nodes.push({
            x: Math.cos(theta) * rad,
            y: y,
            z: Math.sin(theta) * rad * 0.85,
            isCardiacNode: true
          });
        }
      }
      for (let r = 0; r < rings; r++) {
        const start = r * ptsPerRing;
        for (let p = 0; p < ptsPerRing; p++) {
          edges.push([start + p, start + ((p + 1) % ptsPerRing)]);
          if (r < rings - 1) {
            edges.push([start + p, start + ptsPerRing + p]);
          }
        }
      }
    } else if (this.target === 'hepatic') {
      // 3D Hexagonal Liver Lobule Lattice
      const hexCount = 7;
      for (let h = 0; h < hexCount; h++) {
        const cx = (h === 0 ? 0 : Math.cos((h - 1) * Math.PI / 3) * 45);
        const cy = (h === 0 ? 0 : Math.sin((h - 1) * Math.PI / 3) * 38);
        for (let k = 0; k < 6; k++) {
          const ang = (k / 6) * Math.PI * 2;
          nodes.push({
            x: cx + Math.cos(ang) * 20,
            y: cy + Math.sin(ang) * 20,
            z: Math.sin(ang * 2 + h) * 14
          });
        }
      }
      for (let h = 0; h < hexCount; h++) {
        const offset = h * 6;
        for (let k = 0; k < 6; k++) {
          edges.push([offset + k, offset + ((k + 1) % 6)]);
        }
      }
    } else {
      // Sovereign Enclave Shield Geodesic Dome
      const lat = 5;
      const lon = 10;
      for (let i = 0; i < lat; i++) {
        const phi = (i / (lat - 1)) * Math.PI - Math.PI / 2;
        const rad = Math.cos(phi) * 58;
        const y = Math.sin(phi) * 58;
        for (let j = 0; j < lon; j++) {
          const theta = (j / lon) * Math.PI * 2;
          nodes.push({
            x: rad * Math.cos(theta),
            y: y,
            z: rad * Math.sin(theta)
          });
        }
      }
      for (let i = 0; i < lat; i++) {
        const start = i * lon;
        for (let j = 0; j < lon; j++) {
          edges.push([start + j, start + ((j + 1) % lon)]);
          if (i < lat - 1) {
            edges.push([start + j, start + lon + j]);
          }
        }
      }
    }

    return { nodes, edges };
  }

  project(x, y, z, cx, cy) {
    // 3D Rotation Matrix Around Yaw (Y-axis) and Pitch (X-axis)
    const cosY = Math.cos(this.yaw);
    const sinY = Math.sin(this.yaw);
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    const cosP = Math.cos(this.pitch);
    const sinP = Math.sin(this.pitch);
    const y2 = y * cosP - z1 * sinP;
    const z2 = y * sinP + z1 * cosP;

    // Perspective Projection
    const focalLength = 320;
    const scale = focalLength / (focalLength + z2);
    return {
      px: cx + x1 * scale,
      py: cy + y2 * scale,
      scale: scale,
      z: z2
    };
  }

  startLoop() {
    const loop = () => {
      this.update();
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  update() {
    this.pulsePhase += 0.05;

    if (!this.isDragging) {
      this.targetYaw += this.autoSpinSpeed;
    }

    // Smooth Euler Interpolation
    this.yaw += (this.targetYaw - this.yaw) * 0.08;
    this.pitch += (this.targetPitch - this.pitch) * 0.08;

    // Update Telemetry Display
    const angleHud = document.getElementById('hologram-hud-angle');
    if (angleHud) {
      const pDeg = Math.round((this.pitch * 180) / Math.PI);
      const yDeg = Math.round(((this.yaw % (Math.PI * 2)) * 180) / Math.PI);
      angleHud.textContent = `Pitch: ${pDeg}° · Yaw: ${yDeg}°`;
    }
  }

  render() {
    const ctx = this.ctx;
    if (!ctx || !this.canvas) return;

    const w = this.width;
    const h = this.height;
    const cx = w / 2;
    const cy = h / 2;

    ctx.clearRect(0, 0, w, h);

    // Color Palette mapping based on Status
    let primaryColor = '#14b8a6'; // Teal
    let accentGlow = 'rgba(20, 184, 166, 0.4)';
    let nodeColor = '#2dd4bf';
    let pulseShockwaveColor = 'rgba(244, 63, 94, ';

    if (this.status === 'HAZARD') {
      primaryColor = '#f43f5e'; // Rose
      accentGlow = 'rgba(244, 63, 94, 0.55)';
      nodeColor = '#fda4af';
    } else if (this.status === 'WARNING') {
      primaryColor = '#f59e0b'; // Amber
      accentGlow = 'rgba(245, 158, 11, 0.5)';
      nodeColor = '#fde68a';
      pulseShockwaveColor = 'rgba(245, 158, 11, ';
    } else if (this.status === 'SAFE') {
      primaryColor = '#10b981'; // Emerald
      accentGlow = 'rgba(16, 185, 129, 0.5)';
      nodeColor = '#a7f3d0';
      pulseShockwaveColor = 'rgba(16, 185, 129, ';
    }

    // 1. Draw Ambient Center Holographic Gimbal Rings
    ctx.save();
    ctx.strokeStyle = accentGlow;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.ellipse(cx, cy, 110, 42, this.yaw * 0.3, 0, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.ellipse(cx, cy, 95, 80, -this.pitch * 0.4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    // 2. Render Particle Starfield
    ctx.save();
    this.particles.forEach(pt => {
      pt.x += pt.speed * 20;
      const proj = this.project(pt.x, pt.y, pt.z, cx, cy);
      const alpha = Math.max(0.1, Math.min(0.7, (proj.z + 100) / 200));
      ctx.fillStyle = primaryColor;
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.arc(proj.px, proj.py, pt.size * proj.scale, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();

    // 3. Render 3D Wireframe Organ Mesh
    const { nodes, edges } = this.generateMesh();
    const projectedNodes = nodes.map(n => ({
      ...n,
      ...this.project(n.x, n.y, n.z, cx, cy)
    }));

    // Draw Edges with Depth Occlusion
    ctx.save();
    edges.forEach(([i1, i2]) => {
      const p1 = projectedNodes[i1];
      const p2 = projectedNodes[i2];
      if (!p1 || !p2) return;

      const avgZ = (p1.z + p2.z) / 2;
      const alpha = Math.max(0.15, Math.min(0.85, (avgZ + 120) / 240));

      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.strokeStyle = primaryColor;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = Math.max(1, 1.8 * ((p1.scale + p2.scale) / 2));
      ctx.stroke();
    });
    ctx.restore();

    // Draw Nodes and Highlight Active Sites
    ctx.save();
    projectedNodes.forEach(p => {
      const alpha = Math.max(0.2, Math.min(0.95, (p.z + 120) / 240));
      ctx.globalAlpha = alpha;

      if (p.isAlert || (p.isGlomerulus && this.status === 'HAZARD')) {
        // Pulsing Target Lock Highlight
        const pulse = (Math.sin(this.pulsePhase * 2) + 1) / 2;
        ctx.fillStyle = '#f43f5e';
        ctx.beginPath();
        ctx.arc(p.px, p.py, (4 + pulse * 3) * p.scale, 0, Math.PI * 2);
        ctx.fill();

        // Expanding Shockwave Wavefront
        ctx.strokeStyle = `${pulseShockwaveColor}${1 - pulse})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(p.px, p.py, (8 + pulse * 14) * p.scale, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        ctx.fillStyle = nodeColor;
        ctx.beginPath();
        ctx.arc(p.px, p.py, 2.2 * p.scale, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    ctx.restore();

    // 4. Draw HUD Targeting Reticle overlay
    ctx.save();
    ctx.strokeStyle = primaryColor;
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = 1;
    const boxSize = 35;
    // Crosshairs
    ctx.beginPath();
    ctx.moveTo(cx - boxSize, cy); ctx.lineTo(cx - boxSize + 10, cy);
    ctx.moveTo(cx + boxSize - 10, cy); ctx.lineTo(cx + boxSize, cy);
    ctx.moveTo(cx, cy - boxSize); ctx.lineTo(cx, cy - boxSize + 10);
    ctx.moveTo(cx, cy + boxSize - 10); ctx.lineTo(cx, cy + boxSize);
    ctx.stroke();
    ctx.restore();
  }
}

// ═══════════════════════════════════════════
//  3D HOLOGRAPHIC API WRAPPERS
// ═══════════════════════════════════════════
function initHologramMatrix() {
  if (!globalHologram3DInstance && document.getElementById('canvas-hologram-3d')) {
    globalHologram3DInstance = new HolographicMatrix3D('canvas-hologram-3d');
  }
}

function switchHologramTarget(targetKey) {
  if (globalHologram3DInstance) {
    globalHologram3DInstance.setTarget(targetKey);
  }
}

function updateHologramStatus(statusKey, title, targetName, loadName) {
  if (globalHologram3DInstance) {
    globalHologram3DInstance.setStatus(statusKey, title, targetName, loadName);
  }
}

// ═══════════════════════════════════════════
//  🪞 DYNAMIC 3D CARD HOVER TILT & SPECULAR GLARE
//  Smooth CSS3 Perspective Tilt Physics
// ═══════════════════════════════════════════
function init3DCardTilt() {
  const cards = document.querySelectorAll('.card-3d-tilt');
  cards.forEach(card => {
    let ticking = false;

    card.addEventListener('mousemove', (e) => {
      if (ticking) return;
      ticking = true;

      requestAnimationFrame(() => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotX = -((y - centerY) / centerY) * 6.5; // Max 6.5 deg tilt
        const rotY = ((x - centerX) / centerX) * 6.5;

        card.style.transform = `perspective(1000px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) translateZ(4px)`;
        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);
        card.style.setProperty('--sheen-opacity', '1');
        ticking = false;
      });
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)';
      card.style.setProperty('--sheen-opacity', '0');
    });
  });
}

// Global Window Exports
window.initHologramMatrix = initHologramMatrix;
window.switchHologramTarget = switchHologramTarget;
window.updateHologramStatus = updateHologramStatus;
window.init3DCardTilt = init3DCardTilt;
window.toggleQrFlipCard = toggleQrFlipCard;

// ═══════════════════════════════════════════
//  INTERACTIVE JUDGE DEMO & CLINICAL CRISIS SIMULATOR
// ═══════════════════════════════════════════
let demoScenariosCache = null;
let activeDemoScenario = null;
let presenterDrawerCollapsed = false;

async function openJudgeDemoModal() {
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById('modal-judge-demo');
  if (!modal) return;
  modal.style.display = 'flex';

  if (demoScenariosCache) {
    renderDemoScenariosGrid(demoScenariosCache);
    return;
  }

  try {
    const res = await fetch('/api/demo/scenarios');
    if (!res.ok) throw new Error('Failed to load scenarios');
    const data = await res.json();
    demoScenariosCache = data.scenarios || [];
    renderDemoScenariosGrid(demoScenariosCache);
  } catch (err) {
    console.error('Demo scenarios loading error:', err);
    const grid = document.getElementById('judge-demo-grid');
    if (grid) {
      grid.innerHTML = `<div class="p-6 text-center text-rose-400 col-span-2">Failed to load demo scenarios. Ensure backend is running.</div>`;
    }
  }
}

function closeJudgeDemoModal() {
  const modal = document.getElementById('modal-judge-demo');
  if (modal) modal.style.display = 'none';
  if (lastFocusedElement) {
    try { lastFocusedElement.focus(); } catch (_) {}
  }
}

function renderDemoScenariosGrid(scenarios) {
  const grid = document.getElementById('judge-demo-grid');
  if (!grid) return;
  grid.innerHTML = '';

  scenarios.forEach((s, idx) => {
    const card = document.createElement('div');
    card.className = 'bg-slate-900/90 border border-slate-800 hover:border-amber-500/50 rounded-xl p-4 flex flex-col justify-between transition group shadow-md hover:shadow-[0_4px_20px_rgba(245,158,11,0.15)]';
    
    let badgeBg = 'bg-rose-950/80 text-rose-300 border-rose-500/40';
    if (s.badge_color === 'orange') badgeBg = 'bg-amber-950/80 text-amber-300 border-amber-500/40';

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-lg">
            ${s.icon || '⚠️'}
          </span>
          <span class="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded border ${badgeBg}">
            ${escapeHtml(s.badge)}
          </span>
        </div>
        <div class="flex items-baseline space-x-2">
          <span class="text-xs font-mono text-amber-400 font-bold">Case #${idx + 1}</span>
          <h3 class="text-sm font-bold text-white font-heading group-hover:text-amber-300 transition">${escapeHtml(s.title)}</h3>
        </div>
        <p class="text-[11px] text-slate-400 font-mono mt-0.5">${escapeHtml(s.subtitle)}</p>
        <div class="mt-2.5 p-2 rounded bg-slate-950/80 border border-slate-800/80 text-[11px] text-slate-300 leading-relaxed font-sans">
          <strong class="text-amber-300 font-mono">Prescribed:</strong> <span class="text-white font-semibold">${escapeHtml(s.proposed_medication)} (${escapeHtml(s.dosage)})</span> for ${escapeHtml(s.patient_name)}
        </div>
        <p class="text-[10.5px] text-slate-400 mt-2 leading-relaxed">
          ${escapeHtml(s.hazard_summary)}
        </p>
      </div>

      <div class="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
        <span class="text-[10px] font-mono text-slate-500">Hotkey: <kbd class="px-1.5 py-0.5 rounded bg-black/40 border border-slate-700 text-slate-300 font-bold">${idx + 1}</kbd></span>
        <button type="button" onclick="executeDemoScenario('${escapeHtml(s.id)}')" class="px-3.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/50 text-xs font-bold transition flex items-center space-x-1.5 cursor-pointer shadow-sm">
          <span>▶ 1-Click Run &amp; Present</span>
          <i class="fa-solid fa-arrow-right text-[10px]"></i>
        </button>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function executeDemoScenario(scenarioId) {
  closeJudgeDemoModal();
  showToast('⚡ Running Live Simulation', `Executing sovereign safety pipeline for ${scenarioId}...`, 'info', 2500);

  // Switch to Tab 1 (Clinical Review)
  switchMainTab('review');

  try {
    const res = await fetch(`/api/demo/run/${scenarioId}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Demo run failed with status ${res.status}`);
    const data = await res.json();
    activeDemoScenario = data;

    // 1. Update form inputs to match scenario
    const medInput = document.getElementById("proposed-med-input");
    const doseInput = document.getElementById("proposed-dose-input");
    if (medInput) medInput.value = data.scenario.proposed_medication;
    if (doseInput) doseInput.value = data.scenario.dosage;

    // 2. Select patient if available
    if (data.scenario.patient_id) {
      currentPatientId = data.scenario.patient_id;
      const select = document.getElementById("patient-select");
      const selectHeader = document.getElementById("patient-select-header");
      if (select) select.value = data.scenario.patient_id;
      if (selectHeader) selectHeader.value = data.scenario.patient_id;
      
      // Update patient display details
      const nameEl = document.getElementById("display-patient-name");
      const metaEl = document.getElementById("display-patient-meta");
      const tokenEl = document.getElementById("display-patient-token");
      if (nameEl) nameEl.textContent = data.scenario.patient_name;
      if (metaEl) metaEl.textContent = `ID: ${data.scenario.patient_id} · Age: ${data.scenario.demographics?.age || 65}y · ${data.scenario.demographics?.gender || 'Unknown'}`;
      if (tokenEl) tokenEl.textContent = `ANON_${data.scenario.patient_id}`;
    }

    // 3. Render review results
    if (typeof renderReviewResults === 'function') {
      renderReviewResults(data.review);
    }

    // 4. Update and display Floating Live Presenter Cheatsheet
    const widget = document.getElementById('presenter-floating-widget');
    const titleEl = document.getElementById('presenter-active-title');
    const bulletsEl = document.getElementById('presenter-bullets');

    if (titleEl) {
      titleEl.innerHTML = `<span class="text-amber-400 font-mono mr-1">${data.scenario.icon || '⚡'}</span> ${escapeHtml(data.presenter_cheatsheet.title)}: <span class="text-slate-300 font-normal text-xs">${escapeHtml(data.scenario.subtitle)}</span>`;
    }

    if (bulletsEl) {
      bulletsEl.innerHTML = '';
      (data.presenter_cheatsheet.talking_points || []).forEach(pt => {
        const li = document.createElement('li');
        li.className = 'leading-snug';
        li.innerHTML = escapeHtml(pt);
        bulletsEl.appendChild(li);
      });
    }

    if (widget) {
      widget.style.display = 'block';
      const drawer = document.getElementById('presenter-drawer-content');
      if (drawer) drawer.style.display = 'block';
      presenterDrawerCollapsed = false;
      const chevron = document.getElementById('presenter-chevron');
      if (chevron) chevron.className = 'fa-solid fa-chevron-down';
    }

    // 5. Scroll smoothly to review card
    const reviewCard = document.getElementById('review-results-card') || document.getElementById('result-content');
    if (reviewCard) {
      reviewCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    showToast('Simulation Complete', `Case: ${data.scenario.title} evaluated with 0 bytes cloud egress.`, 'success', 3500);

  } catch (err) {
    console.error('Error executing demo scenario:', err);
    showToast('Simulation Error', err.message, 'error', 4000);
  }
}

function togglePresenterDrawer() {
  const drawer = document.getElementById('presenter-drawer-content');
  const chevron = document.getElementById('presenter-chevron');
  if (!drawer) return;
  presenterDrawerCollapsed = !presenterDrawerCollapsed;
  drawer.style.display = presenterDrawerCollapsed ? 'none' : 'block';
  if (chevron) {
    chevron.className = presenterDrawerCollapsed ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down';
  }
}

function dismissPresenterWidget() {
  const widget = document.getElementById('presenter-floating-widget');
  if (widget) widget.style.display = 'none';
}

// Window Exports for Judge Demo Simulator
window.openJudgeDemoModal = openJudgeDemoModal;
window.closeJudgeDemoModal = closeJudgeDemoModal;
window.executeDemoScenario = executeDemoScenario;
window.togglePresenterDrawer = togglePresenterDrawer;
window.dismissPresenterWidget = dismissPresenterWidget;


