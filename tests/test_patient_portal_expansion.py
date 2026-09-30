"""
MediVault Local — Automated Test Suite for Patient Portal Expansion
Tests:
1. Direct URL aliases (/portal, /patient, /patient-portal)
2. Physician advice publishing (POST /api/patient/advice)
3. Patient advice inbox retrieval & unread counts (GET /api/patient/advice)
4. Directive acknowledgment (POST /api/patient/advice/{id}/read)
5. Offline SLM / Deterministic plain-language drafter (POST /api/patient/advice/draft-slm)
6. Plain-English medication safety leaflets (GET /api/patient/medication-guides)
7. Daily medication adherence schedule and tracking (GET /api/patient/adherence & POST /api/patient/adherence/log)
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app, init_db
from backend.migrate_patient_portal import migrate_patient_portal
from backend.auth import create_access_token


class TestPatientPortalExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        migrate_patient_portal()
        cls.client = TestClient(app)

        # Generate a valid patient token for PT-101
        cls.patient_token = create_access_token(data={
            "sub": "PT-101",
            "username": "john.doe",
            "role": "patient",
            "patient_id": "PT-101"
        })
        cls.patient_headers = {
            "Authorization": f"Bearer {cls.patient_token}"
        }

        # Generate a valid physician token
        cls.physician_token = create_access_token(data={
            "sub": "DOC-HOUSE",
            "username": "dr.house",
            "role": "PHYSICIAN",
            "name": "Dr. Gregory House, MD"
        })
        cls.physician_headers = {
            "Authorization": f"Bearer {cls.physician_token}"
        }

    def test_01_direct_url_aliases(self):
        """Verify direct routes /portal and /patient serve the patient portal HTML interface."""
        for path in ["/portal", "/patient", "/patient-portal"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Failed for path {path}")
            self.assertIn("text/html", res.headers.get("content-type", ""))
            self.assertIn("Daily Medication Adherence Schedule", res.text)
            self.assertIn("Emergency Medical ID Pass", res.text)
            self.assertIn("Doctor's Care Instructions", res.text)

    def test_02_draft_plain_language_advice_slm(self):
        """Verify POST /api/patient/advice/draft-slm translates clinical notes into empathetic 6th-grade language."""
        payload = {
            "clinical_notes": "Patient has eGFR of 38 mL/min (CKD stage 3b). Discontinue all NSAID therapy (ibuprofen, meloxicam). Prescribe acetaminophen PRN max 2000mg/day.",
            "patient_id": "PT-101",
            "category": "MEDICATION"
        }
        res = self.client.post("/api/patient/advice/draft-slm", json=payload, headers=self.physician_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("plain_summary", data)
        self.assertIn("model", data)
        self.assertTrue(len(data["plain_summary"]) > 20)
        # Should translate or mention kidney or pain reliever
        summary_lower = data["plain_summary"].lower()
        self.assertTrue("kidney" in summary_lower or "pain" in summary_lower or "medicine" in summary_lower or "care" in summary_lower)

    def test_03_physician_publishes_advice(self):
        """Verify physician can publish clinical advice to patient PT-101."""
        payload = {
            "patient_id": "PT-101",
            "category": "MEDICATION",
            "advice_text": "Do not take over-the-counter Advil or Aleve. Take Tylenol instead for headaches.",
            "plain_summary": "Please do not take Advil, Aleve, or Ibuprofen because they can hurt your kidneys. Use Tylenol if you have pain.",
            "severity": "CRITICAL",
            "practitioner_name": "Dr. Gregory House, MD",
            "hospital_name": "Princeton Plainsboro Hospital"
        }
        res = self.client.post("/api/patient/advice", json=payload, headers=self.physician_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("advice_id", data)
        self.__class__.created_advice_id = data["advice_id"]

    def test_04_patient_retrieves_advice_inbox(self):
        """Verify patient can fetch physician advice directives with unread count."""
        res = self.client.get("/api/patient/advice", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("patient_id"), "PT-101")
        self.assertIn("advice", data)
        self.assertTrue(data.get("unread_count", 0) >= 1)
        self.assertTrue(len(data["advice"]) >= 1)

        # Check our created advice exists in the list
        advice_ids = [a["id"] for a in data["advice"]]
        self.assertIn(getattr(self.__class__, "created_advice_id", None), advice_ids)

    def test_05_patient_acknowledges_advice(self):
        """Verify patient can mark a physician advice directive as read."""
        advice_id = getattr(self.__class__, "created_advice_id", None)
        self.assertIsNotNone(advice_id)

        res = self.client.post(f"/api/patient/advice/{advice_id}/read", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("advice_id"), advice_id)

        # Refetch and check read status is true (1)
        fetch_res = self.client.get("/api/patient/advice", headers=self.patient_headers)
        fetch_data = fetch_res.json()
        matched = [a for a in fetch_data["advice"] if a["id"] == advice_id]
        self.assertTrue(len(matched) > 0)
        self.assertTrue(bool(matched[0]["is_read"]))

    def test_06_medication_guides_endpoint(self):
        """Verify GET /api/patient/medication-guides returns curated plain-English leaflets."""
        res = self.client.get("/api/patient/medication-guides", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("guides", data)
        self.assertIn("library", data)
        guides = data["guides"]
        library = data["library"]

        # Verify patient's active medications have guides
        guide_names = [g["medication_name"].lower() for g in guides]
        self.assertTrue(any("lisinopril" in name for name in guide_names))
        self.assertTrue(any("metformin" in name for name in guide_names))

        # Verify library contains offline drug leaflets with safety details
        for expected_drug in ["lisinopril", "metformin", "amlodipine", "warfarin"]:
            self.assertIn(expected_drug, library, f"Missing safety guide for {expected_drug}")
            guide = library[expected_drug]
            self.assertIn("why_prescribed", guide)
            self.assertIn("how_to_take", guide)
            self.assertIn("missed_dose", guide)
            self.assertIn("cautions", guide)
            self.assertIn("warning_signs", guide)

    def test_07_daily_medication_adherence_tracking(self):
        """Verify daily medication adherence schedule and streak tracking."""
        res = self.client.get("/api/patient/adherence", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("patient_id"), "PT-101")
        self.assertIn("slots", data)
        self.assertIn("streak_days", data)
        self.assertIn("completion_percentage", data)

        slots = data["slots"]
        self.assertIn("MORNING", slots)
        self.assertIn("AFTERNOON", slots)
        self.assertIn("EVENING", slots)

        # Verify Lisinopril is in MORNING slot
        morning_meds = [m["medication_name"] for m in slots["MORNING"]]
        self.assertTrue(any("Lisinopril" in m for m in morning_meds))

    def test_08_log_medication_adherence(self):
        """Verify patient can log/toggle medication adherence."""
        # 1. Mark Lisinopril as taken
        log_payload = {
            "time_slot": "MORNING",
            "medication_name": "Lisinopril",
            "taken": True
        }
        res = self.client.post("/api/patient/adherence/log", json=log_payload, headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("taken"))

        # Verify in GET
        fetch_res = self.client.get("/api/patient/adherence", headers=self.patient_headers)
        fetch_data = fetch_res.json()
        morning_slot = fetch_data["slots"]["MORNING"]
        lisinopril = next(m for m in morning_slot if "Lisinopril" in m["medication_name"])
        self.assertTrue(lisinopril["taken"])
        self.assertTrue(fetch_data["taken_count"] >= 1)

        # 2. Toggle back to False
        log_payload["taken"] = False
        res2 = self.client.post("/api/patient/adherence/log", json=log_payload, headers=self.patient_headers)
        self.assertEqual(res2.status_code, 200)

        # Verify unmarking
        fetch_res2 = self.client.get("/api/patient/adherence", headers=self.patient_headers)
        fetch_data2 = fetch_res2.json()
        morning_slot2 = fetch_data2["slots"]["MORNING"]
        lisinopril2 = next(m for m in morning_slot2 if "Lisinopril" in m["medication_name"])
        self.assertFalse(lisinopril2["taken"])


if __name__ == "__main__":
    unittest.main()
