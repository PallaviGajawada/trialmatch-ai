
import unittest
import pandas as pd

from src.agents.diagnosis_agent import evaluate_diagnosis


class TestDiagnosisAgent(unittest.TestCase):

    def setUp(self):
        self.conditions = pd.DataFrame({
            "patient_id": ["P1", "P1", "P2"],
            "condition": [
                "Type 2 Diabetes Mellitus",
                "Hypertension",
                "Asthma"
            ]
        })

    def test_documented_diagnosis_passes(self):
        result = evaluate_diagnosis("P1", self.conditions)

        self.assertEqual(result["status"], "PASS")
        self.assertIn(
            "Type 2 Diabetes Mellitus",
            result["evidence"]
        )

    def test_no_diagnosis_returns_unknown(self):
        result = evaluate_diagnosis("P2", self.conditions)

        self.assertEqual(result["status"], "UNKNOWN")

    def test_unknown_patient_returns_unknown(self):
        result = evaluate_diagnosis("P99", self.conditions)

        self.assertEqual(result["status"], "UNKNOWN")

    def test_exclusion_with_diagnosis_fails(self):
        result = evaluate_diagnosis(
            "P1",
            self.conditions,
            direction="exclusion"
        )

        self.assertEqual(result["status"], "FAIL")

    def test_missing_condition_data_returns_unknown(self):
        result = evaluate_diagnosis("P1", None)

        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
