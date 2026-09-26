"""
MediVault Local — Automated Test Suite for Clinical Analytics Dashboard
Tests aggregation metrics, alert triage distribution, top flagged drugs,
0-byte sovereign egress guarantee, trends time-series, and CSV export.
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app, init_db


class TestClinicalAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_analytics_summary_endpoint(self):
        """Verify GET /api/analytics/summary returns complete metrics structure."""
        response = self.client.get("/api/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check top-level KPI metrics
        self.assertIn("total_reviews", data)
        self.assertIn("flagged_reviews", data)
        self.assertIn("clear_reviews", data)
        self.assertIn("flag_rate_pct", data)
        self.assertIn("estimated_adverse_events_prevented", data)
        self.assertIn("sovereign_egress_bytes", data)
        self.assertIn("cloud_requests_count", data)

        # Strict Sovereign Air-Gap Check
        self.assertEqual(data["sovereign_egress_bytes"], 0)
        self.assertEqual(data["cloud_requests_count"], 0)
        self.assertTrue(data.get("zero_cloud_verified"))

    def test_02_alert_distribution(self):
        """Verify alert distribution matches critical, warning, and safe totals."""
        response = self.client.get("/api/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        alerts = data.get("alert_distribution", {})
        self.assertIn("CRITICAL", alerts)
        self.assertIn("WARNING", alerts)
        self.assertIn("SAFE", alerts)

        total_alerts = alerts["CRITICAL"] + alerts["WARNING"] + alerts["SAFE"]
        self.assertEqual(total_alerts, data["total_reviews"])

    def test_03_top_flagged_drugs_structure(self):
        """Verify top flagged drugs array contains required risk descriptors."""
        response = self.client.get("/api/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        top_drugs = data.get("top_flagged_drugs", [])
        self.assertIsInstance(top_drugs, list)

        if len(top_drugs) > 0:
            drug_entry = top_drugs[0]
            self.assertIn("drug", drug_entry)
            self.assertIn("count", drug_entry)
            self.assertIn("organ_system", drug_entry)
            self.assertIn("severity", drug_entry)
            self.assertIn("primary_risk", drug_entry)

    def test_04_dangerous_combinations_leaderboard(self):
        """Verify dangerous drug combinations leaderboard is populated."""
        response = self.client.get("/api/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        combos = data.get("dangerous_combinations_leaderboard", [])
        self.assertGreater(len(combos), 0)

        # Check Triple Whammy is present
        whammy = next((c for c in combos if "Triple Whammy" in c.get("name", "")), None)
        self.assertIsNotNone(whammy)
        self.assertEqual(whammy.get("severity"), "CRITICAL")
        self.assertIn("mechanism", whammy)
        self.assertIn("safe_alternative", whammy)

    def test_05_analytics_trends_time_series(self):
        """Verify GET /api/analytics/trends returns Chart.js ready datasets."""
        response = self.client.get("/api/analytics/trends?limit=7")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("labels", data)
        self.assertIn("datasets", data)
        datasets = data["datasets"]
        self.assertIn("total_reviews", datasets)
        self.assertIn("flagged_reviews", datasets)
        self.assertIn("sovereign_egress_bytes", datasets)

        # Verify egress line is strictly all zeros
        egress_series = datasets["sovereign_egress_bytes"]
        self.assertTrue(all(val == 0 for val in egress_series))

    def test_06_analytics_csv_export(self):
        """Verify GET /api/analytics/export returns valid CSV stream."""
        response = self.client.get("/api/analytics/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))
        self.assertIn("attachment", response.headers.get("content-disposition", ""))
        self.assertIn("Event ID", response.text)
        self.assertIn("Cryptographic Audit SHA-256", response.text)


if __name__ == "__main__":
    unittest.main()
