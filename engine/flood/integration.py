"""Separate indicators, no fabricated combination or probability."""

def status():
    return {"status": "exploratory_indicators", "combined_category": None,
        "combined_probability": None, "method": "side_by_side",
        "reason": "No validated integration methodology configured"}


def aggregate_basin(*args, **kwargs):
    return {"status": "unsupported", "value": None,
        "reason": "Verified basin geometry, aggregation method and coverage policy required"}
