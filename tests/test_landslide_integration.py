"""Integration tests for spatial alignment, tile encoding, API endpoints, and publication."""
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from engine.landslide import config
from engine.landslide.pipeline import align_hazard_to_ecmwf_grid
from engine.landslide.tiles import nearest_sample, write_step_tiles
from engine.landslide.processor import process_run
from engine.landslide.storage import atomic_json
from backend.app import app


# ---------------------------------------------------------------------------
# 1. Spatial Alignment & Tie-breaking Tests
# ---------------------------------------------------------------------------

def test_align_hazard_to_ecmwf_grid():
    with tempfile.TemporaryDirectory() as td:
        hazard_tif = Path(td) / "hazard.tif"
        # Create a small Float32 GeoTIFF in EPSG:4326 with 0.5 hazard in center and NaN outside
        transform = from_origin(100.0, -5.0, 0.05, 0.05)
        data = np.full((10, 10), 0.5, dtype=np.float32)
        data[0, :] = np.nan
        with rasterio.open(
            hazard_tif, "w", driver="GTiff", height=10, width=10, count=1,
            dtype="float32", crs="EPSG:4326", transform=transform, nodata=np.nan
        ) as dest:
            dest.write(data, 1)

        # ECMWF grid matching extent
        lats = np.array([-5.1, -5.3, -5.4])  # descending lat
        lons = np.array([100.1, 100.3, 100.4])  # ascending lon

        aligned = align_hazard_to_ecmwf_grid(hazard_tif, lats, lons)
        assert aligned.shape == (3, 3)
        assert np.any(np.isfinite(aligned))
        # Valid values must be clipped between 0.0 and 1.0
        valid = aligned[np.isfinite(aligned)]
        assert np.all((valid >= 0.0) & (valid <= 1.0))


def test_tiles_half_cell_and_tie_breaking():
    # Grid of 2x2 with cells at lats=[10.0, 0.0] and lons=[100.0, 110.0]
    lats = np.array([10.0, 0.0])
    lons = np.array([100.0, 110.0])
    values = np.array([[1, 2], [3, 0]], dtype=np.uint8)

    # Point query inside cell [10.0, 100.0]
    qlat = np.array([10.0, 9.9, 5.0, -6.0])
    qlon = np.array([100.0, 100.1, 105.0, 100.0])
    sampled = nearest_sample(values, lats, lons, qlat, qlon, nodata_val=255)

    assert sampled[0] == 1  # exact center of cell (10, 100)
    assert sampled[1] == 1  # near center
    # Exact halfway at lat=5.0, lon=105.0: tie-breaker chooses northern & eastern cell (top-right = 2)
    assert sampled[2] == 2
    # Outside cell coverage (lat -6.0 < 0.0 - 5.0) -> nodata (255)
    assert sampled[3] == 255


# ---------------------------------------------------------------------------
# 2. End-to-End Processing & Publication
# ---------------------------------------------------------------------------

