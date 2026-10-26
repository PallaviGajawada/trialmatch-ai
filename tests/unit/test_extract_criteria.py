
import unittest

from src.criteria.extract_criteria import extract_criteria


class TestCriteriaExtraction(unittest.TestCase):

    def test_age_range(self):
        text = "Adults aged 18 to 65 years"
        result = extract_criteria(text)

        self.assertEqual(result[0]["criterion_type"], "age")
        self.assertEqual(result[0]["rule"]["minimum_age"], 18)
        self.assertEqual(result[0]["rule"]["maximum_age"], 65)

    def test_type_2_diabetes(self):
        text = "Patients with Type 2 Diabetes"
        result = extract_criteria(text)

        self.assertEqual(result[0]["criterion_type"], "diagnosis")
        self.assertEqual(
            result[0]["rule"]["condition"],
            "Type 2 Diabetes"
        )

    def test_unknown_criterion_requires_review(self):
        text = "Patients with severe kidney impairment"
        result = extract_criteria(text)

        self.assertTrue(result[0]["review_required"])
        self.assertEqual(result[0]["direction"], "unknown")

    def test_empty_text_requires_review(self):
        result = extract_criteria("")

        self.assertTrue(result[0]["review_required"])


if __name__ == "__main__":
    unittest.main()
