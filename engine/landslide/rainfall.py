from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

log = logging.getLogger("landslide.rainfall")


def find_forward_step(available_steps: list[int], start_step: int, horizon_hours: int = 24) -> int | None:
    """
    Find exact forecast step for start_step + horizon_hours.
    Returns None if the end step is not in available_steps.
    """
    target = start_step + horizon_hours
    return target if target in available_steps else None


def compute_forward_rainfall(
    tp_start: np.ndarray,
    tp_end: np.ndarray,
    unit: str = "mm",
) -> np.ndarray:
    """
    Compute forward 24-hour rainfall:
      R24_forward(t) = TP(t + 24) - TP(t)

    Validates:
      - Shape match
      - Unit conversion if meters
      - No negative accumulation (clip to >= 0 or NaN if corrupted)
      - Propagate NaNs (never treat missing as zero)
    """
    if tp_start.shape != tp_end.shape:
        raise ValueError(f"Shape mismatch: {tp_start.shape} vs {tp_end.shape}")

    s = np.asarray(tp_start, dtype=np.float64)
    e = np.asarray(tp_end, dtype=np.float64)

    from .precipitation import unit_factor
    factor = unit_factor(unit)
    s = np.where(np.isfinite(s) & (s >= 0), s * factor, np.nan)
    e = np.where(np.isfinite(e) & (e >= 0), e * factor, np.nan)

    # If either start or end is NaN, the result MUST be NaN (missing != 0)
    diff = e - s

    # Physical validation: negative rainfall is impossible for accumulated TP in same run
    # Only float rounding noise up to 1e-5 mm is clipped; resets become NoData.
    anomalous = np.isfinite(diff) & (diff < -1e-5)
    if np.any(anomalous):
        log.warning("Detected %d grid cells with negative forward rainfall; setting to NaN", int(np.sum(anomalous)))
        diff = np.where(anomalous, np.nan, diff)

    diff = np.where(np.isfinite(diff), np.clip(diff, 0.0, None), np.nan)
    return diff.astype(np.float32)


def get_forward_window_info(run_time: datetime, step: int, horizon_hours: int = 24) -> dict:
    """
    Calculate ISO timestamp window for the forward period [step, step + horizon_hours].
    Always stored in UTC.
    """
    if run_time.tzinfo is None:
        raise ValueError("Run time must have an explicit timezone")
    if step < 0 or horizon_hours <= 0:
        raise ValueError("Invalid forecast window")
    run_time = run_time.astimezone(timezone.utc)

    from datetime import timedelta
    start_dt = run_time + timedelta(hours=step)
    end_dt = run_time + timedelta(hours=step + horizon_hours)

    return {
        "run_time": run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecast_step": step,
        "forecast_horizon_hours": horizon_hours,
        "target_step": step + horizon_hours,
        "forecast_start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecast_end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
