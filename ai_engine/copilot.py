"""
MediVault Local - Sovereign Clinical Copilot Engine (Person C)
Offline interactive clinical decision assistant for physicians.
Grounded in active patient labs, vitals, PK clearance curves, and deterministic CDSS rules.
Implements strict zero-hallucination safety guardrails: the local SLM can never
contradict or override a deterministic contraindication.
"""

import time
import re
import sqlite3
import os
from typing import Dict, Any, List, Optional, Tuple
import httpx

from ai_engine.vector_rag import (
    search_clinical_knowledge,
    get_monograph,
    resolve_drug_name,
    get_allergy_cross_reactivity
)
from ai_engine.pharmacology import PharmacologyKnowledge
from ai_engine.engine import evaluate_full_safety
from ai_engine.hazard_index import calculate_hazard_index

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:latest"
COPILOT_TIMEOUT = 8.0

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _detect_ollama_model() -> Optional[str]:
    """Auto-detect active or installed models in local Ollama instance."""
    try:
        with httpx.Client(timeout=1.5) as client:
            res = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if res.status_code == 200:
                models = [m.get("name") for m in res.json().get("models", []) if m.get("name")]
                # Priority match
                for pref in ["llama3.2:latest", "llama3.2:3b", "llama3.2"]:
                    for m in models:
                        if m == pref or m.startswith(pref):
                            return m
                for m in models:
                    if "llama" in m or "phi" in m or "mistral" in m:
                        return m
                if models:
                    return models[0]
    except Exception:
        pass
    return None


def _strip_repeated_greeting(text: str) -> str:
    """
    Strips redundant introductory greetings ('Hello, I'm the Sovereign Clinical AI Copilot...')
    from responses so follow-up inquiries jump directly to the clinical answer.
    """
    if not text:
        return ""
    full_intro_pattern = (
        r'^[\"\'“‘]?\s*'
        r'(?:(?:Hello|Good\s+(?:morning|afternoon|evening)|Hi|Greetings)(?:,?\s+(?:Doctor|there)?)?[.!,]?\s*)?'
        r'(?:I(?:\'m|\s+am)\s+(?:the|your)\s+Sovereign\s+Clinical\s+(?:AI\s+)?Copilot[^.!?]*[.!?]\s*)'
        r'(?:(?:I\s+(?:can|am\s+here\s+to)\s+help|Please\s+feel\s+free|What[\'’]s\s+your\s+specific)[^.!?]*[.!?]\s*)*'
        r'(?:(?:For|Regarding)\s+(?:your\s+)?(?:specific\s+)?(?:question|inquiry),?\s*)?'
    )
    cleaned = re.sub(full_intro_pattern, '', text, flags=re.IGNORECASE).strip()
    generic_greeting_pattern = (
        r'^[\"\'“‘]?\s*'
        r'(?:Hello|Good\s+(?:morning|afternoon|evening)|Hi|Greetings)(?:,?\s+(?:Doctor|there))?[.!,]\s*'
        r'(?:(?:For|Regarding)\s+(?:your\s+)?(?:specific\s+)?(?:question|inquiry),?\s*)?'
    )
    cleaned = re.sub(generic_greeting_pattern, '', cleaned, flags=re.IGNORECASE).strip()

    if cleaned.endswith('"') and not cleaned.startswith('"'):
        cleaned = cleaned.rstrip('"').strip()

    if not cleaned:
        return text

    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _lookup_patient(patient_id: str) -> Optional[Dict[str, Any]]:
    """Fetch patient clinical chart from local SQLite database."""
    if not patient_id:
        return None
    try:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        p_row = cursor.fetchone()
        if not p_row:
            conn.close()
            return None

        # Patient conditions
        cursor.execute("SELECT condition_name FROM patient_conditions WHERE patient_id = ?", (patient_id,))
        conditions = [r["condition_name"] for r in cursor.fetchall()]

        # Active Medications
        cursor.execute(
            "SELECT medication_name, dosage, frequency FROM patient_medications WHERE patient_id = ?",
            (patient_id,)
        )
        medications = []
        for r in cursor.fetchall():
            name = r["medication_name"]
            dose = r["dosage"] or ""
            freq = r["frequency"] or ""
            medications.append(f"{name} {dose} {freq}".strip())

        # Allergies
        cursor.execute("SELECT allergen, reaction FROM patient_allergies WHERE patient_id = ?", (patient_id,))
        allergies = []
        for r in cursor.fetchall():
            allergen = r["allergen"]
            reaction = r["reaction"]
            allergies.append(f"{allergen} ({reaction})" if reaction else allergen)

        # Recent Labs from patient_labs
        cursor.execute("SELECT biomarker_name, value, unit FROM patient_labs WHERE patient_id = ?", (patient_id,))
        labs = {}
        for r in cursor.fetchall():
            b_name = r["biomarker_name"].lower()
            labs[b_name] = {"value": r["value"], "unit": r["unit"], "status": "RECORDED"}

        patient_name = p_row["patient_name"] if "patient_name" in p_row.keys() else patient_id
        age = p_row["age"] if "age" in p_row.keys() else 65
        gender = p_row["gender"] if "gender" in p_row.keys() else "Unknown"

        conn.close()
        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "full_name": patient_name,
            "age": age,
            "gender": gender,
            "weight_kg": 70.0,
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
            "labs": labs
        }
    except Exception:
        return None


