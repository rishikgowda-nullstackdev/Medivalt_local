"""
MediVault Local - Multi-Drug Polypharmacy Matrix Test Suite
Verifies:
1. "The Triple Whammy" (ACEi/ARB + Diuretic + NSAID) detection.
2. Cumulative QTc Prolongation risk scoring.
3. Cumulative Serotonin Syndrome risk detection.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine.polypharmacy import PolypharmacyEngine


class TestPolypharmacyMatrix(unittest.TestCase):

    def test_01_triple_whammy_lisinopril_furosemide_ibuprofen(self):
        """Lisinopril (ACEi) + Furosemide (Diuretic) + proposed Ibuprofen (NSAID) must flag TRIPLE_WHAMMY."""
        active_meds = ["Lisinopril 20mg", "Furosemide 40mg"]
        proposed = "Ibuprofen 400mg"

        alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed, active_meds)
        self.assertGreaterEqual(len(alerts), 1)

        triple_alerts = [a for a in alerts if a.get("rule_id") == "TRIPLE_WHAMMY"]
        self.assertEqual(len(triple_alerts), 1)
        self.assertEqual(triple_alerts[0]["severity"], "CRITICAL")
        self.assertIn("acute ischemic renal failure", triple_alerts[0]["clinical_mechanism"].lower())

    def test_02_triple_whammy_losartan_hydrochlorothiazide_naproxen(self):
        """Losartan (ARB) + Hydrochlorothiazide (Diuretic) + proposed Naproxen (NSAID) must flag TRIPLE_WHAMMY."""
        active_meds = ["Cozaar 50mg", "Hydrochlorothiazide 25mg"]
        proposed = "Aleve 220mg"

        alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed, active_meds)
        triple_alerts = [a for a in alerts if a.get("rule_id") == "TRIPLE_WHAMMY"]
        self.assertEqual(len(triple_alerts), 1)
        self.assertEqual(triple_alerts[0]["severity"], "CRITICAL")

    def test_03_no_triple_whammy_without_nsaid(self):
        """ACEi + Diuretic + non-NSAID (Acetaminophen) must NOT trigger Triple Whammy."""
        active_meds = ["Lisinopril 20mg", "Furosemide 40mg"]
        proposed = "Acetaminophen 500mg"

        alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed, active_meds)
        triple_alerts = [a for a in alerts if a.get("rule_id") == "TRIPLE_WHAMMY"]
        self.assertEqual(len(triple_alerts), 0)

    def test_04_cumulative_qtc_prolongation(self):
        """Amiodarone + Ondansetron + proposed Azithromycin must trigger QTc Prolongation alert."""
        active_meds = ["Amiodarone 200mg", "Zofran 8mg"]
        proposed = "Azithromycin 500mg"

        alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed, active_meds)
        qt_alerts = [a for a in alerts if a.get("rule_id") == "QTC_PROLONGATION_HIGH"]
        self.assertEqual(len(qt_alerts), 1)
        self.assertEqual(qt_alerts[0]["severity"], "CRITICAL")
        self.assertIn("torsades de pointes", qt_alerts[0]["clinical_mechanism"].lower())

    def test_05_cumulative_serotonin_syndrome(self):
        """Sertraline + Linezolid + proposed Tramadol must trigger Serotonin Syndrome alert."""
        active_meds = ["Zoloft 100mg", "Zyvox 600mg"]
        proposed = "Tramadol 50mg"

        alerts = PolypharmacyEngine.evaluate_polypharmacy(proposed, active_meds)
        serotonin_alerts = [a for a in alerts if a.get("rule_id") == "SEROTONIN_SYNDROME_COMBO"]
        self.assertEqual(len(serotonin_alerts), 1)
        self.assertEqual(serotonin_alerts[0]["severity"], "CRITICAL")
        self.assertIn("serotonin", serotonin_alerts[0]["clinical_mechanism"].lower())


if __name__ == "__main__":
    unittest.main()
