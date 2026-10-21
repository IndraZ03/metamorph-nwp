"""Numeric rainfall only until official categories and inclusivity are verified."""

def classify_rainfall(value):
    return None


def status():
    return {"classification_status": "unverified", "rainfall_category_scale": None,
        "window_type": "trailing_p24", "window_hours": 24, "units": "mm",
        "reason": "Primary BMKG daily category limits/inclusivity not verified"}
