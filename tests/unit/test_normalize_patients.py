
import unittest
import pandas as pd

from src.normalization.normalize_patients import (
    normalize_patients,
    normalize_conditions,
    normalize_observations,
)


class TestNormalization(unittest.TestCase):

    def test_patient_normalization(self):
        raw = pd.DataFrame({
            "Id": [" P1 "],
            "BIRTHDATE": ["1990-01-15"],
            "GENDER": ["M"]
        })

        result = normalize_patients(raw)

        self.assertEqual(result.loc[0, "patient_id"], "P1")
        self.assertEqual(result.loc[0, "gender"], "M")
        self.assertEqual(
            str(result.loc[0, "birth_date"].date()),
            "1990-01-15"
        )

    def test_condition_normalization(self):
        raw = pd.DataFrame({
            "PATIENT": ["P1"],
            "DESCRIPTION": ["Type 2 Diabetes"],
            "START": ["2024-01-01"]
        })

        result = normalize_conditions(raw)

        self.assertEqual(result.loc[0, "patient_id"], "P1")
        self.assertEqual(
            result.loc[0, "condition"], "Type 2 Diabetes"
        )

    def test_observation_normalization(self):
        raw = pd.DataFrame({
            "PATIENT": ["P1"],
            "DESCRIPTION": ["HbA1c"],
            "DATE": ["2024-01-01"],
            "VALUE": ["6.5"],
            "UNITS": ["%"]
        })

        result = normalize_observations(raw)

        self.assertEqual(result.loc[0, "observation"], "HbA1c")
        self.assertEqual(result.loc[0, "value"], "6.5")
        self.assertEqual(result.loc[0, "units"], "%")


if __name__ == "__main__":
    unittest.main()
