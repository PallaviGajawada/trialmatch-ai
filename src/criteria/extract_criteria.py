
import re


def extract_criteria(eligibility_text):
    """
    Extract simple age and diagnosis criteria.
    Unrecognized criteria are preserved for human review.
    """

    if not eligibility_text or not eligibility_text.strip():
        return [{
            "criterion_type": "unknown",
            "direction": "unknown",
            "rule": None,
            "evidence": "",
            "review_required": True
        }]

    results = []

    # Split the original text into lines
    lines = [
        line.strip(" -*\t")
        for line in eligibility_text.splitlines()
        if line.strip()
    ]

    for line in lines:
        lower_line = line.lower()

        # Extract age ranges such as "aged 18 to 65 years"
        age_match = re.search(
            r"\b(?:aged\s*)?(\d{1,3})\s*(?:to|-)\s*"
            r"(\d{1,3})\s*years?\b",
            lower_line
        )

        if age_match:
            minimum_age = int(age_match.group(1))
            maximum_age = int(age_match.group(2))

            results.append({
                "criterion_type": "age",
                "direction": "inclusion",
                "rule": {
                    "minimum_age": minimum_age,
                    "maximum_age": maximum_age
                },
                "evidence": line,
                "review_required": minimum_age > maximum_age
            })
            continue

        # Extract simple Type 2 Diabetes mentions
        if "type 2 diabetes" in lower_line:
            results.append({
                "criterion_type": "diagnosis",
                "direction": (
                    "exclusion"
                    if any(word in lower_line for word in [
                        "without", "no history of", "absence of"
                    ])
                    else "inclusion"
                ),
                "rule": {
                    "condition": "Type 2 Diabetes"
                },
                "evidence": line,
                "review_required": False
            })
            continue

        # Keep other lines instead of silently discarding them
        results.append({
            "criterion_type": "unclassified",
            "direction": "unknown",
            "rule": None,
            "evidence": line,
            "review_required": True
        })

    return results
