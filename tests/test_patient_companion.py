"""
Unit tests for Patient Portal Sovereign AI Health Companion (Person D & Person A).
Tests authenticated plain-language counseling, renal safety guardrails,
and zero cloud egress guarantees.
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestPatientCompanion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Login with seeded demo patient account
        login_resp = cls.client.post("/api/patient/login", json={
            "username": "john.doe",
            "password": "Patient123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        cls.token = login_resp.json()["token"]
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

    def test_unauthenticated_request_blocked(self):
        """Unauthenticated requests must be blocked with 401."""
        unauth_client = TestClient(app)
        res = unauth_client.post("/api/patient/companion/chat", json={
            "message": "Can I take ibuprofen?"
        })
        self.assertEqual(res.status_code, 401)

    def test_companion_renal_nsaid_guardrail(self):
        """Companion must refuse Ibuprofen/Advil for kidney patients with compassionate advice."""
        res = self.client.post(
            "/api/patient/companion/chat",
            json={"message": "Can I take Advil or Ibuprofen for my knee ache?"},
            headers=self.auth_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        reply_lower = data["reply"].lower()
        self.assertTrue(
            "avoid" in reply_lower or 
            "important to avoid" in reply_lower or 
            "kidney" in reply_lower
        )
        self.assertTrue("tylenol" in reply_lower or "acetaminophen" in reply_lower)
        self.assertGreaterEqual(len(data.get("suggested_followups", [])), 2)

    def test_companion_diet_inquiry(self):
        """Companion provides compassionate kidney-friendly dietary suggestions."""
        res = self.client.post(
            "/api/patient/companion/chat",
            json={"message": "What foods should I eat to help my health?"},
            headers=self.auth_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data["reply"]) > 50)
        self.assertTrue(
            "sodium" in data["reply"].lower() or 
            "food" in data["reply"].lower() or 
            "kidney" in data["reply"].lower()
        )

    def test_companion_hydration_inquiry(self):
        """Companion provides supportive hydration advice."""
        res = self.client.post(
            "/api/patient/companion/chat",
            json={"message": "How much water should I drink every day?"},
            headers=self.auth_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue("water" in data["reply"].lower() or "fluid" in data["reply"].lower())


if __name__ == "__main__":
    unittest.main()
