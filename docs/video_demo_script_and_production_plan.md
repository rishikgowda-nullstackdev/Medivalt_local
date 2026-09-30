# MediVault Local — 4 to 5 Minute Prototype Demonstration Video Script & Editing Plan
> **Track:** ASYNC'26, Track 1: Sovereign AI  
> **Team:** Void_coders (Rishikgowda SM, Rakshith DA, Kushal M, Sujan MB)  
> **Target Video Length:** 4:30 – 5:00 Minutes (~650 Spoken Words @ 135 WPM)  
> **Target Audience:** Hackathon Judges, Clinical Directors, Healthcare Security Officers

---

## 1. Video Production Blueprint & Audio-Visual (AV) Script

### ACT 1: The Cold Open & The Hospital Dilemma (0:00 – 0:45)
*Tone: Urgent, tense, cinematic medical documentary.*  
*Music: Low, pulsing electronic tension drone with faint heartbeat monitor pulse in the background.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **0:00 – 0:12** | **B-Roll:** Fast-paced montage of hospital ICU monitors, tired doctors staring at EHR computer screens at 2 AM, and prescription slips piling up. Quick cut to a red emergency alert flashing. | *"Every day in hospitals worldwide, overworked physicians juggle dozens of patient prescriptions. Clinical cognitive overload is real—and Adverse Drug Events have quietly become a top-five cause of death globally."* | **SFX:** Low bass boom. Faint hospital telemetry beep. |
| **0:12 – 0:28** | **Graphic / Motion Graphic:** A doctor’s hands typing patient notes. An animation shows a patient chart being blocked from uploading to a cloud server with a glowing red padlock and the text: **HIPAA § 164.514 & DPDP ACT 2023 — CLOUD PROHIBITED**. | *"Doctors desperately need AI co-pilots. But hospitals face a fatal legal impasse: transmitting confidential patient health records to cloud LLMs like ChatGPT or AWS is illegal under HIPAA and the DPDP Act. A single data breach brings catastrophic penalties up to ₹250 Crore."* | **Graphic Callout:** Red stamp: *"₹250 Cr / $50k per breach penalty"*. **SFX:** Muted digital error thud. |
| **0:28 – 0:45** | **B-Roll / Motion Graphic:** A split screen showing an AI chatbot hallucinating a dosage on the left, and a doctor shaking their head on the right. Rapid zoom in on the title slide of MediVault Local. | *"And when cloud LLMs are tested, they hallucinate—guessing dosages and overlooking kidney thresholds. A life-critical hospital ward cannot gamble on probabilistic text generation.*<br><br>*We built **MediVault Local**: a 100% sovereign AI clinical reviewer that executes completely on the doctor's workstation, with zero bytes to the cloud, zero hallucinations, and mathematical proof of compliance."* | **SFX:** Glitch transition sound into an uplifting, confident synth intro chord. |

---

### ACT 2: The Real-World Crisis — The "Triple Whammy" (0:45 – 1:30)
*Tone: Empathetic, investigative, relatable to any layman or clinician.*  
*Music: Tense, rhythmic electronic beat kicks in.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **0:45 – 1:05** | **Screen Recording / Visual Graphic:** A sleek anatomical illustration of human kidneys with blood flowing into the nephron. Three prescription bottles drop onto the screen: Lisinopril (Blood pressure), Furosemide (Water pill), and Advil (Painkiller). | *"Consider an 80-year-old grandfather with mild chronic kidney disease. He visits the emergency room with severe back pain. An exhausted resident physician prescribes a standard, familiar painkiller: Advil.*<br><br>*To a human doctor in hour 14 of a night shift, Advil seems harmless. But biologically, it is lethal."* | **On-Screen Text:** Lisinopril + Furosemide + Advil = **The "Triple Whammy"**.<br>**SFX:** Three heavy thuds as bottles drop. |
| **1:05 – 1:20** | **Motion Graphic:** Blood vessels entering the kidney pinch shut in animated red. The filtration pressure dial crashes from green (42 mL/min) into deep red (<15 mL/min). | *"The blood pressure pill dilates the outgoing kidney vessel. The water pill reduces blood volume. And the Advil constricts the incoming vessel. Together, glomerular filtration pressure drops to zero. Within 48 hours, his kidneys shut down completely—requiring emergency ICU dialysis."* | **Graphic Overlay:** eGFR Dial plunging from 42 ➔ 12 mL/min.<br>**SFX:** Electronic warning alarm beep. |
| **1:20 – 1:30** | **Screen Recording:** Cut to doctor desktop running MediVault Local with the green glowing **AIR-GAPPED (127.0.0.1)** status pill visible. | *"This preventable disaster happens in 43% of polypharmacy patients. MediVault Local was engineered to stop this exact disaster in under 40 milliseconds—right at the doctor's desk."* | **Callout:** *"Catches Contraindications in <40ms"*. |

