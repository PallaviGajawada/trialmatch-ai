
import unittest
from datetime import date

from src.agents.age_agent import evaluate_age


class TestAgeAgent(unittest.TestCase):

    def setUp(self):
        self.reference_date = date(2026, 10, 26)

    def test_age_passes(self):
        patient = {"birth_date": "1990-05-10"}
        trial = {"minimum_age": "18 Years", "maximum_age": "65 Years"}

        result = evaluate_age(
            patient, trial, self.reference_date
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["age"], 36)

    def test_patient_too_young(self):
        patient = {"birth_date": "2010-01-01"}
        trial = {"minimum_age": "18 Years", "maximum_age": "65 Years"}

        result = evaluate_age(
            patient, trial, self.reference_date
        )

        self.assertEqual(result["status"], "FAIL")

    def test_patient_too_old(self):
        patient = {"birth_date": "1940-01-01"}
        trial = {"minimum_age": "18 Years", "maximum_age": "65 Years"}

        result = evaluate_age(
            patient, trial, self.reference_date
        )

        self.assertEqual(result["status"], "FAIL")

    def test_missing_birth_date(self):
        patient = {"birth_date": None}
        trial = {"minimum_age": "18 Years", "maximum_age": "65 Years"}

        result = evaluate_age(
            patient, trial, self.reference_date
        )

        self.assertEqual(result["status"], "UNKNOWN")

    def test_no_age_limits(self):
        patient = {"birth_date": "1990-05-10"}
        trial = {"minimum_age": None, "maximum_age": None}

        result = evaluate_age(
            patient, trial, self.reference_date
        )

        self.assertEqual(result["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
