
import pandas as pd


def normalize_patients(patients):
    """Clean patient demographics and standardize dates and gender."""

    df = patients[["Id", "BIRTHDATE", "GENDER"]].copy()

    df = df.rename(columns={
        "Id": "patient_id",
        "BIRTHDATE": "birth_date",
        "GENDER": "gender"
    })

    df["patient_id"] = df["patient_id"].astype("string").str.strip()
    df["birth_date"] = pd.to_datetime(
        df["birth_date"], errors="coerce"
    )

    df["gender"] = (
        df["gender"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # Standardize common values without guessing missing values
    df["gender"] = df["gender"].replace({
        "MALE": "M",
        "FEMALE": "F"
    })

    # Remove records without a usable patient ID
    df = df.dropna(subset=["patient_id"])
    df = df[df["patient_id"] != ""]

    if df["patient_id"].duplicated().any():
        raise ValueError("Duplicate patient IDs found.")

    return df.reset_index(drop=True)


def normalize_conditions(conditions):
    """Clean medical condition records."""

    df = conditions[["PATIENT", "DESCRIPTION", "START"]].copy()

    df = df.rename(columns={
        "PATIENT": "patient_id",
        "DESCRIPTION": "condition",
        "START": "start_date"
    })

    df["patient_id"] = df["patient_id"].astype("string").str.strip()
    df["condition"] = df["condition"].astype("string").str.strip()
    df["start_date"] = pd.to_datetime(
        df["start_date"], errors="coerce"
    )

    return df


def normalize_observations(observations):
    """Clean clinical observation records."""

    columns = ["PATIENT", "DESCRIPTION", "DATE"]

    # Include measurements when these columns exist
    for column in ["VALUE", "UNITS", "CODE", "TYPE"]:
        if column in observations.columns:
            columns.append(column)

    df = observations[columns].copy()

    df = df.rename(columns={
        "PATIENT": "patient_id",
        "DESCRIPTION": "observation",
        "DATE": "observation_date",
        "VALUE": "value",
        "UNITS": "units",
        "CODE": "code",
        "TYPE": "type"
    })

    df["patient_id"] = df["patient_id"].astype("string").str.strip()
    df["observation"] = df["observation"].astype("string").str.strip()
    df["observation_date"] = pd.to_datetime(
        df["observation_date"], errors="coerce"
    )

    # Keep the original measurement value.
    # Convert to numeric separately when needed for a specific lab test.
    if "value" in df.columns:
        df["value"] = df["value"].astype("string").str.strip()

    return df


def validate_patient_links(patients, conditions, observations):
    """Report condition and observation records without a known patient."""

    patient_ids = set(patients["patient_id"].dropna())

    unmatched_conditions = (
        ~conditions["patient_id"].isin(patient_ids)
    ).sum()

    unmatched_observations = (
        ~observations["patient_id"].isin(patient_ids)
    ).sum()

    return {
        "unmatched_conditions": int(unmatched_conditions),
        "unmatched_observations": int(unmatched_observations)
    }
