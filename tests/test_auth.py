"""
MediVault Local - Sovereign Authentication & Email Verification Test Suite
Verifies:
1. PBKDF2-HMAC-SHA256 password hashing & salt uniqueness.
2. Offline HMAC-SHA256 JWT tokens with tamper resistance.
3. Hospital email domain whitelisting.
4. Cryptographic 6-digit OTP generation and sovereign outbox logging.
5. Blocking unverified accounts (HIPAA § 164.312(a)(2)(iv)).
6. Account activation via OTP verification.
7. Prescription review attribution to authenticated doctor and hospital in SHA-256 audit ledger.
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    validate_hospital_domain,
    generate_otp
)
from backend.audit_logger import audit_logger


class TestMediVaultAuthentication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_password_hashing(self):
        """Verify PBKDF2-HMAC-SHA256 salt uniqueness and verification."""
        pwd = "HospitalSafe123!"
        salt1, hash1 = hash_password(pwd)
        salt2, hash2 = hash_password(pwd)

        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(hash1, hash2)
        self.assertTrue(verify_password(pwd, salt1, hash1))
        self.assertFalse(verify_password("WrongPassword!", salt1, hash1))

    def test_02_offline_token_generation_and_tampering(self):
        """Verify offline compact JWT token generation, decoding, and signature tampering."""
        data = {"practitioner_id": "PRAC-TEST", "email": "test@stjude.org"}
        token = create_access_token(data, expires_minutes=60)
        self.assertEqual(token.count("."), 2)

        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["practitioner_id"], "PRAC-TEST")

        # Tampered signature
        tampered_token = token[:-4] + "XXXX"
        self.assertIsNone(decode_access_token(tampered_token))

    def test_03_hospital_domain_validation(self):
        """Verify hospital email domain whitelist rules."""
        # Valid domain
        ok1, _ = validate_hospital_domain("dr.watson@stjude.org", "stjude.org")
        self.assertTrue(ok1)

        # Subdomain of valid domain
        ok2, _ = validate_hospital_domain("dr.smith@cardio.stjude.org", "stjude.org")
        self.assertTrue(ok2)

        # Mismatched domain
        bad1, msg1 = validate_hospital_domain("dr.hacker@gmail.com", "stjude.org")
        self.assertFalse(bad1)
        self.assertIn("mismatch", msg1.lower())

        # Invalid email format
        bad2, _ = validate_hospital_domain("not-an-email", "stjude.org")
        self.assertFalse(bad2)

    def test_04_hospital_list_endpoint(self):
        """Verify GET /api/auth/hospitals returns registered institutions."""
        res = self.client.get("/api/auth/hospitals")
        self.assertEqual(res.status_code, 200)
        hospitals = res.json()["hospitals"]
        self.assertGreaterEqual(len(hospitals), 3)
        names = [h["hospital_name"] for h in hospitals]
        self.assertIn("Metro General Hospital", names)
        self.assertIn("St. Jude Medical Center", names)

    def test_05_registration_and_email_verification_flow(self):
        """
        Verify end-to-end flow:
        Register -> OTP Dispatched -> Login Blocked (403) -> Verify OTP -> Login Success -> Audit Attribution
        """
        unique_email = f"dr.sujan.{int(datetime.now().timestamp())}@metrogeneral.org"
        reg_payload = {
            "full_name": "Dr. Sujan MB",
            "email": unique_email,
            "hospital_id": "HOSP-01",
            "medical_license": "NPI-5566778899",
            "password": "ClinicPassword123!"
        }

        # 1. Register
        r_reg = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(r_reg.status_code, 200)
        data_reg = r_reg.json()
        self.assertEqual(data_reg["status"], "PENDING_VERIFICATION")
        otp = data_reg["simulated_code"]
        self.assertEqual(len(otp), 6)

        # 2. Login before verification must be blocked (403)
        r_blocked = self.client.post("/api/auth/login", json={
            "email": unique_email,
            "password": "ClinicPassword123!"
        })
        self.assertEqual(r_blocked.status_code, 403)
        self.assertIn("not yet verified", r_blocked.json()["detail"].lower())

        # 3. Wrong OTP must fail (400)
        r_bad_otp = self.client.post("/api/auth/verify-email", json={
            "email": unique_email,
            "verification_code": "000000"
        })
        self.assertEqual(r_bad_otp.status_code, 400)

        # 4. Correct OTP verifies and activates account
        r_verify = self.client.post("/api/auth/verify-email", json={
            "email": unique_email,
            "verification_code": otp
        })
        self.assertEqual(r_verify.status_code, 200)
        token = r_verify.json()["access_token"]
        self.assertIsNotNone(token)
        self.assertEqual(r_verify.json()["practitioner"]["full_name"], "Dr. Sujan MB")

        # 5. Login succeeds after verification
        r_login = self.client.post("/api/auth/login", json={
            "email": unique_email,
            "password": "ClinicPassword123!"
        })
        self.assertEqual(r_login.status_code, 200)
        self.assertEqual(r_login.json()["status"], "SUCCESS")

        # 6. Prescription review with authenticated doctor binds doctor to audit log
        r_review = self.client.post(
            "/api/review",
            json={"patient_id": "PT-101", "proposed_medication": "Ibuprofen 400mg"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(r_review.status_code, 200)
        review_data = r_review.json()
        self.assertEqual(review_data["practitioner_name"], "Dr. Sujan MB")
        self.assertEqual(review_data["hospital_name"], "Metro General Hospital")

        # 7. Audit hash chain integrity check mathematically passes
        integrity = audit_logger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["status"], "ALL_BLOCKS_VALID_TAMPER_FREE")

    def test_06_preseeded_demo_physician_login(self):
        """Verify pre-seeded demo physicians can log in with default hospital credentials."""
        r_login = self.client.post("/api/auth/login", json={
            "email": "dr.house@princeton.edu",
            "password": "HospitalPass123!"
        })
        self.assertEqual(r_login.status_code, 200)
        data = r_login.json()
        self.assertEqual(data["practitioner"]["full_name"], "Dr. Gregory House, MD")
        self.assertEqual(data["practitioner"]["hospital_name"], "Princeton Plainsboro Teaching Hospital")

    def test_07_demo_switcher(self):
        """Verify 1-click switcher between demo doctors for hackathon evaluations."""
        r_switch = self.client.post("/api/auth/switch-demo", json={"practitioner_id": "PRAC-101"})
        self.assertEqual(r_switch.status_code, 200)
        self.assertEqual(r_switch.json()["practitioner"]["full_name"], "Dr. Sarah Jenkins, MD")


if __name__ == "__main__":
    unittest.main()
