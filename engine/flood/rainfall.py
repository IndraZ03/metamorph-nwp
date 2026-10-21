"""Trailing 24-hour rainfall over (t-24, t]. Never infer zero for missing data."""
from datetime import datetime, timedelta
import numpy as np
from engine.landslide.precipitation import explicit_window, load_tp


def trailing_p24(root, step, available):
    if step < 24:
        row = load_tp(root, step)
        return {"ready": False, "reason": "Requires at least 24 hours of forecast accumulation",
            "values": None, "completeness": 0.0, "step": step,
            "window_start": None, "window_end": row["valid_time"]}
    start = step - 24
    values, base = explicit_window(root, start, step, available, require_baseline=False)
    run = datetime.fromisoformat(base["run_time"])
    finite = np.isfinite(values)
    completeness = float(np.mean(finite)) if values.size else 0.0
    return {"ready": True, "values": values, "completeness": completeness, "step": step,
        "window_start": (run + timedelta(hours=start)).isoformat(),
        "window_end": (run + timedelta(hours=step)).isoformat()}
