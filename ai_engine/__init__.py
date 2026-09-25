"""
MediVault Local - Clinical AI & Pharmacology Engine (Person C)
Implements deterministic SQLite pharmacology rules, multi-drug polypharmacy matrix,
quantitative lab biomarker threshold evaluator, safe alternative recommender,
and local SLM (llama3.2:3b) clinical explanation synthesis.
"""

from ai_engine.engine import analyze, evaluate_full_safety
from ai_engine.pharmacology import PharmacologyKnowledge
from ai_engine.polypharmacy import PolypharmacyEngine
from ai_engine.lab_evaluator import LabBiomarkerEvaluator
from ai_engine.alternatives import SafeAlternativeRecommender
from ai_engine.geriatric_renal import GeriatricRenalEngine, calculate_cockcroft_gault

__all__ = [
    "analyze",
    "evaluate_full_safety",
    "PharmacologyKnowledge",
    "PolypharmacyEngine",
    "LabBiomarkerEvaluator",
    "SafeAlternativeRecommender",
    "GeriatricRenalEngine",
    "calculate_cockcroft_gault"
]
