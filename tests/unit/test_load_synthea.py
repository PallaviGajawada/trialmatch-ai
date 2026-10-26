
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.ingestion.load_synthea import load_synthea_data


class TestSyntheaLoader(unittest.TestCase):

    def create_csv(self, folder, filename, data):
        path = Path(folder) / filename
        pd.DataFrame(data).to_csv(path, index=False)

    def test_load_valid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            self.create_csv(folder, "patients.csv", {
                "Id": ["P1"],
                "BIRTHDATE": ["1990-01-01"],
                "GENDER": ["M"]
            })

            self.create_csv(folder, "conditions.csv", {
                "PATIENT": ["P1"],
                "DESCRIPTION": ["Type 2 Diabetes"],
                "START": ["2024-01-01"]
            })

            self.create_csv(folder, "observations.csv", {
                "PATIENT": ["P1"],
                "DESCRIPTION": ["HbA1c"],
                "DATE": ["2024-01-01"]
            })

            data = load_synthea_data(folder)

            self.assertEqual(len(data["patients"]), 1)
            self.assertEqual(len(data["conditions"]), 1)
            self.assertEqual(len(data["observations"]), 1)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                load_synthea_data(folder)

    def test_missing_required_column(self):
        with tempfile.TemporaryDirectory() as folder:
            self.create_csv(folder, "patients.csv", {
                "Id": ["P1"],
                "GENDER": ["M"]
            })

            with self.assertRaises(ValueError):
                load_synthea_data(folder)


if __name__ == "__main__":
    unittest.main()
