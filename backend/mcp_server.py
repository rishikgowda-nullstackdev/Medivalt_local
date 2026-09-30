"""
MediVault Local — Offline FastMCP Clinical Decision Support Server (Person A + Person C)
Implements Model Context Protocol (MCP) specification 2024-11-05 via MCPServer.
Exposes zero-cloud clinical pharmacology tools to external agents (Claude Desktop, Cursor, local SLMs)
over stdio JSON-RPC and REST loopback.
Guarantees 100% offline sovereign operation (zero external network egress).
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mcp.server.mcpserver import MCPServer

logger = logging.getLogger("medivault.mcp")

# Initialize Sovereign Clinical MCP Server
mcp_server = MCPServer(
    name="medivault-local-cdss",
    version="1.0.0",
    description="Zero-Cloud Offline Clinical Decision Support System & Pharmacovigilance Engine"
)


@mcp_server.tool()
def review_prescription(patient_id: str = "PT-101", proposed_drug: str = "Ibuprofen", enable_slm: bool = False) -> str:
    """
    Cross-checks a proposed prescription against a patient's diagnostic history,
    active medications, allergies, and organ function (eGFR, Creatinine, LFTs).
    Evaluates KDIGO renal staging, Beers criteria, and dangerous polypharmacy cascades.

    Args:
        patient_id: Identifier of the patient (e.g. 'PT-101', 'PT-102')
        proposed_drug: Medication name and dosage (e.g. 'Ibuprofen 400mg', 'Ketorolac')
        enable_slm: If True, enriches the deterministic review with local SLM narrative.
    """
    try:
        from backend.orchestrator import ClinicalOrchestrator
        result = ClinicalOrchestrator.process_review(
            proposed_med=proposed_drug,
            patient_id=patient_id,
            enable_slm=enable_slm
        )
        return json.dumps({
            "status": result.get("overall_status"),
            "proposed_medication": result.get("proposed_medication"),
            "total_alerts": result.get("total_alerts"),
            "alerts": result.get("alerts", []),
            "explanation": result.get("explanation"),
            "hazard_index": result.get("hazard_index"),
            "pk_simulation": {
                "drug": result.get("pk_simulation", {}).get("drug_name"),
                "half_life_normal_hr": result.get("pk_simulation", {}).get("half_life_normal_hr"),
                "half_life_patient_hr": result.get("pk_simulation", {}).get("half_life_patient_hr"),
                "renal_clearance_status": result.get("pk_simulation", {}).get("clinical_alert")
            } if result.get("pk_simulation") else None,
            "recommended_alternatives": result.get("recommended_alternatives", []),
            "audit_hash": result.get("audit_hash"),
            "execution_time_ms": result.get("execution_time_ms")
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to execute clinical review: {str(e)}"})


@mcp_server.tool()
def simulate_pharmacokinetics(drug_name: str = "Ibuprofen", egfr: float = 38.0, dose_mg: float = 400.0, hours: float = 72.0) -> str:
    """
    Simulates a 72-hour multi-compartment pharmacokinetic clearance curve comparing
    standard normal excretion against patient-specific renal impairment clearance.

    Args:
        drug_name: Drug to simulate (e.g. 'Ibuprofen', 'Ketorolac', 'Metformin', 'Lisinopril')
        egfr: Patient estimated Glomerular Filtration Rate in mL/min/1.73m2
        dose_mg: Prescribed dose in milligrams
        hours: Simulation timeline duration (default: 72.0 hours)
    """
    try:
        from ai_engine.pk_model import simulate_pk_curve
        sim = simulate_pk_curve(
            drug_name=drug_name,
            egfr=egfr,
            dose_mg=dose_mg,
            total_hours=hours
        )
        return json.dumps({
            "drug_name": sim.get("display_name", drug_name),
            "drug_key": sim.get("drug_key", drug_name.lower()),
            "half_life_normal_hr": sim.get("half_life_normal_h"),
            "half_life_patient_hr": sim.get("half_life_patient_h"),
            "half_life_multiplier": sim.get("half_life_multiplier"),
            "clinical_alert": sim.get("titration_advice"),
            "severity_label": sim.get("severity_label"),
            "time_points_count": len(sim.get("time_points", [])),
            "patient_curve_sample": sim.get("patient_curve", [])[:10],
            "normal_curve_sample": sim.get("normal_curve", [])[:10]
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"PK simulation failed: {str(e)}"})


@mcp_server.tool()
def search_clinical_knowledge(query: str, category: Optional[str] = None, top_k: int = 3) -> str:
    """
    Executes local vector RAG semantic search across 32 curated FDA monographs,
    KDIGO guidelines, and Beers criteria using pure local NumPy cosine similarity.

    Args:
        query: Medical question or search query (e.g. 'CKD Stage 3 NSAID risk', 'Triple whammy')
        category: Optional category filter (e.g. 'NSAID', 'Cardiovascular', 'Antidiabetic')
        top_k: Number of relevant monographs to retrieve (default: 3)
    """
    try:
        from ai_engine.vector_rag import search_clinical_knowledge as _search
        matches = _search(query=query, category=category, top_k=top_k)
        return json.dumps({
            "query": query,
            "category": category,
            "total_found": len(matches),
            "monographs": matches
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {str(e)}"})


@mcp_server.tool()
def calculate_clinical_hazard(patient_id: str = "PT-101", proposed_med: str = "Ibuprofen") -> str:
    """
    Calculates a multi-dimensional 0-100 Clinical Hazard Index composite score
    evaluating drug-drug severity, renal titration vulnerability, age-adjusted Beers criteria,
    and cumulative organ stress.

    Args:
        patient_id: Patient ID (e.g. 'PT-101')
        proposed_med: Proposed medication name
    """
    try:
        from backend.orchestrator import ClinicalOrchestrator
        res = ClinicalOrchestrator.process_review(proposed_med=proposed_med, patient_id=patient_id, enable_slm=False)
        hazard = res.get("hazard_index") or {}
        return json.dumps({
            "patient_id": patient_id,
            "proposed_med": proposed_med,
            "overall_status": res.get("overall_status"),
            "hazard_index": hazard
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Hazard calculation failed: {str(e)}"})


@mcp_server.tool()
def verify_audit_seal(audit_hash: str) -> str:
    """
    Cryptographically verifies a SHA-256 clinical audit seal against the local SQLite ledger
    for HIPAA § 164.312(b) tamper-evident compliance.

    Args:
        audit_hash: Hexadecimal SHA-256 audit seal to verify
    """
    try:
        from backend.audit_logger import audit_logger
        conn = audit_logger._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_ledger WHERE audit_hash = ?", (audit_hash,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.dumps({
                "verified": True,
                "status": "VALID_TAMPER_EVIDENT_RECORD",
                "audit_hash": audit_hash,
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "patient_token": row["patient_token"],
                "practitioner_id": row.get("practitioner_id", "N/A"),
                "hospital_name": row.get("hospital_name", "N/A"),
                "overall_status": row["overall_status"]
            }, indent=2)
        else:
            return json.dumps({
                "verified": False,
                "status": "UNVERIFIED_OR_TAMPERED",
                "message": "Audit hash does not match any entry in local cryptographic ledger."
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Audit verification failed: {str(e)}"})


def get_available_tools_list() -> List[Dict[str, Any]]:
    """Returns metadata for all available clinical tools for REST and documentation."""
    return [
        {
            "name": "review_prescription",
            "description": "Cross-checks a proposed prescription against patient diagnostic history, active medications, allergies, and organ function.",
            "parameters": {
                "patient_id": "string (e.g. 'PT-101')",
                "proposed_drug": "string (e.g. 'Ibuprofen 400mg')",
                "enable_slm": "boolean (default: false)"
            }
        },
        {
            "name": "simulate_pharmacokinetics",
            "description": "Simulates 72h renal clearance curve and compares normal vs impaired half-life.",
            "parameters": {
                "drug_name": "string",
                "egfr": "float",
                "dose_mg": "float",
                "hours": "float"
            }
        },
        {
            "name": "search_clinical_knowledge",
            "description": "Local vector RAG search across 32 FDA monographs and KDIGO guidelines.",
            "parameters": {
                "query": "string",
                "category": "string (optional)",
                "top_k": "int"
            }
        },
        {
            "name": "calculate_clinical_hazard",
            "description": "Computes composite 0-100 hazard index score and needle gauge angle.",
            "parameters": {
                "patient_id": "string",
                "proposed_med": "string"
            }
        },
        {
            "name": "verify_audit_seal",
            "description": "Cryptographically verifies SHA-256 clearance seal against local ledger.",
            "parameters": {
                "audit_hash": "string"
            }
        }
    ]


if __name__ == "__main__":
    # When run directly from CLI (e.g. by Claude Desktop or Cursor):
    # Runs the stdio JSON-RPC transport loop
    logger.info("Starting MediVault Local Sovereign MCP Server over stdio...")
    mcp_server.run()
