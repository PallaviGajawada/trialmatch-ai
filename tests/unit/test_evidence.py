
import unittest

from src.agents.evidence import create_evidence


class TestEvidence(unittest.TestCase):

    def setUp(self):
        self.agent_result = {
            "agent": "age_agent",
            "status": "PASS",
            "explanation": "Patient meets the age criterion.",
            "age": 35
        }

    def test_create_evidence_record(self):
        result = create_evidence(
            "P1",
            "T1",
            self.agent_result,
            "Age between 18 and 65",
            "ClinicalTrials.gov"
        )

        self.assertEqual(result["patient_id"], "P1")
        self.assertEqual(result["trial_id"], "T1")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["agent"], "age_agent")

    def test_evidence_details_are_preserved(self):
        result = create_evidence(
            "P1", "T1", self.agent_result, "Age criterion"
        )

        self.assertEqual(result["evidence_details"]["age"], 35)

    def test_unknown_status_is_preserved(self):
        agent_result = {
            "agent": "lab_agent",
            "status": "UNKNOWN",
            "explanation": "Lab result is missing."
        }

        result = create_evidence(
            "P1", "T1", agent_result, "HbA1c threshold"
        )

        self.assertEqual(result["status"], "UNKNOWN")

    def test_invalid_agent_result_raises_error(self):
        with self.assertRaises(ValueError):
            create_evidence(
                "P1", "T1", None, "Age criterion"
            )

    def test_missing_patient_id_raises_error(self):
        with self.assertRaises(ValueError):
            create_evidence(
                "", "T1", self.agent_result, "Age criterion"
            )

    def test_missing_criterion_raises_error(self):
        with self.assertRaises(ValueError):
            create_evidence(
                "P1", "T1", self.agent_result, " "
            )


if __name__ == "__main__":
    unittest.main()