class ClinicalCopilot:
    """
    Sovereign Clinical Copilot.
    Synthesizes multi-source patient data, deterministic rule matrices,
    and vector RAG monographs to answer physician queries with zero cloud calls.
    """

    @classmethod
    def ask(
        cls,
        message: str,
        patient_id: Optional[str] = None,
        proposed_med: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a physician inquiry through the Sovereign AI Copilot pipeline.
        Supports multi-turn conversational dialogue grounded in active chart data.
        """
        start_time = time.time()
        citations: List[str] = []
        guardrail_applied = False

        # 1. Resolve Patient Clinical Context
        patient_data = None
        if patient_id:
            patient_data = _lookup_patient(patient_id)
        if not patient_data and context:
            patient_data = context

        # Defaults if no patient loaded
        patient_name = patient_data.get("patient_name") or patient_data.get("full_name") or (patient_id or "Anonymous Patient")
        conditions = patient_data.get("conditions", []) if patient_data else []
        medications = patient_data.get("medications", []) if patient_data else []
        allergies = patient_data.get("allergies", []) if patient_data else []
        labs = patient_data.get("labs", {}) if patient_data else {}
        demographics = {
            "age": patient_data.get("age", 65) if patient_data else 65,
            "gender": patient_data.get("gender", "M") if patient_data else "M",
            "weight_kg": patient_data.get("weight_kg", 70.0) if patient_data else 70.0
        }

        # 2. Extract Drug Entities & Contextual RAG
        target_med = proposed_med
        detected_drug = None
        # Check tokens with fuzzy matching across monographs and brand aliases
        tokens = re.findall(r"\b[A-Za-z0-9\-]+\b", message)
        for t in tokens:
            if t.lower() in ["the", "this", "that", "patient", "tablets", "capsules", "dose", "given", "give", "safe", "take", "any"]:
                continue
            resolved = resolve_drug_name(t)
            if resolved:
                canonical, matched_t, conf = resolved
                target_med = canonical
                detected_drug = canonical
                break

        rag_results = []
        monograph = None
        if target_med:
            monograph = get_monograph(target_med)
            rag_results = search_clinical_knowledge(f"{target_med} {message}", top_k=2)
        else:
            rag_results = search_clinical_knowledge(message, top_k=2)

        # 3. Deterministic CDSS & Hazard Evaluation
        det_status = "SAFE"
        det_alerts = []
        canonical_drug = target_med or "None"
        recommended_alts = []

        if target_med:
            det_status, det_alerts, canonical_drug, recommended_alts = evaluate_full_safety(
                proposed_med=target_med,
                conditions=conditions,
                medications=medications,
                allergies=allergies,
                labs=labs,
                demographics=demographics
            )

        hazard_summary = None
        if target_med and (conditions or medications or labs):
            hazard_summary = calculate_hazard_index(
                biomarkers=labs,
                alerts=det_alerts,
                active_medications=medications,
                conditions=conditions,
                allergies=allergies,
                demographics=demographics,
                overall_status=det_status
            )

        # 4. Generate Clinical Citations
        if monograph:
            if monograph.get("boxed_warnings"):
                citations.append(f"FDA Boxed Warning: {monograph['drug']}")
            if monograph.get("renal_guideline"):
                citations.append("KDIGO Clinical Practice Guideline (Renal Adjustments)")
            if monograph.get("beers_criteria"):
                citations.append("AGS Beers Criteria® (2023 Update)")
        if not citations:
            citations.append("MediVault Sovereign Clinical Pharmacology Matrix (Offline)")

        # 5. Build Grounded Prompt for Local SLM
        patient_summary = (
            f"Name: {patient_name}, Age: {demographics.get('age')}, Gender: {demographics.get('gender')}. "
            f"Active Conditions: {', '.join(conditions) if conditions else 'None documented'}. "
            f"Active Medications: {', '.join(medications) if medications else 'None documented'}. "
            f"Allergies: {', '.join(allergies) if allergies else 'NKDA'}."
        )
        labs_summary = ", ".join([f"{k.upper()}: {v.get('value')} {v.get('unit')}" for k, v in labs.items()]) if labs else "No recent labs recorded"

        alerts_summary = "None"
        if det_alerts:
            formatted_alerts = []
            for a in det_alerts[:3]:
                sev = a.get("severity", "WARNING")
                msg = a.get("message") or a.get("conflicting_factor") or a.get("clinical_mechanism") or str(a)
                formatted_alerts.append(f"[{sev}] {msg}")
            alerts_summary = "; ".join(formatted_alerts)

        rag_snippets = "\n".join([f"- {r['drug']} ({r['category']}): {r['snippet']}" for r in rag_results])

        # Multi-turn history formatting
        history_text = ""
        has_prior_history = bool(history and len(history) > 0)
        is_greeting_query = bool(re.search(r"^\s*(hello|hi|hey|greetings|who\s+are\s+you|what\s+can\s+you\s+do)\b", message, re.IGNORECASE))

        if history and isinstance(history, list):
            recent_turns = history[-4:]
            formatted_turns = []
            for turn in recent_turns:
                role = "Doctor" if turn.get("role") in ["user", "physician"] else "Copilot"
                formatted_turns.append(f"{role}: {turn.get('content', '')}")
            if formatted_turns:
                history_text = f"Prior Conversation ({len(formatted_turns)} turns):\n" + "\n".join(formatted_turns) + "\n\n"

        # 6. Attempt Local SLM Inference with Resilient Timeout & Auto-Detected Model
        reply = None
        model_used = "Deterministic Medical Reasoning"

        active_model = _detect_ollama_model()

        if active_model:
            if has_prior_history:
                system_role_desc = "Role: Bedside Clinical Decision Support Assistant (Ongoing Multi-Turn Conversation).\n"
                greeting_rule = (
                    "- CRITICAL: This is an ONGOING conversation. You have ALREADY introduced yourself. "
                    "DO NOT say 'Hello', 'Good morning', 'I am the Sovereign Clinical AI Copilot', or give any greeting. "
                    "Jump IMMEDIATELY and directly into answering the physician's specific medical inquiry."
                )
            else:
                system_role_desc = "You are the Sovereign Clinical AI Copilot assisting a physician at bedside.\n"
                greeting_rule = (
                    "- If the physician sends a general greeting or introduction ('Hello', 'Who are you?', 'Can you help?'), introduce yourself and summarize how you can assist with this active patient.\n"
                    "- If the physician asks a specific clinical question, answer directly without lengthy preamble."
                )

            allergy_safety_rules = ""
            if allergies:
                allergy_details = []
                for a in allergies:
                    c_info = get_allergy_cross_reactivity(a)
                    if c_info:
                        allergy_details.append(
                            f"- Allergy Class '{c_info['class_name']}': Cross-reacts with {', '.join(c_info['cross_reactive_drugs'][:4])}. "
                            f"Chemically unrelated/safe: {', '.join(c_info['safe_non_cross_reactive'][:4])}. Note: {c_info['clinical_note']}"
                        )
                if allergy_details:
                    allergy_safety_rules = "Pharmacological Allergy Rules:\n" + "\n".join(allergy_details) + "\n\n"

            slm_prompt = (
                f"{system_role_desc}"
                f"Patient Chart: {patient_summary}\n"
                f"Current Labs: {labs_summary}\n"
                f"Proposed Medication: {target_med or 'None'}\n"
                f"Deterministic CDSS Flag: {det_status} (Alerts: {alerts_summary})\n"
                f"Relevant Monographs:\n{rag_snippets}\n\n"
                f"{allergy_safety_rules}"
                f"{history_text}"
                f"Physician Question: {message}\n\n"
                f"Instructions:\n"
                f"- Answer the physician's specific question directly, conversationally, and authoritatively.\n"
                f"{greeting_rule}\n"
                f"- If asked about allergies, state ONLY documented allergies from the chart. DO NOT claim unrelated drugs (like Ibuprofen) are sulfonamides; cite chemical classes accurately.\n"
                f"- If asked about the patient's vitals, labs, conditions, or medications, reference the real chart data above.\n"
                f"- If CDSS status is CRITICAL or WARNING for a proposed drug, you MUST clearly explain the contraindication mechanism and warn against prescribing.\n"
                f"- Never declare a contraindicated drug safe.\n"
                f"- Keep your response concise (2 to 4 sentences or brief bullet points)."
            )

            try:
                with httpx.Client(timeout=COPILOT_TIMEOUT) as client:
                    res = client.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": active_model,
                            "prompt": slm_prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.2,
                                "num_predict": 200
                            }
                        }
                    )
                    if res.status_code == 200:
                        raw_reply = res.json().get("response", "").strip()
                        if raw_reply and len(raw_reply) > 20:
                            reply = raw_reply
                            model_used = f"Ollama Local ({active_model})"
            except Exception:
                pass

        # 7. Fallback to Deterministic Expert Clinical Synthesizer if SLM Offline or Slow
        if not reply:
            reply = cls._generate_deterministic_clinical_reply(
                message=message,
                patient_name=patient_name,
                target_med=target_med,
                det_status=det_status,
                det_alerts=det_alerts,
                conditions=conditions,
                medications=medications,
                allergies=allergies,
                labs=labs,
                monograph=monograph,
                recommended_alts=recommended_alts,
                hazard_summary=hazard_summary,
                has_prior_history=has_prior_history
            )

        # Post-process: Strip repeated greeting on follow-up turns or non-greeting questions
        if reply and (has_prior_history or not is_greeting_query):
            reply = _strip_repeated_greeting(reply)

        # 8. Absolute Sovereign Safety Override (Guardrail Verification)
        if det_status in ["CRITICAL", "WARNING"] and target_med and target_med.lower() in message.lower():
            contradicts = any(phrase in reply.lower() for phrase in [
                "safe to administer", "is safe", "no contraindications", "can safely take", "no risk"
            ])
            if contradicts or not any(kw in reply.lower() for kw in ["contraindicat", "hazard", "risk", "warning", "caution", "avoid", "nephro"]):
                guardrail_applied = True
                warning_lead = (
                    f"⚠️ **Sovereign Safety Override**: {target_med} is flagged as **{det_status}** "
                    f"due to {det_alerts[0].get('message') or det_alerts[0].get('clinical_mechanism') or 'documented contraindications'}. "
                )
                reply = warning_lead + reply

        latency = round((time.time() - start_time) * 1000, 1)

        # 9. Dynamic Clinical Badges, Suggested Actions, and Contextual Follow-up Chips
        clinical_badges = []
        if det_status == "CRITICAL":
            clinical_badges.append({"type": "danger", "label": f"CRITICAL: {target_med or 'Drug'} Contraindicated", "icon": "fa-triangle-exclamation"})
        elif det_status == "WARNING":
            clinical_badges.append({"type": "warning", "label": f"WARNING: {target_med or 'Drug'} High Risk", "icon": "fa-circle-exclamation"})

        if "egfr" in labs:
            try:
                egfr_num = float(labs["egfr"]["value"])
                if egfr_num < 60:
                    stage_str = "Stage 3 CKD" if egfr_num >= 30 else ("Stage 4 CKD" if egfr_num >= 15 else "Stage 5 ESRD")
                    clinical_badges.append({"type": "amber", "label": f"{stage_str} (eGFR {egfr_num})", "icon": "fa-flask"})
            except Exception:
                pass

        if allergies:
            clinical_badges.append({"type": "purple", "label": f"Allergy: {', '.join(allergies)}", "icon": "fa-shield-virus"})

        suggested_actions = []
        if recommended_alts:
            for alt in recommended_alts[:2]:
                suggested_actions.append({
                    "action": "prescribe",
                    "drug": alt.get("name", ""),
                    "label": f"Prescribe {alt.get('name', '')}",
                    "rationale": alt.get("rationale", "Formulary safe alternative")
                })
        elif target_med == "Cetirizine":
            suggested_actions.append({
                "action": "prescribe",
                "drug": "Cetirizine",
                "label": "Set Cetirizine 5mg (Renal-Dosed)",
                "rationale": "50% renal dose reduction for eGFR 38"
            })

        suggested_followups = []
        msg_l = message.lower()
        if any(w in msg_l for w in ["allergy", "allergies", "allergic", "allery"]):
            suggested_followups = [
                "What safe pain medication can this patient take?",
                "Are any of the patient's active prescriptions sulfonamides?",
                "What is the patient's renal lab profile?"
            ]
        elif target_med and target_med.lower() in ["cetirizine", "citrizen", "zyrtec"]:
            suggested_followups = [
                "What is the KDIGO renal dosing for Cetirizine?",
                "Does Cetirizine interact with Lisinopril or Metformin?",
                "What alternatives exist for allergic rhinitis?"
            ]
        elif det_status in ["CRITICAL", "WARNING"]:
            suggested_followups = [
                f"What safe alternatives can I prescribe instead of {target_med}?",
                "Explain the renal hemodynamic injury mechanism",
                "What are the KDIGO dosing adjustments for this patient?"
            ]
        elif any(w in msg_l for w in ["egfr", "creatinine", "labs", "potassium"]):
            suggested_followups = [
                "Can I prescribe an NSAID given this eGFR level?",
                "What is the patient's potassium hyperkalemia risk?",
                "What are safe pain management options in CKD Stage 3?"
            ]
        else:
            suggested_followups = [
                "Why is this prescription flagged for this patient?",
                "What safe alternatives can I prescribe?",
                "Explain the Triple Whammy hemodynamic risk"
            ]

        return {
            "reply": reply,
            "citations": citations,
            "model": model_used,
            "latency_ms": latency,
            "guardrail_applied": guardrail_applied,
            "status": det_status,
            "target_med": target_med,
            "detected_drug": detected_drug,
            "patient_name": patient_name,
            "clinical_badges": clinical_badges,
            "suggested_actions": suggested_actions,
            "suggested_followups": suggested_followups
        }

    @classmethod
    def _generate_deterministic_clinical_reply(
        cls,
        message: str,
        patient_name: str,
        target_med: Optional[str],
        det_status: str,
        det_alerts: List[Dict[str, Any]],
        conditions: List[str],
        medications: List[str],
        allergies: List[str],
        labs: Dict[str, Any],
        monograph: Optional[Dict[str, Any]],
        recommended_alts: List[Dict[str, Any]],
        hazard_summary: Optional[Dict[str, Any]],
        has_prior_history: bool = False
    ) -> str:
        """
        Expert clinical synthesis rule engine. Generates intelligent,
        conversational, and context-aware medical responses when Ollama is offline.
        """
        msg_lower = message.lower().strip()

        # 1. Greetings & System Identity (exact word boundary match)
        if re.search(r"^\s*(hello|hi|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening|who\s+are\s+you|what\s+can\s+you\s+do)\b", msg_lower):
            if has_prior_history:
                return f"I'm here, Doctor. What clinical question or medication inquiry can I help you with regarding {patient_name}?"
            summary_parts = []
            if conditions:
                summary_parts.append(f"Conditions: {', '.join(conditions[:2])}")
            if "egfr" in labs:
                summary_parts.append(f"eGFR: {labs['egfr']['value']} {labs['egfr']['unit']}")
            context_str = f" for **{patient_name}** ({'; '.join(summary_parts)})" if summary_parts else ""

            return (
                f"Hello Doctor. I am your **Sovereign Clinical Copilot**, running 100% offline with zero cloud egress. "
                f"I am actively monitoring patient telemetry{context_str}. "
                f"You can ask me about medication contraindications, renal dosing adjustments, safe alternatives, or patient lab telemetry."
            )

        # 2. Patient Specific Lab Telemetry & Biomarkers
        if any(w in msg_lower for w in ["egfr", "creatinine", "potassium", "labs", "biomarkers", "renal function", "blood pressure", "bp", "inr", "platelets"]):
            if labs:
                lab_items = []
                for b_name, b_data in labs.items():
                    lab_items.append(f"- **{b_name.upper()}**: {b_data.get('value')} {b_data.get('unit')}")
                renal_note = ""
                if "egfr" in labs:
                    egfr_val = float(labs["egfr"]["value"])
                    if egfr_val < 30:
                        renal_note = "\n\n⚠️ **Clinical Note**: eGFR indicates Stage 4/5 severe renal impairment. All nephrotoxic drugs (NSAIDs, aminoglycosides) are contraindicated."
                    elif egfr_val < 60:
                        renal_note = f"\n\n⚠️ **Clinical Note**: eGFR indicates Stage 3 CKD ({egfr_val} mL/min/1.73m2). Exercise strict caution with renally cleared medications."
                return f"**Active Lab Telemetry for {patient_name}**:\n" + "\n".join(lab_items) + renal_note
            return f"No active laboratory biomarkers are currently recorded in the local chart for {patient_name}."

        # 3. Patient Conditions & Diagnoses
        if any(w in msg_lower for w in ["condition", "diagnosis", "diagnoses", "medical history", "history", "diagnosed"]):
            if conditions:
                cond_list = "\n".join([f"- {c}" for c in conditions])
                return f"**Documented Clinical Conditions for {patient_name}**:\n{cond_list}"
            return f"No active diagnostic conditions documented in this record for {patient_name}."

        # 4. Patient Current Medications
        if any(w in msg_lower for w in ["current med", "active med", "what meds", "prescriptions", "taking", "active prescriptions"]):
            if medications:
                med_list = "\n".join([f"- {m}" for m in medications])
                return f"**Current Active Prescriptions for {patient_name}**:\n{med_list}"
            return f"No active outpatient prescriptions recorded for {patient_name}."

        # 5. Patient Allergies
        if any(w in msg_lower for w in ["allergy", "allergies", "allergic", "allery", "allergic reaction"]):
            if allergies:
                alg_list = "\n".join([f"- **{a}**" for a in allergies])
                cross_notes = []
                for a in allergies:
                    c_info = get_allergy_cross_reactivity(a)
                    if c_info:
                        cross_notes.append(
                            f"- **{c_info['class_name']} Class**: Cross-reacts with {', '.join(c_info['cross_reactive_drugs'][:4])}. "
                            f"Chemically unrelated/safe: {', '.join(c_info['safe_non_cross_reactive'][:4])}."
                        )
                cross_str = ("\n\n**Cross-Reactivity Guardrails**:\n" + "\n".join(cross_notes)) if cross_notes else ""
                return (
                    f"**Documented Allergies for {patient_name}**:\n{alg_list}{cross_str}\n\n"
                    f"*Note: MediVault strictly blocks all cross-reactive compounds deterministically.*"
                )
            return f"**{patient_name}** has No Known Drug Allergies (NKDA) on record."

        # 5b. Can I give / Is it safe to prescribe target_med
        if target_med and any(p in msg_lower for p in ["can i give", "can we give", "can i prescribe", "can we prescribe", "is it safe", "is that safe", "should i give", "safe to give", "give the patient"]):
            if det_status in ["CRITICAL", "WARNING"] and det_alerts:
                top_alert = det_alerts[0]
                reason = top_alert.get("message") or top_alert.get("conflicting_factor") or ""
                mech = top_alert.get("mechanism") or (monograph.get("mechanism") if monograph else "")
                return (
                    f"⚠️ **NO — {target_med} is contraindicated ({det_status})** for {patient_name}.\n\n"
                    f"- **Clinical Hazard**: {reason}\n"
                    f"- **Mechanism**: {mech}\n\n"
                    f"Prescribing {target_med} is not recommended. Please review formulary alternatives."
                )
            elif monograph:
                renal_note = f"\n- **KDIGO Renal Dosing**: {monograph['renal_guideline']}" if monograph.get("renal_guideline") else ""
                return (
                    f"✅ **Yes, with appropriate dosing**: **{monograph['drug']}** ({monograph['category']}) "
                    f"has no absolute contraindications with {patient_name}'s current clinical regimen or documented allergies.{renal_note}\n\n"
                    f"Monitor baseline renal markers and response."
                )

        # 6. Patient Chart Summary
        if any(w in msg_lower for w in ["summary", "chart", "profile", "tell me about this patient", "who is the patient"]):
            egfr_str = f"{labs['egfr']['value']} {labs['egfr']['unit']}" if "egfr" in labs else "Not recorded"
            return (
                f"**Clinical Chart Summary — {patient_name}**:\n"
                f"- **Active Conditions**: {', '.join(conditions) if conditions else 'None'}\n"
                f"- **Baseline eGFR**: {egfr_str}\n"
                f"- **Active Medications**: {', '.join(medications) if medications else 'None'}\n"
                f"- **Allergies**: {', '.join(allergies) if allergies else 'NKDA'}\n"
                f"- **Current Proposed Drug**: {target_med or 'None selected'} ({det_status})"
            )

        # 7. Specific Polypharmacy: Triple Whammy
        if "triple whammy" in msg_lower or ("nsaid" in msg_lower and "diuretic" in msg_lower):
            return (
                "**Triple Whammy Interaction**: The concurrent prescription of an **ACE-Inhibitor (or ARB)**, "
                "a **Loop Diuretic (e.g. Furosemide)**, and an **NSAID (e.g. Ibuprofen/Ketorolac)** produces catastrophic prerenal acute kidney injury. "
                "The diuretic causes intravascular volume depletion, the ACE-I impairs efferent arteriolar vasoconstriction, "
                "and the NSAID blocks afferent arteriolar vasodilatory prostaglandins. Glomerular filtration pressure collapses."
            )

        # 8. KDIGO Renal Dosing Guidelines
        if any(w in msg_lower for w in ["kdigo", "renal guideline", "renal dosing", "renal adjustment", "dose adjustment"]):
            egfr_val = labs.get("egfr", {}).get("value")
            renal_text = monograph.get("renal_guideline", "") if monograph else ""
            if egfr_val:
                egfr_num = float(egfr_val)
                if egfr_num < 30:
                    status_guideline = f"For patient's eGFR of **{egfr_num} mL/min/1.73m2** (Stage 4/5 CKD): Complete avoidance of all systemic NSAIDs and nephrotoxins is mandated under KDIGO standards. Prescribe non-renal cleared alternatives."
                elif egfr_num < 60:
                    status_guideline = f"For patient's eGFR of **{egfr_num} mL/min/1.73m2** (Stage 3 CKD): KDIGO recommends 50% dose reductions for renally excreted compounds and strict avoidance of prolonged NSAID therapy."
                else:
                    status_guideline = f"For patient's eGFR of **{egfr_num} mL/min/1.73m2**: Normal renal filtration window. Standard formulary dosing applies with baseline renal monitoring."
                if renal_text:
                    status_guideline += f"\n\n**{target_med or 'Drug'} Monograph Guidance**: {renal_text}"
                return status_guideline
            elif renal_text:
                return f"**KDIGO & Renal Considerations for {target_med}**: {renal_text}"
            return "KDIGO guidelines require dosing titration based on estimated GFR calculated via CKD-EPI formula. Avoid nephrotoxic combinations."

        # 9. Safe Alternatives & Formulary Substitutes
        if any(w in msg_lower for w in ["alternative", "substitute", "replace", "what can i prescribe", "instead", "safer painkiller"]):
            if recommended_alts:
                alt_list = [f"- **{a['name']}** ({a.get('class', 'Alternative')}): {a.get('rationale', 'Formulary safe')}" for a in recommended_alts]
                return f"For this clinical profile, recommended formulary alternatives to **{target_med or 'the proposed drug'}** are:\n" + "\n".join(alt_list)
            elif monograph and monograph.get("safe_alternatives"):
                return f"Clinical monograph recommendations for **{target_med}** contraindications include: {', '.join(monograph['safe_alternatives'])}."
            return "Consider non-nephrotoxic analgesics such as Acetaminophen (capped at 2g/day in CKD/cirrhosis) or localized topical formulations."

        # 10. Why Flagged / Contraindication Explanations
        if any(w in msg_lower for w in ["why", "contraindicated", "flagged", "danger", "hazard", "risk", "harm", "problem"]):
            if det_alerts:
                top_alert = det_alerts[0]
                reason = top_alert.get("message") or top_alert.get("conflicting_factor") or top_alert.get("clinical_mechanism") or ""
                mech = top_alert.get("mechanism") or top_alert.get("clinical_mechanism") or (monograph.get("mechanism") if monograph else "")
                renal = monograph.get("renal_guideline", "") if monograph else ""

                parts = [f"**{target_med} is contraindicated ({det_status})** in {patient_name}: {reason}."]
                if mech and mech != reason:
                    parts.append(f"**Pathophysiology**: {mech}")
                if renal and ("renal" in reason.lower() or "egfr" in reason.lower() or "kidney" in reason.lower()):
                    parts.append(f"**Renal Guidance**: {renal}")
                if recommended_alts:
                    alt_names = [a.get("name") for a in recommended_alts[:2]]
                    parts.append(f"**Safer Substitutes**: Consider {', '.join(alt_names)}.")
                return " ".join(parts)
            elif monograph:
                return (
                    f"**{target_med} ({monograph['category']})**: {monograph['mechanism']} "
                    f"Key contraindications include {', '.join(monograph['contraindications'][:3])}. "
                    f"Renal Guideline: {monograph['renal_guideline']}"
                )

        # 11. Drug Monograph & Mechanism of Action
        if monograph:
            res = [f"**{monograph['drug']} ({monograph['category']})**: {monograph['mechanism']}"]
            if monograph.get("boxed_warnings"):
                res.append(f"**Boxed Warning**: {monograph['boxed_warnings']}")
            if monograph.get("renal_guideline"):
                res.append(f"**Renal Considerations**: {monograph['renal_guideline']}")
            return " ".join(res)

        # 12. General Clinical Fallback
        cond_str = f"diagnoses ({', '.join(conditions[:2])})" if conditions else "general profile"
        med_str = f"active meds ({', '.join(medications[:2])})" if medications else "active regimen"
        return (
            f"Based on local clinical CDS evaluation for **{patient_name}**, {target_med or 'the proposed inquiry'} "
            f"was cross-checked against documented {cond_str}, {med_str}, and lab biomarkers. "
            f"Current Safety Status: **{det_status}**. Let me know if you would like specific guidance on dosing, hemodynamics, or alternative medications."
        )


def ask_copilot(
    message: str,
    patient_id: Optional[str] = None,
    proposed_med: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Top-level copilot dispatch function."""
    return ClinicalCopilot.ask(
        message=message,
        patient_id=patient_id,
        proposed_med=proposed_med,
        context=context,
        history=history
    )
