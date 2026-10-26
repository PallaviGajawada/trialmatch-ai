
import unittest
import pandas as pd

from src.agents.lab_agent import evaluate_lab


class TestLabAgent(unittest.TestCase):

    def setUp(self):
        self.observations = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "observation": ["HbA1c", "HbA1c", "HbA1c"],
            "value": ["7.2", "9.1", "Positive"],
            "units": ["%", "%", "%"],
            "observation_date": [
                "2026-01-01",
                "2026-01-01",
                "2026-01-01"
            ]
        })

    def test_value_passes(self):
        result = evaluate_lab(
            self.observations, "P1", "HbA1c", "<=", 8, "%"
        )
        self.assertEqual(result["status"], "PASS")

    def test_value_fails(self):
        result = evaluate_lab(
            self.observations, "P2", "HbA1c", "<=", 8, "%"
        )
        self.assertEqual(result["status"], "FAIL")

    def test_missing_lab_returns_unknown(self):
        result = evaluate_lab(
            self.observations, "P99", "HbA1c", "<=", 8, "%"
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_non_numeric_lab_returns_unknown(self):
        result = evaluate_lab(
            self.observations, "P3", "HbA1c", "<=", 8, "%"
        )
        self.assertEqual(result["status"], "UNKNOWN")

    def test_wrong_unit_returns_unknown(self):
        result = evaluate_lab(
            self.observations, "P1", "HbA1c", "<=", 8, "mmol/mol"
        )
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
