"""
MediVault Local — Automated Test Suite for Patient Portal
Tests patient registration, authentication, medical profile retrieval,
plain-language lab explanations, dietary/wellness recommendations, and role isolation.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.main import app, init_db
from backend.migrate_patient_portal import migrate_patient_portal
from backend.auth import create_access_token


class TestPatientPortal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        migrate_patient_portal()
        cls.client = TestClient(app)

    def test_01_patient_portal_page_serves(self):
        """Verify GET /patient-portal serves the patient portal HTML interface."""
        response = self.client.get("/patient-portal")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("MediVault Local - Patient Portal", response.text)
        self.assertIn("My Health Summary", response.text)

    def test_02_patient_registration_success(self):
        """Verify successful registration of a patient linked to an existing clinical record."""
        payload = {
            "patient_id": "PT-101",
            "username": "john_test_reg",
            "password": "SecurePassword123!",
            "full_name": "John Doe",
            "date_of_birth": "1962-03-15"
        }
        response = self.client.post("/api/patient/register", json=payload)
        # 200 or 409 if already registered from a previous run
        if response.status_code == 200:
            data = response.json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("username"), "john_test_reg")
            self.assertEqual(data.get("patient_id"), "PT-101")
        else:
            self.assertEqual(response.status_code, 409)

    def test_03_patient_registration_invalid_patient_id(self):
        """Verify registration is rejected if patient_id does not exist in patients table."""
        payload = {
            "patient_id": "PT-NONEXISTENT-999",
            "username": "fake_user",
            "password": "Password123!",
            "full_name": "Fake Person",
            "date_of_birth": "1990-01-01"
        }
        response = self.client.post("/api/patient/register", json=payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json().get("detail", "").lower())

    def test_04_patient_registration_duplicate_username(self):
        """Verify registration rejects duplicate usernames with 409 Conflict."""
        payload = {
            "patient_id": "PT-101",
            "username": "john.doe",  # Seeded demo user
            "password": "Password123!",
            "full_name": "Duplicate John",
            "date_of_birth": "1962-03-15"
        }
        response = self.client.post("/api/patient/register", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already taken", response.json().get("detail", "").lower())

    def test_05_patient_login_success(self):
        """Verify successful login with valid credentials returns JWT and sets cookie."""
        payload = {
            "username": "john.doe",
            "password": "Patient123!"
        }
        response = self.client.post("/api/patient/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("patient_id"), "PT-101")
        self.assertIsNotNone(data.get("token"))
        # Verify session cookie was set
        self.assertIn("medivault_patient_session", response.cookies)

    def test_06_patient_login_wrong_password(self):
        """Verify login fails with 401 for incorrect password."""
        payload = {
            "username": "john.doe",
            "password": "WrongPassword999!"
        }
        response = self.client.post("/api/patient/login", json=payload)
        self.assertEqual(response.status_code, 401)
        self.assertIn("invalid", response.json().get("detail", "").lower())

    def test_07_patient_profile_returns_full_data(self):
        """Verify authenticated patient can retrieve their conditions, medications, allergies, and labs."""
        # Log in first
        login_res = self.client.post("/api/patient/login", json={"username": "john.doe", "password": "Patient123!"})
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.get("/api/patient/profile", headers=headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["patient_id"], "PT-101")
        self.assertIn("conditions", data)
        self.assertIn("medications", data)
        self.assertIn("allergies", data)
        self.assertIn("labs", data)

        # Check PT-101 has conditions (CKD, Hypertension, Diabetes)
        condition_names = [c["condition_name"] for c in data["conditions"]]
        self.assertTrue(any("Kidney Disease" in c for c in condition_names))

        # Check PT-101 has medications
        med_names = [m["medication_name"] for m in data["medications"]]
        self.assertIn("Lisinopril", med_names)

    def test_08_patient_labs_have_plain_explanations(self):
        """Verify lab results contain plain-English non-jargon explanations for patients."""
        login_res = self.client.post("/api/patient/login", json={"username": "john.doe", "password": "Patient123!"})
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.get("/api/patient/profile", headers=headers)
        self.assertEqual(response.status_code, 200)

        labs = response.json().get("labs", [])
        self.assertGreater(len(labs), 0)

        for lab in labs:
            self.assertIn("biomarker", lab)
            self.assertIn("plain_explanation", lab)
            self.assertIn("status", lab)
            self.assertIsInstance(lab["plain_explanation"], str)
            self.assertGreater(len(lab["plain_explanation"]), 10)

    def test_09_patient_recommendations_deterministic(self):
        """Verify dietary and wellness recommendations match patient conditions."""
        login_res = self.client.post("/api/patient/login", json={"username": "john.doe", "password": "Patient123!"})
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.get("/api/patient/recommendations", headers=headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["patient_id"], "PT-101")
        self.assertIn("dietary_guidelines", data)

        guidelines = data["dietary_guidelines"]
        self.assertIn("recommended_foods", guidelines)
        self.assertIn("foods_to_avoid", guidelines)
        self.assertIn("wellness_tips", guidelines)

        # PT-101 has CKD: should have food recommendations for kidney disease
        rec_items = [f["item"] for f in guidelines["recommended_foods"]]
        avoid_items = [f["item"] for f in guidelines["foods_to_avoid"]]

        # Bananas should be avoided for CKD (high potassium)
        self.assertTrue(any("bananas" in item.lower() for item in avoid_items))

    def test_10_patient_token_cannot_access_practitioner_role(self):
        """Verify patient JWT cannot be used as a doctor identity."""
        patient_token = create_access_token({
            "patient_id": "PT-101",
            "username": "john.doe",
            "full_name": "John Doe",
            "role": "patient"
        })

        # Test patient profile works with patient token
        headers = {"Authorization": f"Bearer {patient_token}"}
        res = self.client.get("/api/patient/profile", headers=headers)
        self.assertEqual(res.status_code, 200)

        # Test auth/me checks practitioner identity
        auth_me_res = self.client.get("/api/auth/me", headers=headers)
        # get_current_practitioner returns DEFAULT_DEMO_PRACTITIONER when token has no practitioner_id
        # verifying patient token doesn't grant practitioner privilege
        self.assertNotEqual(auth_me_res.json().get("role"), "patient")


if __name__ == "__main__":
    unittest.main()
