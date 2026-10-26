
import re
from datetime import date, datetime


def parse_age(age_text):
    """Convert an age such as '18 Years' into an integer."""

    if age_text is None:
        return None

    match = re.search(r"\d+", str(age_text))

    if match:
        return int(match.group())

    return None


def calculate_age(birth_date, reference_date):
    """Calculate age in completed years on a given date."""

    if birth_date is None:
        return None

    try:
        if isinstance(birth_date, str):
            birth_date = datetime.strptime(
                birth_date[:10], "%Y-%m-%d"
            ).date()
        elif isinstance(birth_date, datetime):
            birth_date = birth_date.date()

        if not isinstance(birth_date, date):
            return None

        if birth_date > reference_date:
            return None

        age = reference_date.year - birth_date.year

        if (reference_date.month, reference_date.day) < (
            birth_date.month, birth_date.day
        ):
            age -= 1

        return age

    except (ValueError, TypeError):
        return None


def evaluate_age(patient, trial, reference_date=None):
    """Evaluate a patient's age against a trial's age limits."""

    if reference_date is None:
        reference_date = date.today()

    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    minimum_age = parse_age(trial.get("minimum_age"))
    maximum_age = parse_age(trial.get("maximum_age"))

    # No age restrictions were supplied by the API.
    # This does not mean other eligibility criteria are satisfied.
    if minimum_age is None and maximum_age is None:
        return {
            "agent": "age_agent",
            "status": "NOT_APPLICABLE",
            "explanation": "No age limits were provided for this trial."
        }

    birth_date = patient.get("birth_date")

    if birth_date is None:
        birth_date = patient.get("BIRTHDATE")

    age = calculate_age(birth_date, reference_date)

    if age is None:
        return {
            "agent": "age_agent",
            "status": "UNKNOWN",
            "explanation": "Patient birth date is missing or invalid."
        }

    if (
        minimum_age is not None
        and maximum_age is not None
        and minimum_age > maximum_age
    ):
        return {
            "agent": "age_agent",
            "status": "UNKNOWN",
            "explanation": "Trial age limits are inconsistent."
        }

    if minimum_age is not None and age < minimum_age:
        return {
            "agent": "age_agent",
            "status": "FAIL",
            "age": age,
            "explanation": (
                f"Patient is {age}; minimum required age is "
                f"{minimum_age}."
            )
        }

    if maximum_age is not None and age > maximum_age:
        return {
            "agent": "age_agent",
            "status": "FAIL",
            "age": age,
            "explanation": (
                f"Patient is {age}; maximum allowed age is "
                f"{maximum_age}."
            )
        }

    return {
        "agent": "age_agent",
        "status": "PASS",
        "age": age,
        "explanation": "Patient satisfies the specified age limits."
    }
