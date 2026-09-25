"""
MediVault Local - Local Ollama AI Bridge (Day 4)
Connects to offline local SLM (llama3.2:3b / phi3.5:3.8b) on loopback (127.0.0.1:11434).
Provides resilient timeouts and automatic fallback to deterministic synthesis if Ollama is offline.
"""

import httpx
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("medivault.ai_bridge")

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"
REQUEST_TIMEOUT_SECONDS = 4.0


class OllamaBridge:
    """
    Client for local offline Ollama inference.
    Fails safely: if Ollama is not installed or running, clinical review still proceeds
    with 100% deterministic accuracy.
    """

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Probes local Ollama instance and returns connectivity status."""
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    has_target = any("llama3.2" in m or "phi3" in m for m in models)
                    return {
                        "online": True,
                        "url": OLLAMA_BASE_URL,
                        "available_models": models,
                        "target_model_ready": has_target,
                        "active_model": DEFAULT_MODEL if has_target else (models[0] if models else "None")
                    }
        except Exception:
            pass

        return {
            "online": False,
            "url": OLLAMA_BASE_URL,
            "available_models": [],
            "target_model_ready": False,
            "active_model": "None (Using Deterministic Rule Synthesis)"
        }

    @classmethod
    def is_online(cls) -> bool:
        """Fast 0.25s check if local Ollama port is responsive."""
        try:
            with httpx.Client(timeout=0.25) as client:
                res = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    def generate_clinical_explanation(
        cls,
        proposed_drug: str,
        conflicting_factor: str,
        mechanism: str
    ) -> Optional[str]:
        """
        Invokes local SLM to generate a natural, physician-facing clinical explanation.
        Returns None if Ollama is unreachable or times out.
        """
        # Fast failover if Ollama daemon is offline (prevents 4-second connect hang)
        if not cls.is_online():
            return None
        prompt = (
            f"You are a clinical pharmacology specialist advising an emergency physician.\n"
            f"In exactly 2 concise, authoritative sentences, explain why prescribing '{proposed_drug}' "
            f"to a patient with '{conflicting_factor}' is hazardous based on this mechanism: {mechanism}.\n"
            f"Keep it direct, professional, and actionable with zero conversational filler."
        )

        payload = {
            "model": DEFAULT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 128
            }
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                res = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
                if res.status_code == 200:
                    explanation = res.json().get("response", "").strip()
                    if explanation:
                        return f"{explanation} [Local SLM: {DEFAULT_MODEL}]"
        except Exception as e:
            logger.info("Ollama inference skipped (using deterministic fallback): %s", str(e))

        return None


ai_bridge = OllamaBridge()
