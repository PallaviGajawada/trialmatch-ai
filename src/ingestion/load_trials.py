
import json
from pathlib import Path

import requests


API_URL = "https://clinicaltrials.gov/api/v2/studies"
OUTPUT_DIR = Path("data/trials")
OUTPUT_FILE = OUTPUT_DIR / "diabetes_trials.json"


def fetch_diabetes_trials(limit=10):
    """Fetch a small set of Type 2 Diabetes trial records."""

    params = {
        "query.cond": "Type 2 Diabetes",
        "pageSize": limit,
        "format": "json"
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()

    result = response.json()
    trials = []

    for study in result.get("studies", []):
        protocol = study.get("protocolSection", {})

        identification = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        eligibility = protocol.get("eligibilityModule", {})
        design = protocol.get("designModule", {})

        trial = {
            "nct_id": identification.get("nctId"),
            "title": identification.get("briefTitle"),
            "status": status.get("overallStatus"),
            "study_type": design.get("studyType"),
            "minimum_age": eligibility.get("minimumAge"),
            "maximum_age": eligibility.get("maximumAge"),
            "sex": eligibility.get("sex"),
            "eligibility_criteria": eligibility.get(
                "eligibilityCriteria"
            ),
            "source": "ClinicalTrials.gov"
        }

        trials.append(trial)

    return trials


def save_trials(trials):
    """Save trial records as JSON."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(trials, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(trials)} trials to {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        trials = fetch_diabetes_trials(limit=10)
        save_trials(trials)

        print("\nRetrieved trials:")
        for trial in trials:
            print(
                trial["nct_id"],
                "-",
                trial["title"],
                "| Status:",
                trial["status"]
            )

    except requests.RequestException as error:
        print("Could not retrieve trials:", error)
