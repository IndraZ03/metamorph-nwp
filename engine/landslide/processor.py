"""Offline, staged processor; browser requests never run raster calculations."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from . import config
from .classify import classify_arrays
from .pipeline import align_hazard_to_ecmwf_grid
from .precipitation import forward_window
from .rainfall import get_forward_window_info
from .storage import atomic_json, read_json, sha256_file
from .tiles import write_step_tiles


def _publish(manifest):
    previous = read_json(config.LATEST_PATH)
    same_source = (previous and previous.get("method_version") == manifest["method_version"]
                   and previous.get("index_type") == manifest["index_type"]
                   and previous.get("hazard_source", {}).get("source") == manifest["hazard_source"]["source"])
    if not same_source or datetime.fromisoformat(previous["run_time"]) <= datetime.fromisoformat(manifest["run_time"]):
        atomic_json(config.LATEST_PATH, manifest)
    atomic_json(config.STATUS_PATH, {"state": "ready", "run_id": manifest["run_id"],
                "publication_id": manifest["publication_id"], "checked_at": datetime.now(timezone.utc).isoformat()})


def process_run(run_id):
    if not re.fullmatch(r"\d{8}T\d{2}", run_id):
        raise ValueError("Invalid ECMWF run ID")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock = config.OUTPUT_DIR / "processing.lock"
    # Fail closed if another process is publishing. Crash leftovers require operator review.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        return _process_run(run_id)
    except Exception as error:
        atomic_json(config.STATUS_PATH, {"state": "failed", "attempted_run": run_id,
                    "error": str(error), "checked_at": datetime.now(timezone.utc).isoformat()})
        raise
    finally:
        lock.unlink(missing_ok=True)


def _process_run(run_id):
    if not config.BNPB_CACHE_TIF.exists():
        raise FileNotFoundError("BNPB cache missing; run python -m engine.landslide.run ingest")
    hazard_source = read_json(config.BNPB_META_PATH)
    if not hazard_source or hazard_source.get("sha256") != sha256_file(config.BNPB_CACHE_TIF):
        raise ValueError("BNPB cache/metadata checksum mismatch; ingest cache again")
    if hazard_source.get("source") != config.BNPB_IMAGESERVER_URL:
        raise ValueError("BNPB cache source mismatch; ingest vulnerability cache again")
    root = config.TP_DIR / run_id
    available = sorted(int(p.stem) for p in root.glob("*.json")
                       if p.stem.isdigit() and (root / f"{p.stem}.npz").exists())
    if not available:
        raise ValueError("No retained ECMWF TP; rebuild existing ECMWF pipeline with --force")
    # Expected ECMWF start times through +72. Missing starts are explicit, not omitted.
    starts = sorted(set(range(0, config.MAX_FORECAST_START + 1, 3)) |
                    {s for s in available if s <= config.MAX_FORECAST_START})
    windows, unavailable = {}, []
    for step in starts:
        try:
            windows[step] = forward_window(root, step, available)
        except (ValueError, FileNotFoundError) as error:
            unavailable.append({"step": step, "ready": False, "reason": str(error)})
    if not windows:
        raise ValueError("No complete forward-24h windows")
    first = next(iter(windows.values()))[1]
    lats, lons = first["lats"], first["lons"]
    run_time = datetime.fromisoformat(first["run_time"])
    if run_time.tzinfo is None or run_id != run_time.strftime("%Y%m%dT%H"):
        raise ValueError("Run directory disagrees with TP metadata")
    if len(lats) < 2 or len(lons) < 2 or not np.all(np.isfinite(lats)) or not np.all(np.isfinite(lons)):
        raise ValueError("Invalid ECMWF coordinates")
    if not np.all(np.diff(lons) > 0) or not (np.all(np.diff(lats) > 0) or np.all(np.diff(lats) < 0)):
        raise ValueError("Unsupported ECMWF grid orientation")
    if not np.allclose(np.diff(lats), np.diff(lats)[0]) or not np.allclose(np.diff(lons), np.diff(lons)[0]):
        raise ValueError("ECMWF grid must be regular")
    for rain, base in windows.values():
        if (base["run_time"] != first["run_time"] or not np.array_equal(lats, base["lats"])
                or not np.array_equal(lons, base["lons"]) or rain.shape != (len(lats), len(lons))):
            raise ValueError("Mixed grids/runs across forecast windows")
    hazard = align_hazard_to_ecmwf_grid(config.BNPB_CACHE_TIF, lats, lons)
    if not np.any(np.isfinite(hazard)):
        raise ValueError("BNPB has no valid overlap with ECMWF grid")
    signature = {"method": config.METHOD_VERSION, "hazard_source": hazard_source,
        "tp_provenance": {p.stem: read_json(p) for p in sorted(root.glob("*.json"))
                          if p.stem.isdigit() and int(p.stem) in available},
        "hazard_grid_sha256": hashlib.sha256(hazard.tobytes()).hexdigest(),
        "coordinates_sha256": hashlib.sha256(lats.tobytes()+lons.tobytes()).hexdigest(),
        "tp_hashes": {str(s): hashlib.sha256(r.tobytes()).hexdigest() for s, (r, _) in windows.items()},
        "unavailable": unavailable, "rain_threshold": config.RAIN_THRESHOLD_24H,
        "hazard_thresholds": [config.HAZARD_LOW_MAX, config.HAZARD_MEDIUM_MAX],
        "bbox": config.BBOX, "zooms": [config.MINZOOM, config.MAXZOOM]}
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]
    publication_id = f"{run_id}-{digest}"
    destination = config.RUNS_DIR / publication_id
    existing = read_json(destination / "manifest.json")
    if existing:
        _publish(existing)
        return existing
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    dx, dy = abs(lons[1]-lons[0]), abs(lats[1]-lats[0])
    transform = from_origin(lons.min()-dx/2, lats.max()+dy/2, dx, dy)
    with tempfile.TemporaryDirectory(dir=config.RUNS_DIR, prefix="processing-") as staging:
        dest = Path(staging) / "run"
        dest.mkdir()
        rows = []
        for step, (rain, _) in windows.items():
            categories = classify_arrays(hazard, rain)
            np.savez_compressed(dest / f"step_{step:03d}.npz", cat=categories, rain=rain,
                                hazard=hazard, lats=lats, lons=lons)
            oriented = categories if lats[0] > lats[-1] else categories[::-1]
            with rasterio.open(dest / f"step_{step:03d}.tif", "w", driver="GTiff", height=len(lats),
                               width=len(lons), count=1, dtype="uint8", crs="EPSG:4326",
                               transform=transform, nodata=255, compress="deflate") as raster:
                raster.write(oriented, 1)
                factors = [f for f in [2, 4] if min(len(lats), len(lons)) // f >= 1]
                if factors:
                    raster.build_overviews(factors, rasterio.enums.Resampling.nearest)
            count = write_step_tiles(dest / "tiles", step, {"lats": lats, "lons": lons, "values": categories},
                                     minzoom=config.MINZOOM, maxzoom=config.MAXZOOM)
            rows.append({**get_forward_window_info(run_time, step), "step": step, "ready": True, "tiles_count": count})
        manifest = {"product": "landslide_potential", "title": "Prakiraan Potensi Tanah Longsor — Eksperimental",
            "status": "experimental", "model": "ECMWF_IFS", "run_id": run_id, "publication_id": publication_id,
            "run_time": run_time.isoformat(), "method_version": config.METHOD_VERSION,
            "index_type": "vulnerability",
            "rain_threshold_24h_mm": config.RAIN_THRESHOLD_24H, "hazard_class_boundaries_provisional": True,
            "hazard_low_max": config.HAZARD_LOW_MAX, "hazard_medium_max": config.HAZARD_MEDIUM_MAX,
            "hazard_resampling": "average valid index to ECMWF grid; classes applied after aggregation",
            "rain_resampling": "none; native ECMWF grid", "category_resampling": "nearest",
            "bbox": list(config.BBOX), "minzoom": config.MINZOOM, "maxzoom": config.MAXZOOM,
            "tile_url": "/api/landslide/forecast/tile/{run}/{step}/{z}/{x}/{y}.webp",
            "steps": sorted(rows + unavailable, key=lambda row: row["step"]), "signature": signature,
            "hazard_source": hazard_source,
            "rainfall_reference": "Yuniawan et al. (2022), Geosciences 12(3),129; doi:10.3390/geosciences12030129",
            "attribution": "BNPB InaRISK (Kerentanan) × ECMWF IFS; BNPB redistribution terms require verification",
            "limitations": "Daily rainfall baseline adapted to forward rolling 24h; not validated or official warning. No trigger does not mean safe. Vulnerability index is not probability. Grid means hide subgrid extremes.",
            "generated_at": datetime.now(timezone.utc).isoformat()}
        atomic_json(dest / "manifest.json", manifest)
        shutil.move(str(dest), str(destination))
    _publish(manifest)
    return manifest
