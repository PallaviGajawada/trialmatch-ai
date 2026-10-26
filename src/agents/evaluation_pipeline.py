
from src.agents.age_agent import evaluate_age
from src.agents.diagnosis_agent import evaluate_diagnosis
from src.agents.lab_agent import evaluate_lab
from src.agents.exclusion_agent import evaluate_exclusion
from src.agents.coordinator import evaluate_eligibility
from src.agents.evidence import create_evidence


def evaluate_patient_for_trial(
    patient_id,
    trial,
    patients,
    conditions,
    observations,
    criteria_spec,
    reference_date=None
):
    """
    Evaluate one synthetic patient against one trial.

    criteria_spec format:
    {
        "all_criteria_accounted_for": False,
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
        "exclusions": ["Heart Failure"],
        "unsupported_criteria": []
    }

    Unsupported or incompletely mapped criteria require review.
    This is a research prototype, not a clinical decision tool.
    """

    if not isinstance(trial, dict):
        raise ValueError("trial must be a dictionary.")

    if not isinstance(criteria_spec, dict):
        raise ValueError("criteria_spec must be a dictionary.")

    trial_id = trial.get("trial_id") or trial.get("nct_id")

    if not patient_id or not trial_id:
        raise ValueError("patient_id and trial ID are required.")

    source = trial.get("source") or "ClinicalTrials.gov"
    agent_results = []
    evidence_records = []

    def record(result, criterion):
        agent_results.append(result)

        evidence_records.append(
            create_evidence(
                patient_id=patient_id,
                trial_id=trial_id,
                agent_result=result,
                criterion=criterion,
                source=source
            )
        )

    # Find the patient in the normalized patient table.
    patient_found = False
    patient = {}

    if (
        patients is not None
        and hasattr(patients, "columns")
        and "patient_id" in patients.columns
    ):
        matching_patients = patients[
            patients["patient_id"].astype("string").str.strip()
            == str(patient_id).strip()
        ]

        if len(matching_patients) == 1:
            patient = matching_patients.iloc[0].to_dict()
            patient_found = True

    # 1. Age criterion
    if patient_found:
        age_result = evaluate_age(
            patient, trial, reference_date=reference_date
        )
    else:
        age_result = {
            "agent": "age_agent",
            "status": "UNKNOWN",
            "explanation": (
                "Patient was not found in the normalized patient table."
            )
        }

    record(
        age_result,
        (
            f"Age limits: minimum={trial.get('minimum_age')}, "
            f"maximum={trial.get('maximum_age')}"
        )
    )

    # 2. Diagnosis criterion, when explicitly supplied
    diagnosis = criteria_spec.get("diagnosis")

    if diagnosis is not None:
        if not isinstance(diagnosis, dict):
            diagnosis_result = {
                "agent": "diagnosis_agent",
                "status": "UNKNOWN",
                "explanation": "Diagnosis criterion has an invalid format."
            }
            diagnosis_label = "Invalid diagnosis criterion"

        elif not patient_found:
            diagnosis_result = {
                "agent": "diagnosis_agent",
                "status": "UNKNOWN",
                "explanation": "Patient record is unavailable."
            }
            diagnosis_label = str(diagnosis.get("condition", "Diagnosis"))

        else:
            diagnosis_label = str(
                diagnosis.get("condition", "Diagnosis")
            )

            diagnosis_result = evaluate_diagnosis(
                patient_id=patient_id,
                conditions=conditions,
                required_condition=diagnosis.get("condition"),
                direction=diagnosis.get("direction", "inclusion")
            )

        record(diagnosis_result, diagnosis_label)

    # 3. Lab criteria, when explicitly supplied
    labs = criteria_spec.get("labs", [])

    if not isinstance(labs, list):
        labs = [{
            "invalid_criteria_format": True
        }]

    for lab in labs:
        if not isinstance(lab, dict):
            lab = {"invalid_criteria_format": True}

        test_name = lab.get("test_name", "Unknown lab test")

        if lab.get("invalid_criteria_format"):
            lab_result = {
                "agent": "lab_agent",
                "status": "UNKNOWN",
                "explanation": "Lab criterion has an invalid format."
            }

        elif not patient_found:
            lab_result = {
                "agent": "lab_agent",
                "status": "UNKNOWN",
                "test": test_name,
                "explanation": "Patient record is unavailable."
            }

        else:
            lab_result = evaluate_lab(
                observations=observations,
                patient_id=patient_id,
                test_name=test_name,
                operator=lab.get("operator"),
                threshold=lab.get("threshold"),
                expected_unit=lab.get("unit")
            )

        record(lab_result, str(lab))

    # 4. Exclusion criteria
    exclusions = criteria_spec.get("exclusions", [])

    if not isinstance(exclusions, list):
        exclusions = [{"invalid_criteria_format": True}]

    for exclusion in exclusions:
        if not isinstance(exclusion, str) or not exclusion.strip():
            exclusion_result = {
                "agent": "exclusion_agent",
                "status": "UNKNOWN",
                "explanation": "Exclusion criterion is missing or invalid."
            }
            exclusion_label = str(exclusion)

        elif not patient_found:
            exclusion_result = {
                "agent": "exclusion_agent",
                "status": "UNKNOWN",
                "condition": exclusion,
                "explanation": "Patient record is unavailable."
            }
            exclusion_label = exclusion

        else:
            exclusion_result = evaluate_exclusion(
                patient_id=patient_id,
                conditions=conditions,
                excluded_condition=exclusion
            )
            exclusion_label = exclusion

        record(exclusion_result, exclusion_label)

    # 5. Criteria unsupported by the current agents
    unsupported = criteria_spec.get("unsupported_criteria", [])

    if not isinstance(unsupported, list):
        unsupported = ["Unsupported criteria list has an invalid format."]

    for criterion in unsupported:
        result = {
            "agent": "criteria_review",
            "status": "UNKNOWN",
            "explanation": (
                "This criterion is not evaluated by the current agents "
                "and requires human review."
            )
        }
        record(result, str(criterion))

    # 6. Require explicit confirmation that all trial criteria
    # have been accounted for. Defaults to False for safety.
    if criteria_spec.get("all_criteria_accounted_for") is not True:
        result = {
            "agent": "criteria_review",
            "status": "UNKNOWN",
            "explanation": (
                "It has not been confirmed that all trial eligibility "
                "criteria have been mapped and evaluated."
            )
        }
        record(result, "Completeness of trial criteria mapping")

    # 7. Combine all agent results
    overall_result = evaluate_eligibility(
        patient_id=str(patient_id),
        trial_id=str(trial_id),
        agent_results=agent_results
    )

    return {
        "result": overall_result,
        "evidence": evidence_records
    }
