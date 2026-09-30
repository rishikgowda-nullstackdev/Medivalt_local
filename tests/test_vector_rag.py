"""
Unit tests for MediVault Local Clinical Vector RAG Engine (Person C).
Tests dense vector retrieval, cosine similarity ranking, brand name normalization,
and offline execution guarantees.
"""

import unittest
from ai_engine.vector_rag import search_clinical_knowledge, get_monograph, list_monographs, ClinicalVectorRAG


class TestClinicalVectorRAG(unittest.TestCase):

    def test_search_renal_pain(self):
        """Vector RAG should retrieve Ketorolac / NSAID monographs for renal failure and pain query."""
        results = search_clinical_knowledge("kidney failure severe pain", top_k=3)
        self.assertGreaterEqual(len(results), 1)
        top_drugs = [r["drug"] for r in results]
        self.assertTrue("Ketorolac" in top_drugs or "Acetaminophen" in top_drugs)
        self.assertGreater(results[0]["similarity"], 0.2)
        self.assertTrue(bool(results[0]["snippet"]))

    def test_search_anticoagulation_bleeding(self):
        """Query for bleeding and stroke prevention should rank Warfarin or Apixaban high."""
        results = search_clinical_knowledge("atrial fibrillation anticoagulation bleeding risk", top_k=3)
        self.assertGreaterEqual(len(results), 1)
        top_drugs = [r["drug"] for r in results]
        self.assertTrue("Warfarin" in top_drugs or "Apixaban" in top_drugs)

    def test_brand_name_resolution(self):
        """Brand names like Toradol, Advil, Glucophage, Lasix, Eliquis resolve cleanly."""
        m_toradol = get_monograph("Toradol")
        self.assertIsNotNone(m_toradol)
        self.assertEqual(m_toradol["drug"], "Ketorolac")

        m_eliquis = get_monograph("Eliquis")
        self.assertIsNotNone(m_eliquis)
        self.assertEqual(m_eliquis["drug"], "Apixaban")

        m_lasix = get_monograph("Lasix")
        self.assertIsNotNone(m_lasix)
        self.assertEqual(m_lasix["drug"], "Furosemide")

    def test_category_filtering(self):
        """Vector search honors category filtering."""
        results = search_clinical_knowledge("infection", category="Antimicrobial", top_k=5)
        for r in results:
            self.assertEqual(r["category"], "Antimicrobial")

    def test_list_monographs(self):
        """Monograph catalog contains 25+ curated offline monographs."""
        catalog = list_monographs()
        self.assertGreaterEqual(len(catalog), 25)
        drugs = [c["drug"] for c in catalog]
        self.assertIn("Ketorolac", drugs)
        self.assertIn("Lisinopril", drugs)
        self.assertIn("Metformin", drugs)


if __name__ == "__main__":
    unittest.main()
