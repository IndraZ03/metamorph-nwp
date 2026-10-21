"""Unit tests for temporal, rainfall, classification, and provenance validation."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import numpy as np
import pytest

from engine.landslide import config
from engine.landslide.classify import (
    classify_landslide,
    classify_arrays,
    hazard_class_from_index,
    CATEGORY_NAMES,
)
from engine.landslide.rainfall import (
    compute_forward_rainfall,
    find_forward_step,
    get_forward_window_info,
)
from engine.landslide.precipitation import (
    unit_factor,
    load_tp,
    forward_window,
)
from engine.landslide.storage import atomic_json


# ---------------------------------------------------------------------------
# 1. Classification & Boundary Tests
# ---------------------------------------------------------------------------

def test_hazard_class_from_index_boundaries():
    assert hazard_class_from_index(0.0) == "low"
    assert hazard_class_from_index(0.333) == "low"
    assert hazard_class_from_index(0.3330001) == "medium"
    assert hazard_class_from_index(0.666) == "medium"
    assert hazard_class_from_index(0.6660001) == "high"
    assert hazard_class_from_index(1.0) == "high"

    # Out of range and invalid
    assert hazard_class_from_index(-0.001) == "nodata"
    assert hazard_class_from_index(1.001) == "nodata"
    assert hazard_class_from_index(None) == "nodata"
    assert hazard_class_from_index(float("nan")) == "nodata"
    assert hazard_class_from_index(float("inf")) == "nodata"


def test_classify_landslide_boundaries():
    # Rain < 30.0 mm -> no_trigger ONLY when hazard class is valid
    assert classify_landslide("low", 0.0) == "no_trigger"
    assert classify_landslide("low", 29.99) == "no_trigger"
    assert classify_landslide("medium", 29.999) == "no_trigger"
    assert classify_landslide("high", 15.0) == "no_trigger"

    # Critical requirement: Invalid hazard with low rain MUST NOT be no_trigger!
    assert classify_landslide(None, 10.0) == "nodata"
    assert classify_landslide("nodata", 10.0) == "nodata"
    assert classify_landslide("invalid", 10.0) == "nodata"

    # Triggered: Rain >= 30.0 mm
    assert classify_landslide("low", 30.0) == "waspada"
    assert classify_landslide("low", 30.01) == "waspada"
    assert classify_landslide("medium", 30.0) == "siaga"
    assert classify_landslide("medium", 55.0) == "siaga"
    assert classify_landslide("high", 30.0) == "bahaya"
    assert classify_landslide("high", 120.0) == "bahaya"

    # Invalid rain inputs
    assert classify_landslide("high", None) == "nodata"
    assert classify_landslide("high", float("nan")) == "nodata"
    assert classify_landslide("high", -1.0) == "nodata"


def test_classify_arrays_vectorized():
    # Shape mismatch raises ValueError
    with pytest.raises(ValueError, match="Shape mismatch"):
        classify_arrays(np.zeros((2, 2)), np.zeros((3, 3)))

    hazard = np.array([
        [0.1, 0.333, 0.3331],
        [0.5, 0.666, 0.6661],
        [1.0, np.nan, -0.5],
        [0.8, 0.2, 0.5]
    ], dtype=np.float32)

    rain = np.array([
        [29.9, 30.0, 30.0],    # no_trigger, waspada, siaga
        [10.0, 30.0, 30.0],    # no_trigger, siaga, bahaya
        [80.0, 80.0, 10.0],    # bahaya, nodata, nodata (invalid hazard)
        [np.nan, -5.0, 29.99]  # nodata, nodata, no_trigger
    ], dtype=np.float32)

    cats = classify_arrays(hazard, rain)
    assert cats.shape == hazard.shape
    assert cats.dtype == np.uint8

    assert cats[0, 0] == config.CODE_NO_TRIGGER
    assert cats[0, 1] == config.CODE_WASPADA
    assert cats[0, 2] == config.CODE_SIAGA

    assert cats[1, 0] == config.CODE_NO_TRIGGER
    assert cats[1, 1] == config.CODE_SIAGA
    assert cats[1, 2] == config.CODE_BAHAYA

    assert cats[2, 0] == config.CODE_BAHAYA
    assert cats[2, 1] == config.CODE_NODATA   # hazard is NaN
    assert cats[2, 2] == config.CODE_NODATA   # hazard is negative (-0.5)

    assert cats[3, 0] == config.CODE_NODATA   # rain is NaN
    assert cats[3, 1] == config.CODE_NODATA   # rain is negative (-5.0)
    assert cats[3, 2] == config.CODE_NO_TRIGGER


# ---------------------------------------------------------------------------
# 2. Forward Rainfall Calculation
# ---------------------------------------------------------------------------

def test_compute_forward_rainfall_spec_example():
    """Specification requires: TP(+3)=5mm and TP(+27)=85mm produces 80mm."""
    s = np.array([[5.0]], dtype=np.float32)
    e = np.array([[85.0]], dtype=np.float32)
    diff = compute_forward_rainfall(s, e, unit="mm")
    assert np.isclose(diff[0, 0], 80.0)


def test_compute_forward_rainfall_units():
    # In meters: 0.005 m and 0.085 m -> 80.0 mm
    s = np.array([[0.005]], dtype=np.float32)
    e = np.array([[0.085]], dtype=np.float32)
    diff = compute_forward_rainfall(s, e, unit="m")
    assert np.isclose(diff[0, 0], 80.0)

    # Unsupported unit
    with pytest.raises(ValueError, match="Unsupported precipitation unit"):
        compute_forward_rainfall(s, e, unit="inches")


def test_compute_forward_rainfall_missing_and_resets():
    # Missing in start or end propagates NaN, never 0
    s = np.array([[5.0, np.nan, 10.0, -2.0]], dtype=np.float32)
    e = np.array([[np.nan, 20.0, 5.0, 10.0]], dtype=np.float32)

    diff = compute_forward_rainfall(s, e, unit="mm")
    assert np.isnan(diff[0, 0])  # end is NaN
    assert np.isnan(diff[0, 1])  # start is NaN
    assert np.isnan(diff[0, 2])  # 5.0 - 10.0 = -5.0 (reset/anomalous negative -> NaN)
    assert np.isnan(diff[0, 3])  # start is negative (-2.0) -> NaN


def test_get_forward_window_info():
    t_utc = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
    info = get_forward_window_info(t_utc, 3, 24)
    assert info["forecast_step"] == 3
    assert info["target_step"] == 27
    assert info["forecast_start"] == "2026-10-18T03:00:00Z"
    assert info["forecast_end"] == "2026-10-19T03:00:00Z"

    # Naive datetime rejected
    with pytest.raises(ValueError, match="explicit timezone"):
        get_forward_window_info(datetime(2026, 10, 18, 0, 0), 3, 24)

    # Negative step rejected
    with pytest.raises(ValueError, match="Invalid forecast window"):
        get_forward_window_info(t_utc, -1, 24)


def test_find_forward_step():
    steps = [0, 3, 6, 24, 27, 48]
    assert find_forward_step(steps, 0, 24) == 24
    assert find_forward_step(steps, 3, 24) == 27
    assert find_forward_step(steps, 6, 24) is None  # 30 not in steps


# ---------------------------------------------------------------------------
# 3. Provenance & Accumulation Continuity Tests
# ---------------------------------------------------------------------------

def test_unit_factor():
    assert unit_factor("m") == 1000.0
    assert unit_factor("m of water equivalent") == 1000.0
    assert unit_factor("mm") == 1.0
    assert unit_factor("kg m**-2") == 1.0
    assert unit_factor("kg m-2") == 1.0
    assert unit_factor("kg m^-2") == 1.0
    with pytest.raises(ValueError):
        unit_factor("unknown_unit")


def _save_mock_tp(root: Path, step: int, start_step: int, end_step: int, run_dt: datetime,
                  lats: np.ndarray, lons: np.ndarray, values: np.ndarray):
    root.mkdir(parents=True, exist_ok=True)
    npz_path = root / f"{step}.npz"
    np.savez_compressed(npz_path, lats=lats, lons=lons, values=values)
    sha256 = hashlib.sha256(npz_path.read_bytes()).hexdigest()

    from datetime import timedelta
    meta = {
        "run_time": run_dt.isoformat(),
        "model": "ECMWF_IFS",
        "step": step,
        "start_step": start_step,
        "end_step": end_step,
        "step_type": "accum",
        "step_units": "h",
        "units_stored": "mm",
        "valid_time": (run_dt + timedelta(hours=step)).isoformat(),
        "sha256": sha256,
    }
    atomic_json(root / f"{step}.json", meta)


def test_load_tp_checksum_and_shape_validation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])
        values = np.zeros((2, 2), dtype=np.float32)

        _save_mock_tp(root, 3, 0, 3, dt, lats, lons, values)

        # Normal load
        loaded = load_tp(root, 3)
        assert loaded["step"] == 3

        # Corrupt data -> Checksum mismatch
        npz_path = root / "3.npz"
        npz_path.write_bytes(b"corrupted bytes")
        with pytest.raises(ValueError, match="checksum mismatch"):
            load_tp(root, 3)

        # Shape disagreement
        _save_mock_tp(root, 6, 0, 6, dt, lats, lons, np.zeros((3, 3), dtype=np.float32))
        with pytest.raises(ValueError, match="shape disagrees with coordinates"):
            load_tp(root, 6)


def test_forward_window_cumulative_success():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])

        # Baseline: step 3 has 5.0 mm accumulated since step 0
        _save_mock_tp(root, 3, 0, 3, dt, lats, lons, np.full((2, 2), 5.0, dtype=np.float32))
        # Target: step 27 has 85.0 mm accumulated since step 0
        _save_mock_tp(root, 27, 0, 27, dt, lats, lons, np.full((2, 2), 85.0, dtype=np.float32))

        rain, base = forward_window(root, 3, [3, 27])
        assert base["step"] == 3
        assert np.allclose(rain, 80.0)


def test_forward_window_missing_endpoint_or_baseline():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])

        _save_mock_tp(root, 3, 0, 3, dt, lats, lons, np.full((2, 2), 5.0, dtype=np.float32))

        # Missing target endpoint
        with pytest.raises(ValueError, match="Missing endpoint"):
            forward_window(root, 3, [3])

        # Endpoint exists; only baseline is missing.
        _save_mock_tp(root, 30, 0, 30, dt, lats, lons, np.full((2, 2), 85.0, dtype=np.float32))
        with pytest.raises(ValueError, match="Missing baseline"):
            forward_window(root, 6, [30])


def test_forward_window_mixed_runs_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt1 = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])

        _save_mock_tp(root, 0, 0, 0, dt1, lats, lons, np.zeros((2, 2), dtype=np.float32))
        _save_mock_tp(root, 24, 0, 24, dt2, lats, lons, np.full((2, 2), 50.0, dtype=np.float32))

        with pytest.raises(ValueError, match="Mixed ECMWF runs"):
            forward_window(root, 0, [0, 24])


def test_forward_window_incremental_continuity():
    """Test summing contiguous incremental intervals: [0..6] + [6..12] + [12..24] = [0..24]."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])

        # Non-zero start_step indicates incremental mode
        _save_mock_tp(root, 0, 0, 0, dt, lats, lons, np.zeros((2, 2), dtype=np.float32))
        _save_mock_tp(root, 6, 0, 6, dt, lats, lons, np.full((2, 2), 10.0, dtype=np.float32))
        _save_mock_tp(root, 12, 6, 12, dt, lats, lons, np.full((2, 2), 20.0, dtype=np.float32))
        _save_mock_tp(root, 24, 12, 24, dt, lats, lons, np.full((2, 2), 30.0, dtype=np.float32))

        rain, base = forward_window(root, 0, [0, 6, 12, 24])
        # 10 + 20 + 30 = 60
        assert np.allclose(rain, 60.0)


def test_forward_window_incremental_gap_or_overlap():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        lats = np.array([1.0, 0.0])
        lons = np.array([100.0, 101.0])

        # Gap: 0..6, then 9..24 (gap between 6 and 9)
        _save_mock_tp(root, 0, 0, 0, dt, lats, lons, np.zeros((2, 2), dtype=np.float32))
        _save_mock_tp(root, 6, 0, 6, dt, lats, lons, np.full((2, 2), 10.0, dtype=np.float32))
        _save_mock_tp(root, 24, 9, 24, dt, lats, lons, np.full((2, 2), 30.0, dtype=np.float32))

        with pytest.raises(ValueError, match="intervals overlap or contain gaps"):
            forward_window(root, 0, [0, 6, 24])
