
import unittest
from unittest.mock import patch, Mock

from src.ingestion.load_trials import fetch_diabetes_trials


class TestTrialIngestion(unittest.TestCase):

    @patch("src.ingestion.load_trials.requests.get")
    def test_fetch_trials(self, mock_get):
        # Create a fake API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT00000001",
                            "briefTitle": "Type 2 Diabetes Study"
                        },
                        "statusModule": {
                            "overallStatus": "RECRUITING"
                        },
                        "designModule": {
                            "studyType": "INTERVENTIONAL"
                        },
                        "eligibilityModule": {
                            "minimumAge": "18 Years",
                            "maximumAge": "65 Years",
                            "sex": "ALL",
                            "eligibilityCriteria": (
                                "Inclusion Criteria:\n"
                                "- Adults aged 18 to 65 years"
                            )
                        }
                    }
                }
            ]
        }

        mock_get.return_value = mock_response

        trials = fetch_diabetes_trials(limit=1)

        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["nct_id"], "NCT00000001")
        self.assertEqual(trials[0]["minimum_age"], "18 Years")
        self.assertEqual(trials[0]["maximum_age"], "65 Years")
        self.assertTrue(trials[0]["eligibility_criteria"])
        mock_get.assert_called_once()

    @patch("src.ingestion.load_trials.requests.get")
    def test_empty_results(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"studies": []}
        mock_get.return_value = mock_response

        trials = fetch_diabetes_trials(limit=1)

        self.assertEqual(trials, [])


if __name__ == "__main__":
    unittest.main()
