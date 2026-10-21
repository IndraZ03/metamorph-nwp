from __future__ import annotations

import numpy as np

from .config import (
    CODE_BAHAYA,
    CODE_NODATA,
    CODE_NO_TRIGGER,
    CODE_SIAGA,
    CODE_WASPADA,
    RAIN_THRESHOLD_24H,
    HAZARD_LOW_MAX,
    HAZARD_MEDIUM_MAX,
)

CATEGORY_NAMES = {
    CODE_NO_TRIGGER: "no_trigger",
    CODE_WASPADA: "waspada",
    CODE_SIAGA: "siaga",
    CODE_BAHAYA: "bahaya",
    CODE_NODATA: "nodata",
}

NAME_TO_CODE = {v: k for k, v in CATEGORY_NAMES.items()}


def hazard_class_from_index(
    index: float | None,
    low_max: float = HAZARD_LOW_MAX,
    medium_max: float = HAZARD_MEDIUM_MAX,
) -> str:
    if index is None or not np.isfinite(index) or index < 0.0 or index > 1.0:
        return "nodata"
    if index <= low_max:
        return "low"
    if index <= medium_max:
        return "medium"
    return "high"


def classify_landslide(hazard_class: str | None, rainfall_24h: float | None) -> str:
    if rainfall_24h is None or not np.isfinite(rainfall_24h) or rainfall_24h < 0.0:
        return "nodata"
    if hazard_class not in ("low", "medium", "high"):
        return "nodata"
    if rainfall_24h < RAIN_THRESHOLD_24H:
        return "no_trigger"
    if hazard_class == "low":
        return "waspada"
    if hazard_class == "medium":
        return "siaga"
    if hazard_class == "high":
        return "bahaya"
    return "nodata"


def classify_arrays(hazard: np.ndarray, rain_24h: np.ndarray) -> np.ndarray:
    """
    Vectorized array classification.
    Inputs:
      hazard: 2D float array (0.0 to 1.0; NaN for nodata)
      rain_24h: 2D float array (mm; NaN for nodata)
    Output:
      categories: 2D uint8 array (0=no_trigger, 1=waspada, 2=siaga, 3=bahaya, 255=nodata)
    """
    if hazard.shape != rain_24h.shape:
        raise ValueError(f"Shape mismatch: hazard {hazard.shape} vs rain {rain_24h.shape}")

    out = np.full(hazard.shape, CODE_NODATA, dtype=np.uint8)

    valid_hazard = np.isfinite(hazard) & (hazard >= 0.0) & (hazard <= 1.0)
    valid_rain = np.isfinite(rain_24h) & (rain_24h >= 0.0)
    valid_both = valid_hazard & valid_rain

    # No trigger (rain < 30.0 mm)
    no_trig = valid_both & (rain_24h < RAIN_THRESHOLD_24H)
    out[no_trig] = CODE_NO_TRIGGER

    # Triggered (rain >= 30.0 mm)
    triggered = valid_both & (rain_24h >= RAIN_THRESHOLD_24H)

    # Classes: Low (<= HAZARD_LOW_MAX), Medium (> HAZARD_LOW_MAX & <= HAZARD_MEDIUM_MAX), High (> HAZARD_MEDIUM_MAX)
    is_low = triggered & (hazard <= HAZARD_LOW_MAX)
    is_med = triggered & (hazard > HAZARD_LOW_MAX) & (hazard <= HAZARD_MEDIUM_MAX)
    is_high = triggered & (hazard > HAZARD_MEDIUM_MAX)

    out[is_low] = CODE_WASPADA
    out[is_med] = CODE_SIAGA
    out[is_high] = CODE_BAHAYA

    return out