---

### ACT 3: Architecture & The Deterministic Safety Core (1:30 – 2:15)
*Tone: Tech-savvy, rigorous, impressive to technical judges.*  
*Music: Driving, precise electronic tech track.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **1:30 – 1:52** | **Motion Graphic / Screen Recording:** Animated 6-stage pipeline:  
1. Ingestion & RapidOCR  
2. 18 HIPAA Safe Harbor PHI Redaction  
3. Brand-to-Generic Normalization  
4. Deterministic SQLite Engine  
5. Rowland & Tozer PK Model + Ollama SLM  
6. SHA-256 Merkle Ledger. | *"Here is our sovereign architecture. MediVault runs as a 6-stage local pipeline on a strict loopback address—127.0.0.1.*<br><br>*First, on-device RapidOCR and PyMuPDF extract text from scanned paper slips or discharge PDFs. Then, our redaction engine strips all 18 HIPAA Safe Harbor identifiers in RAM, generating an anonymized cryptographic token."* | **Graphic:** Visual glowing pipeline nodes lighting up sequentially.<br>**SFX:** Subtle digital data chirp per stage. |
| **1:52 – 2:15** | **Visual Graphic:** Split diagram showing **Layer 1: Deterministic SQLite Matrix (Anchor)** on bottom, and **Layer 2: Ollama SLM (Synthesizer)** on top. An animated lock icon clamps the safety verdict. | *"Next is our core technical innovation: the **Deterministic-Override Safety Engine**.*<br><br>*Our cardinal rule: Generative AI translates and explains, but deterministic clinical matrices decide and protect.*<br><br>*Safety rules, Cockcroft-Gault kidney calculations, and Beers criteria live in a deterministic SQLite matrix. The local Ollama model (llama3.2:3b) generates natural clinical rationale, but it can NEVER override a rule or invent a clearance flag on its own. If Ollama crashes, our deterministic fallback takes over in 0 milliseconds."* | **On-Screen Formula:** $Verdict = RuleEngine \land SLM$<br>**SFX:** Heavy mechanical latch lock sound. |

---

### ACT 4: Live Prototype Walkthrough — The "Killer Demo" (2:15 – 3:30)
*Tone: Energetic, live, confident, direct software demonstration.*  
*Music: Upbeat, modern electronic pulse.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **2:15 – 2:32** | **Live Screen Recording:** Screen Studio cursor points to the top right of MediVault Local at `http://127.0.0.1:8000`. Zoom in on the pulsing green pill: `AIR-GAPPED: 0 BYTES TRANSMITTED (127.0.0.1)`. Cursor clicks Wi-Fi icon on Windows taskbar and disconnects Wi-Fi. Refreshes the page. | *"Let’s see it live. Watch the top right: 'AIR-GAPPED: 0 BYTES TRANSMITTED'. To prove true sovereignty, we can physically disconnect this computer from Wi-Fi right now. Refresh the page—everything continues running flawlessly on localhost."* | **Visual Callout:** Green ring highlight around Air-Gap badge.<br>**SFX:** Mouse click sound. |
| **2:32 – 2:50** | **Live Screen Recording:** Cursor drags `samples/patient_1_ckd_discharge.pdf` into the upload dropzone. Note auto-ingests. Show the patient card populating: Stage 3 CKD, Lisinopril, Metformin, eGFR: 38. In the prescription box, doctor types: `Advil 400mg PO TID` and clicks **RUN OFFLINE REVIEW**. | *"Now, let's load our CKD patient record. All 18 personal identifiers are instantly scrubbed in RAM.*<br><br>*Now, the doctor types a commercial brand name: Advil. We click 'Run Offline Review'."* | **Visual Zoom:** Smooth 1.3x pan zoom into the prescription input field.<br>**SFX:** Typing sounds, followed by an immediate click. |
| **2:50 – 3:10** | **Live Screen Recording:** In under 40ms, the screen flashes red. Banner appears: 🔴 **CRITICAL CONTRAINDICATION DETECTED**.  
- Subtitle: *Advil normalized to generic Ibuprofen*.  
- PK Accumulation curve shows drug plasma levels crossing the red "Toxic Ceiling" bar at 48h.  
- Formulary swap card appears: *Suggested: Acetaminophen 500mg*. | *"In just 38 milliseconds, MediVault normalizes Advil to generic Ibuprofen, detects the Stage 3 CKD contraindication, and triggers a critical warning.*<br><br>*Notice our Rowland & Tozer dynamic pharmacokinetic model: it simulates 72 hours of drug accumulation, proving the patient's damaged kidneys will fail to clear the drug, crossing the toxic ceiling into nephrotoxicity."* | **Visual Highlight:** Red glowing border on alert card.<br>**SFX:** Sharp chime of urgency. |
| **3:10 – 3:20** | **Live Screen Recording:** Cursor clicks **"1-Click Swap: Acetaminophen"**. Re-evaluates instantly. Banner turns glowing emerald green: 🟢 **PRESCRIPTION CLEARED (SAFE)**. | *"With one click, the doctor swaps to a safe alternative: Acetaminophen. The system re-evaluates: prescription cleared. Kidney perfusion remains 100% protected."* | **Visual Callout:** Green checkmark badge.<br>**SFX:** Crisp success chime. |
| **3:20 – 3:30** | **Live Screen Recording:** Scroll down to the **Local Cryptographic Audit Trail**. Click **"Verify Hash Chain"**. Green text flashes: `CRYPTOGRAPHIC PROOF: All 102 blocks verified intact (Zero Tampering Detected)`. Click **"Optical QR Transfer"** to reveal dynamic SVG QR code. | *"Finally, every decision is sealed in an on-device SHA-256 Merkle blockchain. Click 'Verify Chain'—we have mathematical proof of zero tampering fulfilling HIPAA § 164.312(b). And records transfer across wards wire-free via compressed optical SVG QR codes."* | **Visual Highlight:** Green Merkle block tree animation.<br>**SFX:** Camera shutter sound. |