def test_process_run_and_publication(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out_dir = root / "output" / "landslide"
        runs_dir = out_dir / "runs"
        tp_dir = out_dir / "precipitation"
        hazard_dir = out_dir / "hazard"
        latest_path = out_dir / "latest.json"
        status_path = out_dir / "status.json"
        cache_tif = hazard_dir / "bnpb_vulnerability.tif"
        meta_path = hazard_dir / "bnpb_meta.json"

        monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(config, "RUNS_DIR", runs_dir)
        monkeypatch.setattr(config, "TP_DIR", tp_dir)
        monkeypatch.setattr(config, "HAZARD_DIR", hazard_dir)
        monkeypatch.setattr(config, "LATEST_PATH", latest_path)
        monkeypatch.setattr(config, "STATUS_PATH", status_path)
        monkeypatch.setattr(config, "BNPB_CACHE_TIF", cache_tif)
        monkeypatch.setattr(config, "BNPB_META_PATH", meta_path)

        # 1. Create mock BNPB hazard cache
        hazard_dir.mkdir(parents=True, exist_ok=True)
        transform = from_origin(94.0, 7.0, 0.25, 0.25)
        h_data = np.full((73, 191), 0.7, dtype=np.float32)  # High hazard everywhere
        with rasterio.open(
            cache_tif, "w", driver="GTiff", height=73, width=191, count=1,
            dtype="float32", crs="EPSG:4326", transform=transform, nodata=np.nan
        ) as dest:
            dest.write(h_data, 1)

        atomic_json(meta_path, {
            "source": config.BNPB_IMAGESERVER_URL,
            "fingerprint": "mock_fingerprint",
            "sha256": hashlib.sha256(cache_tif.read_bytes()).hexdigest(),
            "bbox": list(config.BBOX),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })

        # 2. Create mock retained TP for run 20261018T00 (steps 0 and 24)
        run_id = "20261018T00"
        run_dt = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
        tp_run_dir = tp_dir / run_id
        tp_run_dir.mkdir(parents=True, exist_ok=True)

        lats = np.linspace(6.5, -11.5, 73)
        lons = np.linspace(94.0, 141.5, 191)

        def save_tp(step, rain_val):
            npz = tp_run_dir / f"{step}.npz"
            np.savez_compressed(npz, lats=lats, lons=lons, values=np.full((73, 191), rain_val, dtype=np.float32))
            sha = hashlib.sha256(npz.read_bytes()).hexdigest()
            from datetime import timedelta
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

        save_tp(0, 5.0)
        save_tp(24, 85.0)  # diff = 80.0 mm >= 30.0 mm trigger; hazard=0.7 -> High -> Bahaya (code 3)

        # A newer publication from the old source must not block this migration.
        atomic_json(latest_path, {
            "run_id": "20261019T00", "run_time": "2026-10-19T00:00:00Z",
            "method_version": "experimental_v1",
        })
        manifest = process_run(run_id)
        assert manifest["run_id"] == run_id
        assert manifest["publication_id"].startswith(f"{run_id}-")
        assert manifest["status"] == "experimental"
        assert manifest["method_version"] == "experimental_v2_vulnerability"
        assert manifest["index_type"] == "vulnerability"
        assert manifest["hazard_source"]["source"] == config.BNPB_IMAGESERVER_URL

        # Check latest.json updated atomically
        assert latest_path.exists()
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        assert latest["publication_id"] == manifest["publication_id"]

        # Check step 0 is ready
        step0 = next(s for s in manifest["steps"] if s["step"] == 0)
        assert step0["ready"] is True
        assert step0["forecast_start"] == "2026-10-18T00:00:00Z"
        assert step0["forecast_end"] == "2026-10-19T00:00:00Z"

        # Step 3 is explicit unavailable (ready False) because step 27 TP is absent
        step3 = next(s for s in manifest["steps"] if s["step"] == 3)
        assert step3["ready"] is False

        # Verify publication directory contents
        pub_dir = runs_dir / manifest["publication_id"]
        assert (pub_dir / "step_000.npz").exists()
        assert (pub_dir / "step_000.tif").exists()

        # Idempotence: processing the identical run re-publishes existing manifest
        manifest2 = process_run(run_id)
        assert manifest2["publication_id"] == manifest["publication_id"]

        # Matching checksum cannot authorize a cache from the previous source.
        source_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        source_meta["source"] = "https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_BAHAYA_TANAHLONGSOR/ImageServer"
        atomic_json(meta_path, source_meta)
        with pytest.raises(ValueError, match="BNPB cache source mismatch"):
            process_run(run_id)


# ---------------------------------------------------------------------------
# 3. FastAPI Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_status_and_metadata_503(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out_dir = root / "output" / "landslide"
        monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(config, "LATEST_PATH", out_dir / "latest.json")
        monkeypatch.setattr(config, "STATUS_PATH", out_dir / "status.json")
        monkeypatch.setattr(config, "BNPB_CACHE_TIF", out_dir / "hazard" / "bnpb_vulnerability.tif")

        client = TestClient(app)

        # /status when uninitialized
        res = client.get("/api/landslide/forecast/status")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is False
        assert data["experimental"] is True

        # /metadata when uninitialized -> 503
        res = client.get("/api/landslide/forecast/metadata")
        assert res.status_code == 503
        assert "belum tersedia" in res.json()["detail"]


def test_api_tile_and_point_inspection(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out_dir = root / "output" / "landslide"
        runs_dir = out_dir / "runs"
        latest_path = out_dir / "latest.json"
        monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(config, "RUNS_DIR", runs_dir)
        monkeypatch.setattr(config, "LATEST_PATH", latest_path)

        run_id = "20261018T00"
        pub_id = f"{run_id}-a1b2c3d4e5f67890"
        pub_dir = runs_dir / pub_id
        pub_dir.mkdir(parents=True, exist_ok=True)

        lats = np.array([5.0, 0.0, -5.0])
        lons = np.array([100.0, 105.0, 110.0])
        # category Bahaya (3) at (0.0, 105.0)
        cats = np.full((3, 3), 255, dtype=np.uint8)
        cats[1, 1] = 3
        hazard = np.full((3, 3), np.nan, dtype=np.float32)
        hazard[1, 1] = 0.8
        rain = np.full((3, 3), np.nan, dtype=np.float32)
        rain[1, 1] = 50.0

        np.savez_compressed(pub_dir / "step_000.npz", cat=cats, hazard=hazard, rain=rain, lats=lats, lons=lons)

        # Write dummy tile for zoom 3
        tile_dir = pub_dir / "tiles" / "0" / "3" / "6"
        tile_dir.mkdir(parents=True, exist_ok=True)
        (tile_dir / "4.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8X")

        manifest = {
            "product": "landslide_potential",
            "run_id": run_id,
            "publication_id": pub_id,
            "run_time": "2026-10-18T00:00:00Z",
            "method_version": config.METHOD_VERSION,
            "index_type": "vulnerability",
            "hazard_source": {"source": config.BNPB_IMAGESERVER_URL},
            "rain_threshold_24h_mm": 30.0,
            "hazard_low_max": 0.333,
            "hazard_medium_max": 0.666,
            "bbox": [94.0, -11.5, 141.5, 6.5],
            "minzoom": 3,
            "maxzoom": 6,
            "steps": [{
                "step": 0, "ready": True,
                "forecast_start": "2026-10-18T00:00:00Z",
                "forecast_end": "2026-10-19T00:00:00Z"
            }, {
                "step": 3, "ready": False
            }]
        }
        atomic_json(pub_dir / "manifest.json", manifest)
        atomic_json(latest_path, manifest)

        client = TestClient(app)

        # Test metadata
        res = client.get("/api/landslide/forecast/metadata")
        assert res.status_code == 200
        assert res.json()["publication_id"] == pub_id

        # Test point inspection at (lat=0.0, lon=105.0)
        res = client.get("/api/landslide/forecast/point", params={"lat": 0.0, "lon": 105.0, "step": 0})
        assert res.status_code == 200
        pt = res.json()
        assert pt["category"] == "bahaya"
        assert pt["category_code"] == 3
        assert pt["hazard_class"] == "high"
        assert pt["hazard_index"] == pytest.approx(0.8)
        assert pt["rainfall_24h_mm"] == 50.0
        assert pt["rainfall_trigger"] is True
        assert pt["publication_id"] == pub_id
        assert pt["index_type"] == "vulnerability"

        # Test point outside domain
        res = client.get("/api/landslide/forecast/point", params={"lat": 50.0, "lon": 0.0, "step": 0})
        assert res.status_code == 200
        assert res.json()["category"] == "nodata"
        assert res.json()["category_code"] == 255

        # Test point query on unavailable step (step 3) -> 404
        res = client.get("/api/landslide/forecast/point", params={"lat": 0.0, "lon": 105.0, "step": 3})
        assert res.status_code == 404

        # Test tile serving: valid existing tile -> 200
        res = client.get(f"/api/landslide/forecast/tile/{pub_id}/0/3/6/4.webp")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/webp"

        # Test tile out of zoom range -> 404
        res = client.get(f"/api/landslide/forecast/tile/{pub_id}/0/12/100/100.webp")
        assert res.status_code == 404

        # Test tile outside Indonesia bbox at valid zoom (e.g. z=3, x=0, y=0) -> transparent webp
        res = client.get(f"/api/landslide/forecast/tile/{pub_id}/0/3/0/0.webp")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/webp"


@pytest.mark.parametrize("change", [
    {"method_version": "experimental_v1"},
    {"index_type": "hazard"},
    {"hazard_source": {"source": "old-hazard-service"}},
])
def test_api_rejects_previous_source_publications(monkeypatch, tmp_path, change):
    pub_id = "20261018T00-a1b2c3d4e5f67890"
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "LATEST_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(config, "STATUS_PATH", tmp_path / "status.json")
    manifest = {
        "run_id": "20261018T00", "method_version": config.METHOD_VERSION,
        "index_type": "vulnerability", "hazard_source": {"source": config.BNPB_IMAGESERVER_URL},
        **change,
    }
    atomic_json(config.LATEST_PATH, manifest)
    atomic_json(config.RUNS_DIR / pub_id / "manifest.json", manifest)
    client = TestClient(app)
    assert client.get("/api/landslide/forecast/status").json()["available"] is False
    assert client.get("/api/landslide/forecast/metadata").status_code == 503
    assert client.get(f"/api/landslide/forecast/tile/{pub_id}/0/3/6/4.webp").status_code == 404
    assert client.get("/api/landslide/forecast/point", params={
        "run": pub_id, "lat": 0, "lon": 105, "step": 0,
    }).status_code == 404
