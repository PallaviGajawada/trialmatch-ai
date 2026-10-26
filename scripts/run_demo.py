
import json
from pathlib import Path

from src.ingestion.load_synthea import load_synthea_data
from src.normalization.normalize_patients import (
    normalize_patients,
    normalize_conditions,
    normalize_observations,
)
from src.agents.evaluation_pipeline import evaluate_patient_for_trial


# 1. Load the synthetic patient datasets
print("Loading synthetic patient data...")

raw_data = load_synthea_data()

patients = normalize_patients(raw_data["patients"])
conditions = normalize_conditions(raw_data["conditions"])
observations = normalize_observations(raw_data["observations"])

print("Patients loaded:", len(patients))
print("Conditions loaded:", len(conditions))
print("Observations loaded:", len(observations))


# 2. Load the saved clinical trial records
trials_file = Path("data/trials/diabetes_trials.json")

if not trials_file.exists():
    raise FileNotFoundError(
        "Trial file not found. Check data/trials/diabetes_trials.json"
    )

with trials_file.open("r", encoding="utf-8") as file:
    trials = json.load(file)

if not trials:
    raise ValueError("No clinical trials were found in the JSON file.")


# 3. Select one patient and one trial for a demo
patient_id = str(patients.iloc[0]["patient_id"])
trial = trials[0]

print("\nSelected patient:", patient_id)
print("Selected trial:", trial.get("nct_id"))
print("Trial title:", trial.get("title"))


# 4. Define the criteria mapping
# Do not assume the search topic is an actual inclusion criterion.
# The trial's full eligibility criteria still need human review.
criteria_spec = {
    "all_criteria_accounted_for": False,
    "diagnosis": None,
    "labs": [],
    "exclusions": [],
    "unsupported_criteria": [
        "Full trial eligibility criteria require manual review and mapping."
    ],
}


# 5. Run the evaluation pipeline
evaluation = evaluate_patient_for_trial(
    patient_id=patient_id,
    trial=trial,
    patients=patients,
    conditions=conditions,
    observations=observations,
    criteria_spec=criteria_spec,
)


# 6. Display the overall result
print("\n========== EVALUATION RESULT ==========")
print(json.dumps(evaluation["result"], indent=2, default=str))


# 7. Display the supporting evidence
print("\n========== EVIDENCE RECORDS ==========")
print(json.dumps(evaluation["evidence"], indent=2, default=str))


# 8. Save the result and evidence to a JSON file
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "demo_evaluation.json"

with output_file.open("w", encoding="utf-8") as file:
    json.dump(evaluation, file, indent=2, default=str)

print("\nEvaluation saved to:", output_file)
