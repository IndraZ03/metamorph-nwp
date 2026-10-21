"""Retain TP from existing ECMWF decoder, with GRIB time/accumulation provenance."""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timedelta, timezone

import numpy as np

from . import config
from .storage import atomic_json


def grib_tp_metadata(path):
    import eccodes as ec
    found = []
    with open(path, "rb") as stream:
        while True:
            handle = ec.codes_grib_new_from_file(stream)
            if handle is None:
                break
            try:
                if ec.codes_get(handle, "shortName") != "tp":
                    continue
                def get(key, default=None):
                    try:
                        return ec.codes_get(handle, key)
                    except ec.CodesInternalError:
                        return default
                run = datetime.strptime(f"{get('dataDate')}{int(get('dataTime')):04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                found.append({"run_time": run.isoformat(), "units": get("units"),
                    "step_type": get("stepType"), "start_step": get("startStep"),
                    "end_step": get("endStep"), "step_units": str(get("stepUnits")),
                    "stream": get("marsStream"), "grid_type": get("gridType")})
            finally:
                ec.codes_release(handle)
    if len(found) != 1:
        raise ValueError("Expected exactly one ECMWF TP message per forecast step")
    return found[0]


def unit_factor(unit):
    unit = str(unit).strip().lower()
    if unit in ("m", "m of water equivalent"):
        return 1000.0
    if unit in ("mm", "kg m**-2", "kg m-2", "kg m^-2"):
        return 1.0
    raise ValueError(f"Unsupported precipitation unit: {unit}")


def retain_tp(run_id, run_time, step, field, grib_path):
    provenance = grib_tp_metadata(grib_path)
    actual_run = datetime.fromisoformat(provenance["run_time"])
    if actual_run != run_time or provenance["end_step"] != step:
        raise ValueError("ECMWF TP run/step mismatch")
    if provenance["step_type"] != "accum" or provenance["step_units"] not in ("1", "h"):
        raise ValueError("TP must have accumulated intervals expressed in hours")
    # Decoder supplies mm, conversion already validated against GRIB units.
    unit_factor(provenance["units"])
    if provenance["start_step"] is None or not 0 <= provenance["start_step"] <= step:
        raise ValueError("Invalid TP accumulation interval")
    root = config.TP_DIR / run_id
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{step}.npz"
    fd, temp = tempfile.mkstemp(dir=root, suffix=".npz")
    os.close(fd)
    try:
        np.savez_compressed(temp, lats=field["lats"], lons=field["lons"], values=field["values"])
        os.replace(temp, target)
    finally:
        from pathlib import Path
        Path(temp).unlink(missing_ok=True)
    provenance.update({"sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "step": step, "units_stored": "mm", "model": "ECMWF_IFS",
        "valid_time": (run_time + timedelta(hours=step)).isoformat()})
    atomic_json(root / f"{step}.json", provenance)


def load_tp(root, step):
    from .storage import read_json
    info = read_json(root / f"{step}.json")
    if not info:
        raise ValueError(f"Missing TP metadata +{step}")
    path = root / f"{step}.npz"
    if not info.get("sha256") or hashlib.sha256(path.read_bytes()).hexdigest() != info["sha256"]:
        raise ValueError("TP data/metadata checksum mismatch")
    if info.get("step") != step:
        raise ValueError("TP filename disagrees with metadata step")
    with np.load(path, allow_pickle=False) as source:
        row = {**info, **{key: source[key] for key in ("lats", "lons", "values")}}
    if row["values"].shape != (len(row["lats"]), len(row["lons"])):
        raise ValueError("TP shape disagrees with coordinates")
    return row


def forward_window(root, start, available):
    """Preserve landslide forward-24h contract."""
    return explicit_window(root, start, start + 24, available)


def explicit_window(root, start, end, available, require_baseline=True):
    """Exact same-run endpoint difference or gap-free incremental interval sum."""
    from .rainfall import compute_forward_rainfall
    if not 0 <= start < end:
        raise ValueError("Invalid precipitation window")
    if end not in available:
        raise ValueError(f"Missing endpoint +{end}")
    target = load_tp(root, end)
    base = load_tp(root, start) if start in available else None
    has_baseline = base is not None
    if base is None:
        if require_baseline:
            raise ValueError(f"Missing baseline +{start}; never infer zero")
        base = target  # Reference metadata only, never an inferred zero accumulation.
    def validate(row):
        if row["run_time"] != base["run_time"] or row["model"] != "ECMWF_IFS":
            raise ValueError("Mixed ECMWF runs")
        if row.get("step_type") != "accum" or row.get("units_stored") != "mm":
            raise ValueError("Unverified TP accumulation")
        if row["end_step"] != row["step"] or row["step_units"] not in ("1", "h"):
            raise ValueError("Invalid interval metadata")
        if not 0 <= row["start_step"] <= row["end_step"]:
            raise ValueError("Invalid accumulation bounds")
        run = datetime.fromisoformat(row["run_time"])
        if run.tzinfo is None:
            raise ValueError("TP run timezone missing")
        if datetime.fromisoformat(row["valid_time"]) != run + timedelta(hours=row["step"]):
            raise ValueError("Invalid TP valid time")
        if not np.array_equal(row["lats"], base["lats"]) or not np.array_equal(row["lons"], base["lons"]):
            raise ValueError("TP grid changed within run")
    validate(base)
    validate(target)
    if has_baseline and base["start_step"] == target["start_step"] and base["start_step"] <= start:
        rain = compute_forward_rainfall(base["values"], target["values"])
    else:
        rows = [load_tp(root, step) for step in sorted(available) if start < step <= end]
        cursor = start
        rain = np.zeros_like(base["values"], dtype=np.float64)
        for row in rows:
            validate(row)
            if row["start_step"] != cursor or row["end_step"] <= cursor:
                raise ValueError("TP intervals overlap or contain gaps")
            values = row["values"]
            if np.any(np.isfinite(values) & (values < 0)):
                raise ValueError("Negative incremental TP")
            rain += values
            cursor = row["end_step"]
        if cursor != end:
            raise ValueError("Incomplete forward interval")
    if not np.any(np.isfinite(rain)):
        raise ValueError("Forward rainfall entirely NoData")
    return rain.astype(np.float32), base
