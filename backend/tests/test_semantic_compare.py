import unittest
from semantic_compare import _numeric_change, _surrounding_context, analyze_policy_changes


class FakeResponse:
    content = '{"summary":"Limit increased","category":"financial","impact":"Higher reimbursement","uncertainty":""}'


class FakeLLM:
    def invoke(self, prompt):
        return FakeResponse()


def doc(text, version):
    return {"document": {"id": version, "status": "ready", "policy_key": "travel", "version_label": version},
            "chunks": [{"page": 1, "content": text}]}


class SemanticComparisonTests(unittest.TestCase):
    def test_context_preserves_section_heading(self):
        document = doc("2.1 Hotel reimbursement\\nINR 2,000 per night", "v1")
        evidence = [{"page": 1, "text": "INR 2,000 per night"}]
        context = _surrounding_context(document, evidence)
        self.assertIn("Hotel reimbursement", context)
        self.assertIn("INR 2,000 per night", context)

    def test_numeric_delta(self):
        result = _numeric_change("INR 2,000 per night", "INR 3,500 per night")
        self.assertEqual(result["delta_inr"], 1500)
        self.assertEqual(result["percent_change"], 75)

    def test_evidence_and_interpretation(self):
        old = doc("Hotel allowance INR 2,000 per night.", "v1")
        new = doc("Hotel allowance INR 3,500 per night.", "v2")
        result = analyze_policy_changes(old, new, FakeLLM())
        self.assertEqual(result["change_count"], 1)
        change = result["changes"][0]
        self.assertEqual(change["before"][0]["page"], 1)
        self.assertEqual(change["after"][0]["page"], 1)
        self.assertEqual(change["interpretation"]["category"], "financial")
        self.assertTrue(change["review_required"])


if __name__ == "__main__":
    unittest.main()
