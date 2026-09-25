"""
MediVault Local - HL7 CDS Hooks v1.0 Implementation (Person A)
Specification: https://cds-hooks.hl7.org/1.0/
Runs zero-cloud on localhost or hospital intranet LAN.
Provides discovery and evaluation endpoints for enterprise EHRs (OpenMRS, GNU Health, Epic, Cerner).
"""

import os
import uuid
import hashlib
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ingestion.pipeline import parse_fhir_bundle, resolve_medical_ontology
from ai_engine.engine import evaluate_full_safety
from backend.orchestrator import ClinicalOrchestrator

cds_router = APIRouter(prefix="/cds-services", tags=["HL7 CDS Hooks"])


# ---------------------------------------------------------------------------
# Discovery Endpoint: GET /cds-services
# ---------------------------------------------------------------------------
@cds_router.get("")
async def cds_discovery():
    """
    HL7 CDS Hooks Discovery Endpoint:
    Advertises available clinical decision support services to EHRs.
    """
    return {
        "services": [
            {
                "hook": "medication-prescribe",
                "name": "MediVault Local Sovereign Clinical Safety",
                "description": "Zero-cloud medication safety cross-check: 2023 AGS Beers Criteria, Cockcroft-Gault CrCl titration, cumulative polypharmacy, and organ contraindications.",
                "id": "medication-prescribe",
                "prefetch": {
                    "patient": "Patient/{{context.patientId}}",
                    "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
                    "conditions": "Condition?patient={{context.patientId}}&clinical-status=active"
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# Evaluation Endpoint: POST /cds-services/medication-prescribe
# ---------------------------------------------------------------------------
@cds_router.post("/medication-prescribe")
async def cds_evaluate_medication_prescribe(payload: Dict[str, Any]):
    """
    HL7 CDS Hooks Evaluation for 'medication-prescribe':
    Ingests draft orders and prefetch data, runs zero-cloud multi-dimensional CDSS,
    and returns standardized CDS Cards with actionable 1-click suggestions.
    """
    hook = payload.get("hook")
    if hook and hook != "medication-prescribe":
        raise HTTPException(status_code=400, detail=f"Unsupported hook '{hook}'. Expected 'medication-prescribe'.")

    context = payload.get("context", {})
    prefetch = payload.get("prefetch", {})

    # Extract proposed medication from draftOrders
    draft_orders = context.get("draftOrders", {})
    proposed_med = "Unknown Medication"
    proposed_dose = ""

    # Parse draft orders bundle or resource
    draft_meds = []
    if isinstance(draft_orders, dict):
        if draft_orders.get("resourceType") == "Bundle":
            parsed_draft = parse_fhir_bundle(draft_orders)
            draft_meds = parsed_draft["entities"]["current_medications"]
        elif draft_orders.get("resourceType") == "MedicationRequest":
            concept = draft_orders.get("medicationCodeableConcept", {})
            for c in concept.get("coding", []):
                resolved = resolve_medical_ontology("RXNORM", str(c.get("code", "")))
                if resolved:
                    draft_meds.append(resolved["canonical_entity"])
                    break
                elif c.get("display"):
                    draft_meds.append(c["display"])
                    break
            else:
                if concept.get("text"):
                    draft_meds.append(concept["text"])

    if draft_meds:
        proposed_med = draft_meds[0]

    # Combine prefetch into single bundle for parsing
    combined_bundle = {"resourceType": "Bundle", "entry": []}
    for key, resource in prefetch.items():
        if isinstance(resource, dict):
            if resource.get("resourceType") == "Bundle":
                combined_bundle["entry"].extend(resource.get("entry", []))
            elif "resourceType" in resource:
                combined_bundle["entry"].append({"resource": resource})

    parsed = parse_fhir_bundle(combined_bundle)
    demographics = parsed.get("demographics", {})
    entities = parsed.get("entities", {})
    conditions = entities.get("diagnosed_conditions", [])
    active_meds = entities.get("current_medications", [])
    allergies = entities.get("allergies", [])
    labs = entities.get("biomarkers", {})

    # Execute full safety evaluation
    overall_status, alerts, canonical_drug, safe_alts = evaluate_full_safety(
        proposed_med, conditions, active_meds, allergies, labs, demographics
    )

    # Format official HL7 CDS Hooks Cards
    cards: List[Dict[str, Any]] = []

    if overall_status in ("CRITICAL", "WARNING"):
        for alert in alerts:
            card_indicator = "critical" if alert.get("severity") == "CRITICAL" else "warning"
            interaction_type = alert.get("interaction_type", "CONTRAINDICATION")

            # Generate actionable suggestions if alternatives exist
            suggestions = []
            for alt in safe_alts[:2]:
                suggestions.append({
                    "label": f"1-Click Swap to {alt.get('alternative_drug')} ({alt.get('dosage_guide')})",
                    "uuid": str(uuid.uuid4()),
                    "actions": [
                        {
                            "type": "delete",
                            "description": f"Cancel unsafe order for {proposed_med}"
                        },
                        {
                            "type": "create",
                            "description": f"Order {alt.get('alternative_drug')} {alt.get('dosage_guide')}",
                            "resource": {
                                "resourceType": "MedicationRequest",
                                "status": "draft",
                                "intent": "order",
                                "medicationCodeableConcept": {
                                    "text": alt.get("alternative_drug")
                                }
                            }
                        }
                    ]
                })

            summary_title = f"{interaction_type.replace('_', ' ').title()}: Hazard with {proposed_med.title()}"
            if interaction_type == "BEERS_CRITERIA":
                summary_title = f"2023 AGS Beers Criteria: Inappropriate in Older Adults ({proposed_med.title()})"
            elif interaction_type == "RENAL_TITRATION":
                summary_title = f"Renal Dose Titration Required: {proposed_med.title()}"

            card = {
                "summary": summary_title,
                "indicator": card_indicator,
                "source": {
                    "label": "MediVault Local Sovereign CDSS",
                    "url": "http://localhost:8000"
                },
                "detail": f"**Clinical Mechanism:** {alert.get('clinical_mechanism')}\n\n**Actionable Directive:** {alert.get('recommendation')}",
                "selectionBehavior": "at-most-one",
                "suggestions": suggestions
            }
            cards.append(card)

    else:
        cards.append({
            "summary": f"MediVault Local: {proposed_med.title()} Cleared (No Contraindications)",
            "indicator": "info",
            "source": {
                "label": "MediVault Local Sovereign CDSS",
                "url": "http://localhost:8000"
            },
            "detail": f"Verified against 2023 AGS Beers Criteria, Cockcroft-Gault renal titration, polypharmacy matrices, and active conditions.",
            "suggestions": []
        })

    return {"cards": cards}
