import unittest
from version_compare import compare_versions

class VersionComparisonTests(unittest.TestCase):
    def doc(self, content):
        return {"document": {"filename": "policy.pdf", "policy_key": "travel"},
                "chunks": [{"page": 2, "content": content}]}

    def test_changed_policy_limit_has_page_evidence(self):
        old = self.doc("Hotel reimbursement limit is 2000 rupees per night.")
        new = self.doc("Hotel reimbursement limit is 3500 rupees per night.")
        result = compare_versions(old, new)
        self.assertEqual(result["changes"][0]["type"], "modified")
        self.assertEqual(result["changes"][0]["before"][0]["page"], 2)
        self.assertIn("3500", result["changes"][0]["after"][0]["text"])

    def test_identical_documents(self):
        doc = self.doc("Hotel reimbursement limit is 2000 rupees per night.")
        self.assertEqual(compare_versions(doc, doc)["changes"], [])

    def test_added_clause(self):
        old = self.doc("Hotel reimbursement limit is 2000 rupees per night.")
        new = self.doc("Hotel reimbursement limit is 2000 rupees per night. Manager approval is required.")
        self.assertEqual(compare_versions(old, new)["changes"][0]["type"], "added")

if __name__ == "__main__":
    unittest.main()
