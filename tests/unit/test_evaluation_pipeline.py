
import unittest
import pandas as pd
from datetime import date

from src.agents.evaluation_pipeline import evaluate_patient_for_trial


class TestEvaluationPipeline(unittest.TestCase):

    def setUp(self):
        self.patients = pd.DataFrame({
            "patient_id": ["P1"],
            "birth_date": [pd.Timestamp("1990-01-01")],
            "gender": ["F"]
        })

        self.conditions = pd.DataFrame({
            "patient_id": ["P1"],
            "condition": ["Type 2 Diabetes"]
        })

        self.observations = pd.DataFrame({
            "patient_id": ["P1"],
            "observation": ["HbA1c"],
            "value": ["7.2"],
            "units": ["%"],
            "observation_date": ["2026-01-01"]
        })

        self.trial = {
            "nct_id": "NCT00000001",
            "minimum_age": "18 Years",
            "maximum_age": "65 Years",
            "source": "ClinicalTrials.gov"
        }

        self.criteria_spec = {
            "all_criteria_accounted_for": True,
            "diagnosis": {
                "condition": "Type 2 Diabetes",
                "direction": "inclusion"
            },
            "labs": [
                {
                    "test_name": "HbA1c",
                    "operator": "<=",
                    "threshold": 8,
                    "unit": "%"
                }
            ],
            "exclusions": [],
            "unsupported_criteria": []
        }

    def test_all_supported_criteria_pass(self):
        result = evaluate_patient_for_trial(
            "P1",
            self.trial,
            self.patients,
            self.conditions,
            self.observations,
            self.criteria_spec,
            reference_date=date(2026, 10, 26)
        )

        self.assertEqual(
            result["result"]["status"],
            "Potential match"
        )

    def test_incomplete_criteria_require_review(self):
        criteria = self.criteria_spec.copy()
        criteria["all_criteria_accounted_for"] = False

        result = evaluate_patient_for_trial(
            "P1",
            self.trial,
            self.patients,
            self.conditions,
            self.observations,
            criteria,
            reference_date=date(2026, 10, 26)
        )

        self.assertEqual(
            result["result"]["status"],
            "Requires review"
        )

    def test_unsupported_criterion_requires_review(self):
        criteria = self.criteria_spec.copy()
        criteria["unsupported_criteria"] = [
            "History of a specific medical condition"
        ]

        result = evaluate_patient_for_trial(
            "P1",
            self.trial,
            self.patients,
            self.conditions,
            self.observations,
            criteria,
            reference_date=date(2026, 10, 26)
        )

        self.assertEqual(
            result["result"]["status"],
            "Requires review"
        )

    def test_documented_exclusion_means_not_a_match(self):
        conditions = pd.DataFrame({
            "patient_id": ["P1", "P1"],
            "condition": ["Type 2 Diabetes", "Heart Failure"]
        })

        criteria = self.criteria_spec.copy()
        criteria["exclusions"] = ["Heart Failure"]

        result = evaluate_patient_for_trial(
            "P1",
            self.trial,
            self.patients,
            conditions,
            self.observations,
            criteria,
            reference_date=date(2026, 10, 26)
        )

        self.assertEqual(
            result["result"]["status"],
            "Not a match"
        )

    def test_missing_patient_requires_review(self):
        result = evaluate_patient_for_trial(
            "P99",
            self.trial,
            self.patients,
            self.conditions,
            self.observations,
            self.criteria_spec,
            reference_date=date(2026, 10, 26)
        )

        self.assertEqual(
            result["result"]["status"],
            "Requires review"
        )

    def test_evidence_is_created_for_agent_results(self):
        result = evaluate_patient_for_trial(
            "P1",
            self.trial,
            self.patients,
            self.conditions,
            self.observations,
            self.criteria_spec,
            reference_date=date(2026, 10, 26)
        )

        self.assertGreater(len(result["evidence"]), 0)

        for record in result["evidence"]:
            self.assertEqual(record["patient_id"], "P1")
            self.assertEqual(record["trial_id"], "NCT00000001")
            self.assertIn("status", record)
            self.assertIn("explanation", record)


if __name__ == "__main__":
    unittest.main()
