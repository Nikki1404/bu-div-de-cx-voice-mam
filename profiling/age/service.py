from profiling.config import AGE_LABELS

AGE_BUCKETS = {
    "teens": "Under 20",
    "twenties": "20-30",
    "thirties": "30-40",
    "fourties": "40-50",
    "fifties": "50-60",
    "sixties": "60+",
}


def age_from_gender_age(gender_age: dict) -> dict:
    """Marginalise the joint gender_age head into age-group probabilities."""
    return {age: gender_age[f"female-{age}"] + gender_age[f"male-{age}"] for age in AGE_LABELS}


def format_age_result(prediction: dict) -> dict:
    probabilities = {label: float(prediction["age"][label]) for label in AGE_LABELS}
    age_group = max(probabilities, key=probabilities.get)
    return {
        "age_group": age_group,
        "age_bucket": AGE_BUCKETS[age_group],
        "age_confidence": round(probabilities[age_group], 4),
        "age_probabilities": {label: round(p, 4) for label, p in probabilities.items()},
    }
