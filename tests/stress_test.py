"""
MediVault Local - Day 6 Concurrency & Stress Test Suite
Simulates rapid concurrent physician clinical reviews to test thread-safety,
SQLite WAL concurrency, and cryptographic SHA-256 audit chain resilience.
"""

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.audit_logger import audit_logger


class TestMediVaultDay6Concurrency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_concurrent_reviews_and_audit_integrity(self):
        """
        Simulate 12 concurrent clinical reviews across different patient profiles.
        Verifies:
        1. Zero locked-database errors (SQLite WAL mode).
        2. 100% accurate triage statuses under concurrent load.
        3. Cryptographic SHA-256 audit chain remains unbroken and completely valid.
        """
        test_requests = [
            {"patient_id": "PT-101", "proposed_medication": "Ibuprofen 400mg", "expected": "CRITICAL"},
            {"patient_id": "PT-102", "proposed_medication": "Propranolol 40mg", "expected": "CRITICAL"},
            {"patient_id": "PT-103", "proposed_medication": "Aspirin 81mg", "expected": "CRITICAL"},
            {"patient_id": "PT-101", "proposed_medication": "Amoxicillin 500mg", "expected": "SAFE"},
            {"patient_id": "PT-101", "proposed_medication": "Advil 400mg", "expected": "CRITICAL"},
            {"patient_id": "PT-102", "proposed_medication": "Amlodipine 5mg", "expected": "SAFE"},
            {"patient_id": "PT-103", "proposed_medication": "Ibuprofen 400mg", "expected": "CRITICAL"},
            {"patient_id": "PT-101", "proposed_medication": "Naproxen 250mg", "expected": "CRITICAL"},
            {"patient_id": "PT-102", "proposed_medication": "Timolol 0.5%", "expected": "CRITICAL"},
            {"patient_id": "PT-101", "proposed_medication": "Acetaminophen 500mg", "expected": "SAFE"},
            {"patient_id": "PT-103", "proposed_medication": "Codeine 30mg", "expected": "CRITICAL"},
            {"patient_id": "PT-102", "proposed_medication": "Fluticasone 110mcg", "expected": "SAFE"}
        ]

        results = []

        def execute_review(req):
            res = self.client.post("/api/review", json={
                "patient_id": req["patient_id"],
                "proposed_medication": req["proposed_medication"]
            })
            return req, res

        # Run with 6 concurrent worker threads
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_req = {executor.submit(execute_review, r): r for r in test_requests}
            for future in as_completed(future_to_req):
                req, response = future.result()
                self.assertEqual(response.status_code, 200, f"Failed for {req['proposed_medication']}: {response.text}")
                data = response.json()
                self.assertEqual(
                    data["overall_status"],
                    req["expected"],
                    f"Mismatch for {req['proposed_medication']}: got {data['overall_status']}, expected {req['expected']}"
                )
                self.assertTrue(data["zero_cloud_verified"])
                results.append(data)

        self.assertEqual(len(results), len(test_requests))

        # CRITICAL TEST: Mathematically verify that the SHA-256 hash chain is 100% valid!
        integrity = audit_logger.verify_integrity()
        self.assertTrue(
            integrity["valid"],
            f"Audit integrity compromised under concurrency: {integrity.get('error')}"
        )
        self.assertEqual(integrity["status"], "ALL_BLOCKS_VALID_TAMPER_FREE")
        self.assertGreaterEqual(integrity["total_blocks"], len(test_requests))


if __name__ == "__main__":
    unittest.main()
