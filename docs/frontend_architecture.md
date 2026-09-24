# MediVault Local — Frontend UI Architecture
> **Owner:** Sujan MB (Person D)  
> **Stack:** Plain HTML5 + Tailwind CSS (CDN) + Vanilla JavaScript + Font Awesome icons  
> **Files:** `/frontend/index.html`, `/frontend/app.js`

---

## Overview

The MediVault Local doctor dashboard is a single-page application (SPA) served as a static file by the FastAPI backend at `http://127.0.0.1:8000`. It communicates exclusively with the local backend API — zero external network calls.

---

## Screen Architecture (3 Logical Screens)

```
┌─────────────────────────────────────────────────────────────────┐
│                       SCREEN 1: HEADER                          │
│  MediVault Local logo | AI Status Pill | Air-Gap Trust Pill     │
│  HIPAA badge | Doctor Profile Pill (→ opens Auth Modal)         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────────────┐
│  SCREEN 2: LEFT PANEL    │  │  SCREEN 3: RIGHT PANEL           │
│  (5 cols)                │  │  (7 cols)                        │
│                          │  │                                  │
│  ┌──────────────────┐    │  │  ┌────────────────────────────┐  │
│  │ Intake Mode Tabs │    │  │  │  Prescription Input Form   │  │
│  │  • Demo Patients │    │  │  │  Medication + Dosage       │  │
│  │  • Upload / Paste│    │  │  │  Quick Prescribe Chips     │  │
│  └──────────────────┘    │  │  │  [RUN REVIEW Button]       │  │
│                          │  │  └────────────────────────────┘  │
│  ┌──────────────────┐    │  │                                  │
│  │ Patient Card     │    │  │  ┌────────────────────────────┐  │
│  │  • Name / Meta   │    │  │  │  Review Result Card        │  │
│  │  • Conditions    │    │  │  │  🔴 CRITICAL / 🟡 WARNING   │  │
│  │  • Medications   │    │  │  │     / 🟢 SAFE Banner       │  │
│  │  • Allergies     │    │  │  │  Alert Conflict Cards      │  │
│  └──────────────────┘    │  │  │  Audit Hash + Latency      │  │
│                          │  │  └────────────────────────────┘  │
└──────────────────────────┘  └──────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   BOTTOM: AUDIT TRAIL SECTION                   │
│  Collapsible SHA-256 hash-chained log table                     │
│  "Verify Chain Integrity" button → HIPAA § 164.312(b) badge     │
│  Export CSV / JSON controls                                     │
└─────────────────────────────────────────────────────────────────┘

                  ┌──────────────────────────┐
                  │   AUTH MODAL (overlay)   │
                  │  Tabs: Demo | Login | Reg│
                  │  OTP Verification Screen │
                  └──────────────────────────┘
```

---

## API Endpoints Consumed by the Frontend

| Endpoint | Method | When Called | What It Does |
|---|---|---|---|
| `/api/patients` | GET | On load | Populates demo patient dropdown |
| `/api/patients/{id}` | GET | On patient select change | Loads patient profile card |
| `/api/upload-record` | POST | On file drop/upload | Sends PDF/TXT, gets redacted text + entities |
| `/api/extract` | POST | On "Run Redaction" click | Extracts entities from pasted text |
| `/api/review` | POST | On "Run Review" click | Core safety check; returns flags + alerts |
| `/api/ai-status` | GET | On load | Checks if Ollama is running |
| `/api/audit-logs` | GET | After each review | Refreshes the audit trail table |
| `/api/audit-verify` | GET | On "Verify Chain" click | Validates SHA-256 chain integrity |
| `/api/auth/me` | GET | On load | Loads current doctor session |
| `/api/auth/hospitals` | GET | On load | Populates hospital dropdown in Register tab |
| `/api/auth/practitioners` | GET | On load | Populates demo doctor list |
| `/api/auth/switch-demo` | POST | On "Switch" doctor click | Hot-swaps active reviewer context |
| `/api/auth/login` | POST | On Sign In submit | Authenticates physician |
| `/api/auth/register` | POST | On Register submit | Creates new physician account |
| `/api/auth/verify-email` | POST | On OTP submit | Verifies 6-digit institutional code |
| `/api/auth/resend-code` | POST | On "Resend Code" click | Issues a new OTP |

---

## Key JavaScript Functions (`app.js`)

| Function | Purpose |
|---|---|
| `loadPatientProfile(id)` | Fetches and renders the patient card for a demo patient |
| `renderPatientCard(...)` | Populates conditions, medications, allergies DOM elements |
| `handleFileUpload(file)` | POST to `/api/upload-record`; updates UI on success/error |
| `triggerRedaction()` | POST text to `/api/extract`; updates patient card |
| `runSafetyCheck()` | POST to `/api/review`; dispatches to `renderReviewResults()` |
| `renderReviewResults(data)` | Renders the CRITICAL/WARNING/SAFE banner and alert cards |
| `refreshAuditTrail()` | Fetches and renders the audit log table rows |
| `verifyAuditChain()` | Calls `/api/audit-verify`; shows integrity banner |
| `toggleAuditDrawer()` | Shows/hides the audit table |
| `openAuthModal()` / `closeAuthModal()` | Controls the physician auth overlay |
| `switchAuthTab(tab)` | Switches between Demo/Login/Register tabs |
| `switchDemoDoctor(id)` | POST to `/api/auth/switch-demo`; updates header pill |
| `handleLogin()` | POST credentials to `/api/auth/login` |
| `handleRegister()` | POST new physician to `/api/auth/register` |
| `showOtpScreen(email, code)` | Shows the 6-digit OTP verification screen |
| `handleVerifyOtp()` | POST OTP code to `/api/auth/verify-email` |
| `checkAiStatus()` | Polls `/api/ai-status` and updates the Ollama status pill |

---

## Design Tokens (Tailwind Color Palette)

| Token | Hex / Class | Usage |
|---|---|---|
| Background | `bg-slate-900` | Page background |
| Card Background | `bg-slate-800/90` | All panel cards |
| Primary Accent | `teal-400 / teal-500` | Headers, borders, icons, buttons |
| CRITICAL | `red-400 / red-950` | Danger banners, high-risk conditions |
| WARNING | `amber-400 / amber-950` | Caution banners, allergy tags |
| SAFE | `emerald-400 / emerald-950` | Safe prescription banner |
| Muted Text | `slate-400` | Labels, secondary info |
| Code / Mono | `font-mono` | Hashes, IDs, OTP codes |

---

## Offline / Fallback Behavior

All API calls are wrapped in `try/catch`. On failure:
- Patient profile: silently falls back to default hardcoded values in HTML
- Safety check: shows error state; button re-enables
- Audit trail: `console.warn` only; no crash
- AI status: `console.warn` only; pill stays at last known value

This means the UI **never crashes** even if the backend is temporarily unavailable.
