AGENTS.md — MediVault Local (ASYNC'26, Track 1: Sovereign AI)

Standing context for any AI agent working in this workspace, whichever team member is driving. Read this fully before touching any file. If a human's one-off request conflicts with the folder-ownership or git rules below, flag the conflict rather than silently overriding them.

1. Project overview

MediVault Local — a zero-cloud, HIPAA/DPDP-compliant clinical record reviewer that cross-checks patient diagnostic history against drug-interaction contraindications, running entirely offline on a local machine. No patient data ever leaves the device. Why it matters: hospitals can't legally send patient records to cloud LLMs. Doctors juggling multiple prescriptions miss dangerous interactions (e.g. NSAIDs for a CKD patient) due to manual fatigue. Judging weights: Technical Execution 30%, Innovation 20%, Impact 20%, Product Experience 15%, Demo & Completeness 15%. Team: 4 people, beginner level, using AI coding agents. 30–60 min/day, 22–28 Sept; buffer day 29 Sept; 24-hour final build 30 Sept–1 Oct.

2. Pipeline and folder ownership
[File upload] -> [PII redaction] -> [Interaction DB check] -> [Local LLM reasoning] -> [Flag + report]
     Data            Data             Knowledge/Memory          Reasoning              Action
Stage	Owner	Folder	Others touch it?
Data ingestion + PII redaction	Person B	/ingestion	No — call the function, never edit
Knowledge DB + LLM reasoning	Person C	/ai_engine	No — call the function, never edit
API + backend integration + repo	Person A (Repo Lead)	/backend	No
UI + docs/demo/QA	Person D	/frontend, /docs	No

Golden rule for every agent, regardless of who's driving: only edit inside your own person's folder. If a task seems to require a change in someone else's folder, stop and say so — don't just make the edit. Shared root files (CONTRACTS.md, README.md) are edited only by group agreement.

3. The frozen contract — do not deviate without group agreement

Lives at CONTRACTS.md, root of repo. This is the interface that lets all four people build in parallel without constant coordination.

Ingestion (Person B):
  in:  a file (PDF or .txt)
  out: a single redacted plain-text string
  e.g. "Patient: John Doe, Phone: 9876543210" -> "Patient: [REDACTED], Phone: [REDACTED]"

AI Engine (Person C):
  in:  a redacted string
  out: { "flagged": bool, "reason": str, "drug": str|null }

Backend API (Person A):
  POST /upload-record  in: multipart file      out: { "redacted_text": str }
  POST /analyze         in: { "redacted_text": str }  out: AI Engine output above

Frontend (Person D):
  calls both endpoints in sequence, renders the final flag as a badge

Never change a field name or shape unilaterally. If a change seems necessary, get the human to confirm the team agreed, first.

4. Tech stack & conventions (all folders)
Python 3.10+ backend/AI code; plain HTML/CSS/JS frontend. Git + GitHub for version control.
PEP 8, type-hinted function signatures, docstrings on anything non-trivial.
Every function that touches external input (files, API bodies, LLM responses) validates and fails with a clear message — never a raw stack trace or silent crash.
No real patient data, ever, anywhere — synthetic sample records only, even in tests/fixtures.
Keep each folder's own requirements.txt (or equivalent) current when a new dependency is added, with a one-line reason in the commit message.
5. Git workflow — applies to every folder
Branch naming: feature/<folder>-<short-description>, e.g. feature/ingestion-pdf-extract, feature/frontend-upload-form.
One branch per task, alive 1–2 days max. Pull main before starting each session to catch drift early — this is the single biggest cause of painful conflicts on small teams.
Small, frequent commits with real messages (add PII regex for phone numbers, not stuff).
Push + open a PR when a day's task is done, even if the module isn't fully finished.
Person A is Repo Lead: merges every PR. Instant-merge if a PR only touches its author's own folder. If it touches a shared file (CONTRACTS.md, README.md, /backend/db schema), stop and get a short human sync between the two authors before resolving — never silently pick a side.
6. Per-person contracts and immediate scope

Person A — Repo Lead + Backend (/backend): owns main.py's two endpoints, glue code calling into B's and C's functions, error handling, the repo itself, and merging/conflict resolution. Never writes redaction or LLM logic. Person B — Data & Ingestion (/ingestion): owns extract_text() (PyMuPDF for PDFs, plain read for .txt) and redact_pii() (regex for name, phone, ID number in week 1; email/DOB are stretch). Chains into one function Person A imports. Person C — AI Engine (/ai_engine): owns the SQLite table of ~10 hardcoded drug interactions, a deterministic check_interactions() keyword match, and analyze() which only calls the local Ollama model (llama3.2:3b) to explain/confirm a match the deterministic layer already found — the LLM never introduces a flag on its own. This override design is the strongest technical-execution talking point in the whole project. Person D — Frontend, Docs & QA (/frontend, /docs): owns the 3-screen UI (upload → loading → result badge), README.md, the demo script, and end-to-end manual testing after every merge to main.

7. Week-1 build order (22–28 Sept) — each day builds on the last
Day 1: Repo + folder structure created. CONTRACTS.md written together (B picks PII fields + writes examples; C picks the 10 interactions + output shape; A drafts the API shape; D sketches 3 screens + starts README). Everyone does one trivial practice PR.
Day 2: A builds the backend skeleton returning hardcoded fake data matching the contract. B builds extract_text(). C gets Ollama installed and confirms a basic prompt/response round-trip. D builds a static upload form against A's fake backend.
Day 3 (🔗 team sync): A wires real calls into B/C where ready. B adds redact_pii(). C builds the SQLite interaction table + deterministic keyword check (no LLM yet). D chains the two API calls with a loading state. Sync to confirm the contract still matches reality.
Day 4: A adds error handling for bad input. B handles edge cases (empty/unsupported files). C wires Ollama on top of the deterministic check (heaviest day for C — budget extra time). D builds the real warning-badge UI against hardcoded sample data.
Day 5: A finishes full integration (no fake data left). B polishes redaction, optionally adds email/DOB patterns. C tests analyze() against B's real output across 4–5 samples, tunes the prompt. D points the frontend at the real /analyze endpoint.
Day 6 (🔗 team sync): everyone runs the full live flow 3+ times with different records. Every bug becomes a GitHub Issue tagged by folder — D triages/tags them — nothing gets fixed silently.
Day 7: everyone fixes only their tagged bugs — no new features. A tags v1.0 once stable and verifies a fresh clone runs cleanly. D finishes the README and drafts the demo script.
29 Sept (buffer): no fixed tasks — fix anything shaky, rehearse the pitch, rest.
8. Hackathon day (30 Sept–1 Oct, 24 hrs)
Hrs 0–1: everyone re-confirms their piece runs on the competition machine/network (Ollama and PyMuPDF setups are the most likely to break silently on a new machine — check early).
Hrs 1–6 (pick 1–2 stretch goals, not all): ChromaDB semantic retrieval (C) · SHA-256 stamp + FastMCP PDF export (A+C) · OCR for handwritten notes (B) · richer demo styling / multi-sample click-through (D).
Hrs 6–8 (🔗 sync): full live run together, log new bugs, don't fix silently.
Hrs 8–14: fix bugs + take an actual rest block — don't push straight through 24 hours with a beginner team.
Hrs 14–18: second polish pass, or cut a shaky stretch feature rather than ship it broken.
Hrs 18–20: freeze main. No commits after this except a critical fix verified end-to-end first.
Hrs 20–22: timed rehearsal, twice. Each person speaks to their own piece: A = architecture/API + the deterministic-override design, B = the privacy/redaction angle, C = the AI reasoning + safety layer, D = drives the live clicking and owns the UX.
Hrs 22–24: submit with buffer time before the deadline.
9. Hard guardrails — for every agent, regardless of who's driving
Never edit inside another person's folder without a human confirming it's been discussed with that person.
Never change /upload-record or /analyze response shapes without confirmed group agreement.
Never commit directly to main — always branch, always PR.
Never fabricate or use real patient data, including in tests.
Never silently resolve a conflict in CONTRACTS.md, README.md, or a shared DB schema — flag it for a human sync first.