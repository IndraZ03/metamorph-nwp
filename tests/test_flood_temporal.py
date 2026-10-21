"""Temporal tests for trailing P24 and 7-day antecedent."""
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import numpy as np
import pytest
from engine.landslide.precipitation import explicit_window
from engine.landslide.storage import atomic_json
from engine.flood.rainfall import trailing_p24
from engine.flood.antecedent import trailing_antecedent


def test_trailing_p24_requires_24h_accumulation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        meta = {"run_time": "2026-10-18T00:00:00Z", "model": "ECMWF_IFS", "step": 12,
            "start_step": 0, "end_step": 12, "step_type": "accum", "step_units": "h",
            "units_stored": "mm", "valid_time": "2026-10-18T12:00:00Z", "sha256": "dummy"}
        npz = root / "12.npz"
        np.savez_compressed(npz, lats=[0.0], lons=[100.0], values=[[5.0]])
        import hashlib
        meta["sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
        atomic_json(root / "12.json", meta)

        res = trailing_p24(root, 12, [12])
        assert res["ready"] is False
        assert res["completeness"] == 0.0
        assert "at least 24 hours" in res["reason"]


def test_explicit_window_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="Invalid precipitation window"):
        explicit_window(Path("."), 24, 12, [12, 24])


def test_trailing_antecedent_non_overlap_with_p24():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        meta = {"run_time": "2026-10-18T00:00:00Z", "model": "ECMWF_IFS", "step": 24,
            "start_step": 0, "end_step": 24, "step_type": "accum", "step_units": "h",
            "units_stored": "mm", "valid_time": "2026-10-19T00:00:00Z", "sha256": "dummy"}
        npz = root / "24.npz"
        np.savez_compressed(npz, lats=[0.0], lons=[100.0], values=[[5.0]])
        import hashlib
        meta["sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
        atomic_json(root / "24.json", meta)

        # For step 24, P24 is (0, 24]. Antecedent needs (t-192, 0] which requires historical adapter
        res = trailing_antecedent(root, 24, [24])
        assert res["status"] == "incomplete"
        assert res["completeness"] == 0.0
        assert res["ar7_weighted_mm"] is None


def save_tp(root, step, start, values, **overrides):
    run = datetime(2026, 10, 18, tzinfo=timezone.utc)
    path = root / f"{step}.npz"
    np.savez_compressed(path, lats=[0.0], lons=[100.0, 101.0],
        values=np.broadcast_to(np.asarray(values, dtype=np.float32), (1, 2)))
    meta = {"run_time": run.isoformat(), "valid_time": (run + timedelta(hours=step)).isoformat(),
        "step": step, "start_step": start, "end_step": step, "step_type": "accum",
        "step_units": "h", "units_stored": "mm", "model": "ECMWF_IFS",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **overrides}
    atomic_json(root / f"{step}.json", meta)


def test_trailing_cumulative_no_intermediate_outputs_or_double_conversion(tmp_path):
    save_tp(tmp_path, 24, 0, 10)
    save_tp(tmp_path, 48, 0, [40, np.nan])
    result = trailing_p24(tmp_path, 48, [24, 48])
    assert result["values"][0, 0] == 30
    assert np.isnan(result["values"][0, 1])
    assert result["completeness"] == 0.5
    assert result["window_start"].startswith("2026-10-19T00")
    assert result["window_end"].startswith("2026-10-20T00")


def test_trailing_irregular_incremental_without_baseline(tmp_path):
    for end, start, value in [(3, 0, 1), (15, 3, 2), (24, 15, 4)]:
        save_tp(tmp_path, end, start, value)
    result = trailing_p24(tmp_path, 24, [3, 15, 24])
    np.testing.assert_array_equal(result["values"], [[7, 7]])


@pytest.mark.parametrize("start", [2, 4])
def test_incremental_overlap_and_gap_rejected(tmp_path, start):
    save_tp(tmp_path, 3, 0, 1)
    save_tp(tmp_path, 24, start, 4)
    with pytest.raises(ValueError, match="overlap or contain gaps"):
        trailing_p24(tmp_path, 24, [3, 24])


@pytest.mark.parametrize("change", [
    {"run_time": "2026-10-17T00:00:00+00:00"},
    {"units_stored": "m"}, {"step_units": "3"},
])
def test_mixed_run_and_unverified_units_rejected(tmp_path, change):
    save_tp(tmp_path, 0, 0, 0)
    save_tp(tmp_path, 24, 0, 5, **change)
    with pytest.raises(ValueError):
        trailing_p24(tmp_path, 24, [0, 24])


def test_cumulative_reset_not_silently_zero(tmp_path):
    save_tp(tmp_path, 24, 0, 20)
    save_tp(tmp_path, 48, 0, 10)
    with pytest.raises(ValueError, match="entirely NoData"):
        trailing_p24(tmp_path, 48, [24, 48])


def test_full_antecedent_excludes_p24_and_tracks_pixel_completeness(tmp_path):
    for step in range(0, 193, 24):
        save_tp(tmp_path, step, 0, step)
    result = trailing_antecedent(tmp_path, 192, list(range(0, 193, 24)))
    assert result["status"] == "complete"
    assert result["complete_pixel_fraction"] == 1
    assert result["daily_windows"][0]["end_step"] == 168
    assert result["daily_windows"][-1]["start_step"] == 0
    assert sum(w["values"][0, 0] for w in result["daily_windows"]) == 168
    assert result["ar7_weighted_mm"] is None
    save_tp(tmp_path, 48, 0, [48, np.nan])
    partial = trailing_antecedent(tmp_path, 192, list(range(0, 193, 24)))
    assert partial["completeness"] == 1
    assert partial["complete_pixel_fraction"] == 0.5
    assert partial["status"] == "incomplete"


def test_unverified_history_adapter_rejected(tmp_path):
    with pytest.raises(ValueError, match="Historical adapter unsupported"):
        trailing_antecedent(tmp_path, 24, [], history_adapter=lambda *_: np.ones((1, 2)))
