import json
import unittest
from claim_verification import verify_interpretation


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, verdict):
        self.verdict = verdict

    def invoke(self, prompt):
        self.prompt = prompt
        return FakeResponse(self.verdict)


def llm_with(summary, impact):
    return FakeLLM(json.dumps({
        "summary": {"status": summary, "reason": "Checked against evidence"},
        "impact": {"status": impact, "reason": "Checked against evidence"},
    }))


class ClaimVerificationTests(unittest.TestCase):
    def test_supported_claims(self):
        llm = llm_with("supported", "supported")
        result = verify_interpretation("INR 2,000", "INR 3,500",
            {"summary": "Limit rose", "impact": "Higher reimbursement cap"}, llm)
        self.assertEqual(result["status"], "supported")
        self.assertTrue(result["review_required"])
        self.assertIn("INR 2,000", llm.prompt)

    def test_unsupported_impact_is_flagged(self):
        result = verify_interpretation("Hotel reimbursement INR 2,000",
            "Hotel reimbursement INR 3,500",
            {"summary": "Reimbursement cap rose",
             "impact": "Employees will pay INR 1,500 more"},
            llm_with("supported", "unsupported"))
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["claims"]["impact"]["status"], "unsupported")

    def test_uncertain_claim(self):
        result = verify_interpretation("Approval above INR 5,000",
            "Approval above INR 10,000",
            {"summary": "Threshold rose", "impact": "All lower amounts are exempt"},
            llm_with("supported", "uncertain"))
        self.assertEqual(result["status"], "uncertain")

    def test_malformed_response_fails_closed(self):
        result = verify_interpretation("before", "after",
            {"summary": "A change", "impact": "An impact"}, FakeLLM("not json"))
        self.assertEqual(result["status"], "unverified")

    def test_partial_verdict_fails_closed(self):
        result = verify_interpretation("before", "after",
            {"summary": "A change", "impact": "An impact"},
            FakeLLM('{"summary":{"status":"supported","reason":"ok"}}'))
        self.assertEqual(result["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
