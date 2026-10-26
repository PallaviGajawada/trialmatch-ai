"""Unit tests for Person 1's eligibility coordinator (src.agents.coordinator)."""

import unittest

from src.agents.coordinator import evaluate_eligibility


class TestPerson1Coordinator(unittest.TestCase):

    def test_all_criteria_pass(self):
        results = [
            {"agent": "age_agent", "status": "PASS"},
            {"agent": "diagnosis_agent", "status": "PASS"},
            {"agent": "lab_agent", "status": "PASS"},
        ]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Potential match")

    def test_one_criterion_fails(self):
        results = [
            {"agent": "age_agent", "status": "FAIL"},
            {"agent": "diagnosis_agent", "status": "PASS"},
        ]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Not a match")

    def test_unknown_requires_review(self):
        results = [
            {"agent": "age_agent", "status": "PASS"},
            {"agent": "diagnosis_agent", "status": "UNKNOWN"},
        ]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Requires review")

    def test_not_applicable_is_neutral(self):
        results = [
            {"agent": "age_agent", "status": "NOT_APPLICABLE"},
            {"agent": "diagnosis_agent", "status": "PASS"},
        ]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Potential match")

    def test_empty_results_require_review(self):
        result = evaluate_eligibility("P1", "T1", [])

        self.assertEqual(result["status"], "Requires review")

    def test_only_not_applicable_requires_review(self):
        results = [{"agent": "age_agent", "status": "NOT_APPLICABLE"}]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Requires review")

    def test_invalid_status_requires_review(self):
        results = [{"agent": "age_agent", "status": "MAYBE"}]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["status"], "Requires review")

    def test_original_results_are_preserved(self):
        results = [{"agent": "age_agent", "status": "PASS"}]

        result = evaluate_eligibility("P1", "T1", results)

        self.assertEqual(result["criteria_results"], results)


if __name__ == "__main__":
    unittest.main()