---

### ACT 5: Engineering Rigor & Judging Alignment (3:30 – 4:15)
*Tone: Authoritative, impressive, data-backed.*  
*Music: Triumphant, high-energy tech synth.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **3:30 – 3:55** | **Screen Recording:** Cut to VS Code / Terminal. Run automated test suite: `python -m unittest discover -s tests -p "*.py"`. Show 117 tests passing across 17 test modules with `OK`. | *"We engineered MediVault Local with enterprise clinical rigor. 117 automated unit and integration tests verify every layer—from 18 Safe Harbor regex strippers to Beers elderly criteria and Cockcroft-Gault formulas.*<br><br>*We stress-tested multi-threaded ward entries: SQLite Write-Ahead Logging (WAL) handled concurrent reviews with zero database locks."* | **On-Screen Banner:** `117 / 117 Tests Passing across 17 modules`.<br>**SFX:** Fast terminal scrolling sound into success chime. |
| **3:55 – 4:15** | **Motion Graphic:** Five cards highlighting the ASYNC'26 judging weights:  
- Technical Execution (30%)  
- Innovation (20%)  
- Impact (20%)  
- Product Experience (15%)  
- Completeness (15%). | *"Against the ASYNC'26 judging criteria, MediVault delivers maximum execution:*<br><br>*- **30% Technical Execution:** 117 tests and zero-cloud network assertions.*<br>*- **20% Innovation:** Deterministic SLM override, Merkle ledger, and optical air gaps.*<br>*- **20% Impact:** Eliminates fatal ADEs in polypharmacy patients.*<br>*- **15% Product Experience:** 40ms doctor workflow, keyboard hotkeys, and patient portal.*<br>*- **15% Completeness:** 1-click launcher and pre-configured judge crisis scenarios."* | **Visual Elements:** Five judging icons light up with gold borders.<br>**SFX:** Upbeat progressive pings. |

---

### ACT 6: Real-World Impact, Roadmap & The Finale (4:15 – 5:00)
*Tone: Visionary, inspiring, memorable.*  
*Music: Grand, uplifting crescendo.*

