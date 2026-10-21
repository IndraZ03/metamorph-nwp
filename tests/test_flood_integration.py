"""Integration tests for flood indicators, API contracts, and publication."""
import hashlib
import json
from pathlib import Path
import tempfile
from datetime import datetime, timezone, timedelta
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from engine.flood import config as flood_config
from engine.flood.processor import process_run
from engine.flood.prune import prune_runs
from engine.landslide.storage import atomic_json
from backend.app import app


def test_api_status_503_when_no_data(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        monkeypatch.setattr(flood_config, "OUTPUT_DIR", root)
        monkeypatch.setattr(flood_config, "RUNS_DIR", root / "runs")
        monkeypatch.setattr(flood_config, "LATEST_PATH", root / "latest.json")
        monkeypatch.setattr(flood_config, "STATUS_PATH", root / "status.json")

        client = TestClient(app)
        res = client.get("/api/flood/forecast/status")
        assert res.status_code == 200
        assert res.json()["available"] is False
        assert res.json()["modes"]["bayuadji"] == "NOT_CONFIGURED"

        res_meta = client.get("/api/flood/forecast/metadata")
        assert res_meta.status_code == 503


@pytest.mark.parametrize("invalid_hazard", [False, True])
def test_process_run_and_api_endpoints(monkeypatch, invalid_hazard):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out_dir = root / "flood"
        runs_dir = out_dir / "runs"
        tp_dir = out_dir / "precipitation"
        sources_dir = out_dir / "sources"
        latest_path = out_dir / "latest.json"
        status_path = out_dir / "status.json"

        monkeypatch.setattr(flood_config, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(flood_config, "RUNS_DIR", runs_dir)
        monkeypatch.setattr(flood_config, "TP_DIR", tp_dir)
        monkeypatch.setattr(flood_config, "SOURCES_DIR", sources_dir)
        monkeypatch.setattr(flood_config, "LATEST_PATH", latest_path)
        monkeypatch.setattr(flood_config, "STATUS_PATH", status_path)

        # 1. Create mock sources (hazard & vulnerability)
        lats = np.linspace(6.5, -11.5, 73)
        lons = np.linspace(94.0, 141.5, 191)

        def make_source(kind, val):
            d = sources_dir / kind
            d.mkdir(parents=True, exist_ok=True)
            # Use 64-char sha-like name
            tif_data = np.full((73, 191), val, dtype=np.float32)
            transform = from_origin(94.0, 6.5, 0.25, 0.25)
            tmp_tif = d / "temp.tif"
            with rasterio.open(
                tmp_tif, "w", driver="GTiff", height=73, width=191, count=1,
                dtype="float32", crs="EPSG:4326", transform=transform, nodata=np.nan
            ) as dst:
                dst.write(tif_data, 1)
            sha = hashlib.sha256(tmp_tif.read_bytes()).hexdigest()
            target_name = f"{sha}.tif"
            target_tif = d / target_name
            tmp_tif.rename(target_tif)
            meta = {
                "source": flood_config.SOURCES[kind],
                "file": target_name,
                "sha256": sha,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json(d / "latest.json", meta)

        make_source("hazard", 0.65)
        make_source("vulnerability", 0.42)
        if invalid_hazard:
            atomic_json(sources_dir / "hazard" / "latest.json", {
                "source": flood_config.SOURCES["hazard"], "file": "../untrusted.tif"})

        # 2. Mock retained TP steps 0 and 24
        run_id = "20261018T00"
        run_dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        tp_run_dir = tp_dir / run_id
        tp_run_dir.mkdir(parents=True, exist_ok=True)

        def save_tp(step, rain_val):
            npz = tp_run_dir / f"{step}.npz"
            np.savez_compressed(npz, lats=lats, lons=lons, values=np.full((73, 191), rain_val, dtype=np.float32))
            sha = hashlib.sha256(npz.read_bytes()).hexdigest()
            meta = {
                "run_time": run_dt.isoformat(),
                "model": "ECMWF_IFS",
                "step": step,
                "start_step": 0,
                "end_step": step,
                "step_type": "accum",
                "step_units": "h",
                "units_stored": "mm",
                "valid_time": (run_dt + timedelta(hours=step)).isoformat(),
                "sha256": sha,
            }
            atomic_json(tp_run_dir / f"{step}.json", meta)

        save_tp(0, 10.0)
        save_tp(24, 60.0)  # trailing P24 = 50.0 mm

        manifest = process_run(run_id)
        assert manifest["run_id"] == run_id
        assert manifest["publication_id"].startswith(f"{run_id}-")
        assert manifest["method_version"] == flood_config.METHOD_VERSION

        # Verify publication directory contents
        pub_id = manifest["publication_id"]
        pub_dir = runs_dir / pub_id
        assert (pub_dir / "step_024.npz").exists()
        assert (pub_dir / "manifest.json").exists()

        step0 = next(s for s in manifest["steps"] if s["step"] == 0)
        assert step0["ready"] is False
        step24 = next(s for s in manifest["steps"] if s["step"] == 24)
        assert step24["ready"] is True
        assert step24["completeness"] == 1.0

        client = TestClient(app)

        # /metadata endpoint
        res = client.get("/api/flood/forecast/metadata")
        assert res.status_code == 200
        assert res.json()["publication_id"] == pub_id

        # /point inspection
        res_pt = client.get("/api/flood/forecast/point", params={"lat": 0.0, "lon": 105.0, "step": 24})
        assert res_pt.status_code == 200
        pt = res_pt.json()
        assert pt["rainfall_p24_mm"] == pytest.approx(50.0)
        assert pt["rainfall_category"] is None
        assert pt["rainfall_category_status"] == "unverified"
        assert pt["bayuadji_model"]["status"] == "NOT_CONFIGURED"
        assert pt["bayuadji_model"]["probability"] is None
        if invalid_hazard:
            assert pt["hazard_index"] is None
            assert manifest["indices"]["hazard"]["status"] == "invalid"
        else:
            assert pt["hazard_index"] == pytest.approx(0.65, abs=0.01)
        assert pt["vulnerability_index"] == pytest.approx(0.42, abs=0.01)
        assert "ECMWF" in pt["disclaimer"]

        # /point on step < 24 returns 404 (incomplete window)
        res_pt_0 = client.get("/api/flood/forecast/point", params={"lat": 0.0, "lon": 105.0, "step": 0})
        assert res_pt_0.status_code == 404

        # /tile endpoint
        res_tile = client.get(f"/api/flood/forecast/tile/{pub_id}/24/4/12/8.webp?indicator=rainfall")
        assert res_tile.status_code == 200
        assert res_tile.headers["content-type"] == "image/webp"

        # Prune dry-run
        summary = prune_runs(keep=1, dry_run=True)
        assert len(summary["kept"]) == 1
        assert summary["dry_run"] is True
        with pytest.raises(ValueError, match="Deletion disabled"):
            prune_runs(keep=1, dry_run=False)


def test_incomplete_publication_preserves_latest(tmp_path, monkeypatch):
    from engine.flood.processor import _publish
    monkeypatch.setattr(flood_config, "LATEST_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(flood_config, "STATUS_PATH", tmp_path / "status.json")
    older = {"publication_id": "older", "method_version": flood_config.METHOD_VERSION,
        "run_time": "2026-10-17T00:00:00+00:00", "steps": [{"ready": True}]}
    _publish(older)
    _publish({**older, "publication_id": "newer", "run_time": "2026-10-18T00:00:00+00:00",
        "steps": [{"ready": False}]})
    assert json.loads(flood_config.LATEST_PATH.read_text())["publication_id"] == "older"
    assert json.loads(flood_config.STATUS_PATH.read_text())["state"] == "incomplete"


def test_processor_rejects_grid_change_before_publication(tmp_path, monkeypatch):
    from engine.flood import processor
    root = tmp_path / "tp" / "20261018T00"
    root.mkdir(parents=True)
    for step in [0, 24]:
        (root / f"{step}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(flood_config, "TP_DIR", tmp_path / "tp")
    base = {"run_time": "2026-10-18T00:00:00+00:00", "lats": np.array([1, 0]),
        "lons": np.array([100, 101]), "sha256": "test"}
    monkeypatch.setattr(processor, "load_tp", lambda _, step:
        {**base, "lons": np.array([100, 102])} if step == 24 else base)
    monkeypatch.setattr(processor, "sha256_file", lambda _: "test")
    monkeypatch.setattr(processor, "source_grid", lambda *_: (None, {}))
    with pytest.raises(ValueError, match="grid changed"):
        processor._process("20261018T00")
