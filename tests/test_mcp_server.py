"""
MediVault Local — Automated Test Suite for FastMCP Server (Track 1 Sovereign AI)
Verifies:
1. Model Context Protocol (MCP) server initialization and tool registration.
2. Direct invocation of clinical tools: review_prescription, simulate_pharmacokinetics,
   search_clinical_knowledge, calculate_clinical_hazard, verify_audit_seal.
3. HTTP MCP Gateway endpoints (GET /api/mcp/tools, POST /api/mcp/call).
"""

import json
import unittest
from fastapi.testclient import TestClient

from backend.main import app, init_db
from backend.mcp_server import (
    mcp_server,
    review_prescription,
    simulate_pharmacokinetics,
    search_clinical_knowledge,
    calculate_clinical_hazard,
    verify_audit_seal,
    get_available_tools_list
)


class TestFastMcpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_mcp_server_initialization_and_tool_registration(self):
        """Verify MCP Server metadata and tool declarations."""
        self.assertEqual(mcp_server.name, "medivault-local-cdss")
        tools = get_available_tools_list()
        self.assertGreaterEqual(len(tools), 5)
        names = [t["name"] for t in tools]
        self.assertIn("review_prescription", names)
        self.assertIn("simulate_pharmacokinetics", names)
        self.assertIn("search_clinical_knowledge", names)
        self.assertIn("calculate_clinical_hazard", names)
        self.assertIn("verify_audit_seal", names)

    def test_02_review_prescription_mcp_tool(self):
        """Verify review_prescription MCP tool returns valid structured JSON."""
        res_raw = review_prescription(patient_id="PT-101", proposed_drug="Ibuprofen", enable_slm=False)
        data = json.loads(res_raw)
        self.assertEqual(data.get("status"), "CRITICAL")
        self.assertIn("alerts", data)
        self.assertGreaterEqual(data.get("total_alerts", 0), 1)
        self.assertIn("hazard_index", data)
        self.assertIn("audit_hash", data)

    def test_03_simulate_pk_mcp_tool(self):
        """Verify simulate_pharmacokinetics MCP tool computes clearance curves."""
        res_raw = simulate_pharmacokinetics(drug_name="Ibuprofen", egfr=35.0, dose_mg=400.0, hours=72.0)
        data = json.loads(res_raw)
        self.assertTrue("Ibuprofen" in data.get("drug_name", ""))
        self.assertIn("half_life_normal_hr", data)
        self.assertIn("half_life_patient_hr", data)
        self.assertIn("patient_curve_sample", data)
        # Patient half life should be longer than normal
        self.assertGreater(data["half_life_patient_hr"], data["half_life_normal_hr"])

    def test_04_search_knowledge_mcp_tool(self):
        """Verify search_clinical_knowledge MCP tool retrieves relevant vector monographs."""
        res_raw = search_clinical_knowledge(query="NSAID kidney damage", top_k=2)
        data = json.loads(res_raw)
        self.assertIn("monographs", data)
        self.assertGreaterEqual(data.get("total_found", 0), 1)
        # At least one returned monograph should be an NSAID
        monographs = data["monographs"]
        self.assertTrue(any("NSAID" in m.get("category", "") or "Ketorolac" in m.get("drug", "") or "Ibuprofen" in m.get("drug", "") for m in monographs))

    def test_05_calculate_hazard_mcp_tool(self):
        """Verify calculate_clinical_hazard MCP tool returns composite risk tier."""
        res_raw = calculate_clinical_hazard(patient_id="PT-101", proposed_med="Ibuprofen")
        data = json.loads(res_raw)
        self.assertIn("hazard_index", data)
        hazard = data["hazard_index"]
        self.assertIn("risk_tier", hazard)
        self.assertIn("needle_degrees", hazard)

    def test_06_http_mcp_gateway_list_and_call(self):
        """Verify HTTP REST gateway endpoints /api/mcp/tools and /api/mcp/call."""
        # 1. List tools
        res_list = self.client.get("/api/mcp/tools")
        self.assertEqual(res_list.status_code, 200)
        list_data = res_list.json()
        self.assertTrue(list_data.get("zero_cloud_guarantee"))
        self.assertIn("tools", list_data)

        # 2. Invoke tool via POST /api/mcp/call
        call_payload = {
            "tool_name": "review_prescription",
            "arguments": {
                "patient_id": "PT-101",
                "proposed_drug": "Ibuprofen",
                "enable_slm": False
            }
        }
        res_call = self.client.post("/api/mcp/call", json=call_payload)
        self.assertEqual(res_call.status_code, 200)
        call_data = res_call.json()
        self.assertTrue(call_data.get("success"))
        self.assertEqual(call_data.get("tool"), "review_prescription")
        self.assertEqual(call_data["result"]["status"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()
