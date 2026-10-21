"""Fail-closed gate. Original equation, parameters and domain not yet verified."""
import numpy as np


def model_status():
    return {"status": "NOT_CONFIGURED", "probability": None, "category": None,
        "decay_factor": None, "parameter_verification": "unverified",
        "local_validation": "not_performed", "domain_status": "unsupported",
        "reason": "Original equation, decay, coefficients, regional domains and category boundaries unavailable",
        "reference": "https://www.researchgate.net/publication/343548913_Probabilistic_Rainfall_Threshold_for_Flood_Early_Warning_in_the_Upper_Watersheds_Java_Island_Indonesia"}


def stable_sigmoid(value):
    """Numerical primitive only; not an enabled flood model."""
    value = np.asarray(value, dtype=np.float64)
    result = np.empty_like(value)
    positive = value >= 0
    result[positive] = 1 / (1 + np.exp(-value[positive]))
    exp = np.exp(value[~positive])
    result[~positive] = exp / (1 + exp)
    return result


def evaluate(*args, **kwargs):
    return model_status()