| Timecode | Visual / On-Screen Action (Screen Recording & B-Roll) | Voiceover Script (Exact Words to Speak) | Sound Effects & Graphics |
|---|---|---|---|
| **4:15 – 4:40** | **B-Roll / Concept Visuals:** A rural clinic in a remote region with no internet. A military field triage tent with a rugged laptop running MediVault Local. Cut to team photo / names of Void_coders. | *"Where does this change the world? In rural community clinics where broadband is unavailable. In military field hospitals cut off from satellite uplinks. And in tertiary hospitals that simply refuse to surrender patient privacy to Big Tech cloud monopolies.*<br><br>*Our post-hackathon roadmap includes direct on-premise EHR connectors for Epic and Cerner, and pharmacogenomics integration for CYP2D6 metabolizers."* | **Graphic Overlay:** Roster card showing Person A, B, C, D roles.<br>**SFX:** Warm, atmospheric hospital soundscape. |
| **4:40 – 5:00** | **Cinematic Title Card:** Clean, glowing MediVault Local logo with the official tagline centered on screen. Fast cut to GitHub repository URL and team sign-off. | *"Sovereign AI isn’t just about keeping secrets from the cloud—it’s about saving human lives when the world goes offline.*<br><br>***MediVault Local: No Cloud. No Hallucinations. No Data Leaks.***<br><br>*We are Team Void_coders. Thank you."* | **On-Screen Final Card:**  
**MediVault Local**  
*No Cloud. No Hallucinations. No Data Leaks.*  
Track 1: Sovereign AI • ASYNC'26  
**Music:** Final powerful synth resolve & fade out. |

---

## 2. Complete Video Editing & Production Plan

### A. Pre-Production Checklist (Recording Setup)

| Parameter | Recommended Setting | Purpose |
|---|---|---|
| **Screen Recorder** | **Screen Studio** (macOS) or **OBS Studio** (Windows) | Screen Studio provides automatic smooth cursor motion and dynamic auto-zoom on clicks. If using OBS, record in 1080p60 @ 12,000 kbps. |
| **Resolution & Canvas** | 1920x1080 @ 60 FPS (16:9 Widescreen) | Sharp, crisp text that remains legible even on mobile screens or projector displays. |
| **Browser Configuration** | Google Chrome or Microsoft Edge @ **125% DPI Zoom** | Slightly larger text ensures judges can read drug names, dosages, and eGFR numbers clearly without squinting. |
| **Desktop Environment** | Hide desktop icons, close taskbar apps, clean wallpaper | Professional, sterile presentation environment. |
| **Microphone & Voiceover** | USB Condenser (Blue Yeti / Rode / Shure) or high-quality lapel | Voice should be recorded in a quiet room with minimal reverb. Use a gentle 80Hz high-pass filter, mild compression, and -14 LUFS loudness. |

---

### B. Screen Recording Shot List (Exact Actions to Capture)

1. **Shot 1 (Air-Gap Disconnect):**
   - Start recording with browser on `http://127.0.0.1:8000`.
   - Hover cursor over the pulsing green **"AIR-GAPPED: 0 BYTES TRANSMITTED"** badge for 3 seconds.
   - Click Windows Wi-Fi menu and click "Disconnect".
   - Press <kbd>F5</kbd> / Refresh browser. Show that the page reloads instantly from localhost with zero errors.
2. **Shot 2 (Drag-and-Drop Ingestion):**
   - Have `samples/patient_1_ckd_discharge.pdf` open in File Explorer alongside the browser.
   - Drag the PDF smoothly into the upload dropzone.
   - Watch the status badge flash *"PHI Redacted: 18 elements removed"* and patient card auto-populate.
3. **Shot 3 (Advil Contraindication Cascade):**
   - Click into the Prescription input well.
   - Type: `Advil 400mg PO TID`.
   - Click the blue button: **"RUN OFFLINE REVIEW"**.
   - Show the instant transition (<40ms) to the 🔴 **CRITICAL ALERT** banner.
   - Slowly scroll down to show the Rowland & Tozer dynamic PK accumulation graph crossing the red toxic ceiling.
4. **Shot 4 (1-Click Safe Formulary Swap):**
   - Move cursor to the green box: **"💡 Safe Alternative: Acetaminophen 500mg"**.
   - Click **"1-Click Swap"**.
   - Screen updates immediately to 🟢 **PRESCRIPTION CLEARED (SAFE)** with healthy renal perfusion metrics.
5. **Shot 5 (Merkle Audit Drawer & Optical QR):**
   - Click on the **"Local Cryptographic Audit Trail"** drawer to expand it.
   - Click the button: **"Verify Hash Chain"**.
   - Capture the green verified confirmation: `All 102 blocks verified intact`.
   - Click **"Optical QR Transfer"** to show the dynamic high-density SVG QR code pulsing on screen.
6. **Shot 6 (Terminal Test Run):**
   - Open PowerShell in the project root.
   - Type and run: `python -m unittest discover -s tests -p "*.py"`.
   - Capture the terminal output running all 117 tests and printing `OK`.

