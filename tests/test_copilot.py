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

    def test_copilot_multi_turn_history(self):
        """Verify copilot handles multi-turn conversation history."""
        history = [
            {"role": "user", "content": "What is the patient eGFR?"},
            {"role": "assistant", "content": "Patient PT-101 has an eGFR of 38 mL/min/1.73m² (CKD Stage 3b)."}
        ]
        res = ask_copilot(
            message="Can we prescribe an NSAID given this level?",
            patient_id="PT-101",
            proposed_med="Ibuprofen",
            history=history
        )
        self.assertIn(res["status"], ["CRITICAL", "WARNING"])
        reply_lower = res["reply"].lower()
        self.assertTrue("nsaid" in reply_lower or "ibuprofen" in reply_lower or "contraindicated" in reply_lower or "kidney" in reply_lower)

    def test_copilot_lab_profile_inquiry(self):
        """Verify copilot returns patient lab profile telemetry."""
        res = ask_copilot(
            message="What is the current patient lab profile and eGFR?",
            patient_id="PT-101"
        )
        reply_lower = res["reply"].lower()
        self.assertTrue("egfr" in reply_lower or "serum creatinine" in reply_lower or "potassium" in reply_lower)

    def test_copilot_no_repeated_hello_on_subsequent_turns(self):
        """Verify copilot does not prepend 'Hello, I am the Sovereign Clinical Copilot' on subsequent turns."""
        history = [
            {"role": "user", "content": "What is the patient allergy profile?"},
            {"role": "assistant", "content": "Patient has a documented allergy to Sulfonamides."}
        ]
        res = ask_copilot(
            message="does the patient has any allery",
            patient_id="PT-101",
            history=history
        )
        reply = res["reply"]
        self.assertFalse(reply.lower().startswith("hello"))
        self.assertFalse(reply.lower().startswith("good morning"))
        self.assertFalse("i'm the sovereign clinical ai copilot" in reply.lower())
        self.assertFalse("i am the sovereign clinical copilot" in reply.lower())

    def test_fuzzy_drug_resolution_citrizen(self):
        """Verify typo 'Citrizen' is resolved to 'Cetirizine' with renal dosage instructions."""
        res = ask_copilot(
            message="Can I give the patient Citrizen tablets?",
            patient_id="PT-101"
        )
        self.assertEqual(res["target_med"], "Cetirizine")
        self.assertEqual(res["detected_drug"], "Cetirizine")
        self.assertTrue("cetirizine" in res["reply"].lower())
        self.assertIn("clinical_badges", res)
        self.assertIn("suggested_actions", res)
        self.assertIn("suggested_followups", res)

    def test_allergy_cross_reactivity_and_typo(self):
        """Verify 'does the patient has any allery' resolves allergy profile with class guardrails."""
        res = ask_copilot(
            message="does the patient has any allery",
            patient_id="PT-101"
        )
        self.assertTrue("sulfonamide" in res["reply"].lower())
        # Followups should be present
        self.assertGreater(len(res["suggested_followups"]), 0)


if __name__ == "__main__":
    unittest.main()
