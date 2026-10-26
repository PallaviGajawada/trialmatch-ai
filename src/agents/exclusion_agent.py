
import pandas as pd

from src.agents.diagnosis_agent import normalize_condition_name


def evaluate_exclusion(patient_id, conditions, excluded_condition):
    """
    Check whether a documented patient condition matches
    a trial's exclusion criterion.

    PASS: No matching excluded condition was found in the
          available records. This is not proof of absence.
    FAIL: A matching excluded condition is documented.
    UNKNOWN: Patient data or criterion is missing/invalid.
    """

    def unknown(message):
        return {
            "agent": "exclusion_agent",
            "status": "UNKNOWN",
            "condition": excluded_condition,
            "explanation": message
        }

    if not patient_id or not excluded_condition:
        return unknown("Patient ID or exclusion criterion is missing.")

    if conditions is None or not isinstance(conditions, pd.DataFrame):
        return unknown("Patient condition data is missing or invalid.")

    required_columns = {"patient_id", "condition"}

    if not required_columns.issubset(conditions.columns):
        return unknown("Condition data is missing required columns.")

    target = normalize_condition_name(excluded_condition)

    if not target:
        return unknown("The exclusion criterion could not be normalized.")

    patient_conditions = conditions[
        conditions["patient_id"].astype("string").str.strip()
        == str(patient_id).strip()
    ]

    if patient_conditions.empty:
        return unknown(
            "No condition records were found for this patient; "
            "absence of records does not prove absence of disease."
        )

    documented_conditions = (
        patient_conditions["condition"]
        .dropna()
        .astype(str)
        .map(normalize_condition_name)
    )

    # Conservative exact matching: avoid guessing that similar
    # condition names necessarily mean the same diagnosis.
    if target in set(documented_conditions):
        return {
            "agent": "exclusion_agent",
            "status": "FAIL",
            "condition": excluded_condition,
            "explanation": (
                f"The excluded condition '{excluded_condition}' "
                "is documented for this patient."
            )
        }

    return {
        "agent": "exclusion_agent",
        "status": "UNKNOWN",
        "condition": excluded_condition,
        "explanation": (
            f"No exact record of '{excluded_condition}' was found. "
            "This does not establish that the patient is free "
            "of the condition."
        )
    }