---

### C. Motion Graphics & Visual Elements to Create / Insert

1. **Lower Thirds (Speaker Identification):**
   - Clean slate-blue lower-third bars with neon emerald accent lines:
     - *Rishikgowda SM — Repo Lead & Backend Architecture*
     - *Rakshith DA — Ingestion Engine & PHI Redaction*
     - *Kushal M — Pharmacology Engine & SLM Reasoning*
     - *Sujan MB — Frontend Workstation & QA Lead*
2. **Nephron Glomerular Hemodynamics Diagram:**
   - Visual animation overlay during Beat 2: showing the afferent arteriole (Advil vasoconstriction) and efferent arteriole (Lisinopril vasodilation) causing glomerular filtration pressure to collapse.
3. **Zoom & Pan Highlights:**
   - Use 1.25x to 1.35x smooth digital push-in zooms whenever typing drug names or highlighting the 38ms latency counter.
4. **Key Metric Callout Cards:**
   - Pop-up badge at 0:25: `₹250 Crore Regulatory Fine (DPDP Act)`.
   - Pop-up badge at 2:55: `38ms Local Evaluation Latency`.
   - Pop-up badge at 3:35: `117 / 117 Automated Tests Passing`.

---

### D. Audio & Sound Design Blueprint

| Track / Sound Type | Source / Style | Usage & Timing |
|---|---|---|
| **Background Music 1 (Intro/Problem)** | Tense, low cinematic synth drone (e.g. *Hans Zimmer / Tenet* style) | Starts at 0:00, sets dramatic urgency, builds tension through 1:30. |
| **Background Music 2 (Tech/Demo)** | Rhythmic, driving modern electronic tech beat (e.g. *Apple product reveal / cyberpunk lo-fi tech*) | Drops at 1:30 when architecture and demo start. Keeps energy high through 4:15. |
| **Background Music 3 (Finale)** | Uplifting, triumphant melodic synth with warm sub-bass | Plays from 4:15 to 5:00 for the visionary closing impact statement. |
| **SFX: Digital Glitch / Swoosh** | High-frequency digital riser or cyber whoosh | Used during slide/scene transitions. |
| **SFX: Heavy Latch / Lock** | Solid mechanical vault latch sound | Fires at 2:05 when the Deterministic Rule Gate clamps over the SLM. |
| **SFX: Warning Chime** | Medical monitor alert chime (urgent double-beep) | Fires at 2:52 when Advil triggers the 🔴 Critical Contraindication. |
| **SFX: Success Ping** | Soft, satisfying high-register glass chime | Fires at 3:12 when Acetaminophen clears as 🟢 Safe. |
| **SFX: Camera Shutter** | Crisp mechanical camera shutter click | Fires at 3:28 when the Optical QR code appears. |

---

### E. Editing Workflow & Post-Production Steps (Premiere Pro / DaVinci / CapCut)

1. **Step 1 — Voiceover Track Assembly (Timeline Track A1):**
   - Record the voiceover in one sitting for vocal consistency.
   - Edit out pauses, breaths, and retakes. Ensure the timeline duration sits between **4:30 and 4:50**.
2. **Step 2 — A-Roll / Screen Recording Sync (Timeline Track V1):**
   - Align screen capture clips to the narration cues.
   - Use speed ramping (1.2x – 1.5x) on mouse movements and file dragging so there is zero dead air or hesitation.
3. **Step 3 — Dynamic Zooms & Framing (Timeline Track V2):**
   - Apply keyframed scale (100% ➔ 130%) on critical UI moments (the Air-Gap badge, the Advil warning banner, and the Merkle verification).
4. **Step 4 — Graphic Overlays & Callouts (Timeline Track V3):**
   - Add the lower-third titles, statutory penalty stamps, and animated 6-stage pipeline graphic.
5. **Step 5 — Sound Effects & Music Mixing (Tracks A2, A3, A4):**
   - Duck background music by -14 dB whenever the voiceover is speaking (auto-ducking).
   - Place SFX precisely on cursor clicks and banner pop-ups.
6. **Step 6 — Color Grading & Export:**
   - Apply a subtle "Teal & Dark Slate" clinical LUT to boost contrast and make the emerald and crimson status banners pop.
   - Export settings: **H.264 / MP4, 1920x1080, 60fps, VBR 2-pass (Target: 16 Mbps, Max: 24 Mbps), AAC Audio 320 kbps**.
