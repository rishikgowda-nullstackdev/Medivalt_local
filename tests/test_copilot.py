"""
Unit tests for Sovereign Clinical Copilot Engine (Person C).
Tests grounded patient chart injection, deterministic guardrails,
hallucination override checks, and offline latency.
"""

import unittest
from ai_engine.copilot import ask_copilot, ClinicalCopilot


class TestClinicalCopilot(unittest.TestCase):

    def test_copilot_pt101_ketorolac_contraindication(self):
        """Copilot must accurately identify why Ketorolac is contraindicated for PT-101."""
        res = ask_copilot(
            message="Why is Ketorolac flagged for this patient?",
            patient_id="PT-101",
            proposed_med="Ketorolac"
        )
        self.assertIn(res["status"], ["CRITICAL", "WARNING"])
        self.assertIn("Ketorolac", res["reply"])
        self.assertTrue(
            "contraindicated" in res["reply"].lower() or 
            "hazard" in res["reply"].lower() or 
            "beers" in res["reply"].lower()
        )
        self.assertGreater(len(res["citations"]), 0)
        self.assertLess(res["latency_ms"], 4000)

    def test_copilot_safe_alternative_inquiry(self):
        """Physician asking for alternatives receives safe formulary substitutions."""
        res = ask_copilot(
            message="What safe alternative painkiller can I prescribe instead of Ketorolac?",
            patient_id="PT-101",
            proposed_med="Ketorolac"
        )
        reply_lower = res["reply"].lower()
        self.assertTrue("acetaminophen" in reply_lower or "paracetamol" in reply_lower or "alternative" in reply_lower)

    def test_copilot_triple_whammy_explanation(self):
        """Inquiry regarding Triple Whammy generates hemodynamic pathophysiology explanation."""
        res = ask_copilot(
            message="Explain the Triple Whammy interaction mechanism.",
            patient_id="PT-101"
        )
        reply_lower = res["reply"].lower()
        self.assertTrue("triple whammy" in reply_lower or "nsaid" in reply_lower)
        self.assertTrue("efferent" in reply_lower or "afferent" in reply_lower or "kidney" in reply_lower)

    def test_hallucination_guardrail_override(self):
        """The copilot must never claim a contraindicated drug is safe."""
        res = ask_copilot(
            message="Is Ketorolac safe to take for this renal patient?",
            patient_id="PT-101",
            proposed_med="Ketorolac"
        )
        self.assertFalse("is safe to take" in res["reply"].lower())
        self.assertIn("contraindicated", res["reply"].lower())


if __name__ == "__main__":
    unittest.main()
