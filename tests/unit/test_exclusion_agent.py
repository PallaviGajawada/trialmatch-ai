
import unittest
import pandas as pd

from src.agents.exclusion_agent import evaluate_exclusion


class TestExclusionAgent(unittest.TestCase):

    def setUp(self):
        self.conditions = pd.DataFrame({
            "patient_id": ["P1", "P1", "P2"],
            "condition": [
                "Heart Failure",
                "Type 2 Diabetes",
                "Type 2 Diabetes"
            ]
        })

    def test_documented_excluded_condition_fails(self):
        result = evaluate_exclusion(
            "P1", self.conditions, "Heart Failure"
        )
        self.assertEqual(result["status"], "FAIL")

    def test_missing_condition_record_returns_unknown(self):
        result = evaluate_exclusion(
            "P1", self.conditions, "Kidney Disease"
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_unknown_patient_returns_unknown(self):
        result = evaluate_exclusion(
            "P99", self.conditions, "Heart Failure"
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_missing_data_returns_unknown(self):
        result = evaluate_exclusion(
            "P1", None, "Heart Failure"
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_invalid_criterion_returns_unknown(self):
        result = evaluate_exclusion(
            "P1", self.conditions, "   "
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_missing_required_column_returns_unknown(self):
        invalid_data = pd.DataFrame({
            "patient_id": ["P1"]
        })

        result = evaluate_exclusion(
            "P1", invalid_data, "Heart Failure"
        )
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
