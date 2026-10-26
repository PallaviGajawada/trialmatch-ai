
import math
import pandas as pd


def evaluate_lab(
    observations,
    patient_id,
    test_name,
    operator,
    threshold,
    expected_unit=None
):
    """
    Compare a patient's latest matching lab result with a threshold.

    Supported operators: <, <=, >, >=, ==

    This function evaluates one explicitly specified threshold.
    It does not decide overall trial eligibility.
    """

    def unknown(message):
        return {
            "agent": "lab_agent",
            "status": "UNKNOWN",
            "test": test_name,
            "explanation": message
        }

    if observations is None or not isinstance(observations, pd.DataFrame):
        return unknown("Observation data is missing or invalid.")

    required = {"patient_id", "observation", "value"}

    if not required.issubset(observations.columns):
        return unknown("Observation data is missing required columns.")

    if operator not in {"<", "<=", ">", ">=", "=="}:
        return unknown("Unsupported comparison operator.")

    try:
        threshold = float(threshold)
        if not math.isfinite(threshold):
            return unknown("Threshold must be a finite number.")
    except (TypeError, ValueError):
        return unknown("Threshold is missing or invalid.")

    patient_rows = observations[
        observations["patient_id"].astype("string").str.strip()
        == str(patient_id).strip()
    ]

    matching = patient_rows[
        patient_rows["observation"].astype("string").str.strip().str.casefold()
        == str(test_name).strip().casefold()
    ].copy()

    if matching.empty:
        return unknown(f"No {test_name} result was found for this patient.")

    if expected_unit is not None:
        if "units" not in matching.columns:
            return unknown("Lab units are unavailable for comparison.")

        matching = matching[
            matching["units"].astype("string").str.strip().str.casefold()
            == str(expected_unit).strip().casefold()
        ]

        if matching.empty:
            return unknown(
                "No matching lab result with the required unit was found."
            )

    # Prefer the most recent result when dates are available.
    if "observation_date" in matching.columns:
        matching["observation_date"] = pd.to_datetime(
            matching["observation_date"], errors="coerce"
        )
        matching = matching.sort_values(
            "observation_date", na_position="first"
        )

    latest = matching.iloc[-1]

    try:
        value = float(latest["value"])
        if not math.isfinite(value):
            return unknown("The lab value is not a finite number.")
    except (TypeError, ValueError):
        return unknown("The lab value is missing or non-numeric.")

    comparisons = {
        "<": value < threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        ">=": value >= threshold,
        "==": value == threshold
    }

    passed = comparisons[operator]

    return {
        "agent": "lab_agent",
        "status": "PASS" if passed else "FAIL",
        "test": test_name,
        "value": value,
        "unit": latest.get("units") if "units" in matching.columns else None,
        "threshold": threshold,
        "operator": operator,
        "explanation": (
            f"{test_name} value {value} "
            f"{operator} {threshold}: criterion "
            f"{'satisfied' if passed else 'not satisfied'}."
        )
    }
