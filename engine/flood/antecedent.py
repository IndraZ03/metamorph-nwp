"""Seven daily windows preceding P24: (t-192, t-24]. No overlap with R0."""
from datetime import datetime, timedelta
import numpy as np
from engine.landslide.precipitation import explicit_window, load_tp


def trailing_antecedent(root, step, available, history_adapter=None):
    """Raw forecast antecedent only; unverified external history is rejected."""
    if history_adapter is not None:
        raise ValueError("Historical adapter unsupported until time/grid/units/quality/provenance validation exists")
    row = load_tp(root, step)
    run = datetime.fromisoformat(row["run_time"])
    windows = []
    for day in range(1, 8):
        end = step - 24 - (day - 1) * 24
        start = end - 24
        window = {"day": day, "start_step": start, "end_step": end,
            "start_time": (run + timedelta(hours=start)).isoformat(),
            "end_time": (run + timedelta(hours=end)).isoformat(),
            "values": None, "ready": False, "finite_fraction": 0.0}
        if start < 0:
            window["reason"] = "Verified historical input unavailable"
        else:
            try:
                rain, _ = explicit_window(root, start, end, available, require_baseline=False)
                window.update(values=rain, ready=True, finite_fraction=float(np.mean(np.isfinite(rain))))
            except (ValueError, FileNotFoundError) as error:
                window["reason"] = str(error)
        windows.append(window)
    temporal = sum(w["ready"] for w in windows) / 7.0
    complete_pixels = np.ones_like(row["values"], dtype=bool)
    for window in windows:
        complete_pixels &= np.isfinite(window["values"]) if window["ready"] else False
    pixel_fraction = float(np.mean(complete_pixels))
    return {"status": "complete" if temporal == 1.0 and pixel_fraction == 1.0 else "incomplete",
        "ar7_weighted_mm": None, "decay_factor": None, "completeness": temporal,
        "complete_pixel_fraction": pixel_fraction, "daily_windows": windows,
        "reason": "AR7 decay factor not verified from primary literature"}
