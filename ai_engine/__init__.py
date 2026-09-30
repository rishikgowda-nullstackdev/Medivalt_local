"""
MediVault Local - Clinical AI & Pharmacology Engine (Person C)
Implements deterministic SQLite pharmacology rules, multi-drug polypharmacy matrix,
quantitative lab biomarker threshold evaluator, safe alternative recommender,
clinical hazard index gauge, pharmacokinetic clearance curves, and local SLM (llama3.2:3b) synthesis.
"""

from ai_engine.engine import analyze, evaluate_full_safety
from ai_engine.pharmacology import PharmacologyKnowledge
from ai_engine.polypharmacy import PolypharmacyEngine
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
from ai_engine.alternatives import SafeAlternativeRecommender
from ai_engine.geriatric_renal import GeriatricRenalEngine, calculate_cockcroft_gault
from ai_engine.hazard_index import calculate_hazard_index
from ai_engine.pk_model import simulate_pk_curve, resolve_pk_drug, calculate_patient_ke
from ai_engine.vector_rag import search_clinical_knowledge, get_monograph, list_monographs, ClinicalVectorRAG
from ai_engine.copilot import ask_copilot, ClinicalCopilot

__all__ = [
    "analyze",
    "evaluate_full_safety",
    "PharmacologyKnowledge",
    "PolypharmacyEngine",
    "LabBiomarkerEvaluator",
    "SafeAlternativeRecommender",
    "GeriatricRenalEngine",
    "calculate_cockcroft_gault",
    "calculate_hazard_index",
    "simulate_pk_curve",
    "resolve_pk_drug",
    "calculate_patient_ke",
    "search_clinical_knowledge",
    "get_monograph",
    "list_monographs",
    "ClinicalVectorRAG",
    "ask_copilot",
    "ClinicalCopilot"
]
