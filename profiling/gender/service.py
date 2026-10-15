from profiling.config import AGE_LABELS, SEX_LABELS


def gender_from_gender_age(gender_age: dict) -> dict:
    """Marginalise the joint gender_age head into female/male probabilities."""
    return {
        gender: sum(gender_age[f"{gender}-{age}"] for age in AGE_LABELS)
        for gender in ("female", "male")
    }


def format_gender_result(prediction: dict) -> dict:
    female = float(prediction["gender"]["female"])
    male = float(prediction["gender"]["male"])
    if female > male:
        gender, confidence = SEX_LABELS[0], female
    else:
        gender, confidence = SEX_LABELS[1], male
    return {
        "gender": gender,
        "gender_confidence": round(confidence, 4),
        "gender_probabilities": {"female": round(female, 4), "male": round(male, 4)},
    }
