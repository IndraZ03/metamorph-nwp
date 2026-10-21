"""Offline independent indicators on native ECMWF grid; immutable publications."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import numpy as np
from rasterio.errors import RasterioError
from engine.landslide.storage import atomic_json, read_json, sha256_file
from engine.landslide.precipitation import load_tp
from engine.landslide.pipeline import align_hazard_to_ecmwf_grid
from . import config, bayuadji, screening, integration
from .rainfall import trailing_p24
from .antecedent import trailing_antecedent
from .tiles import write_tiles


def source_grid(kind, lats, lons):
    empty = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    try:
        meta = read_json(config.SOURCES_DIR / kind / "latest.json")
        if not meta:
            return empty, {"status": "unavailable", "source": config.SOURCES[kind]}
        name = meta.get("file", "")
        if not re.fullmatch(r"[a-f0-9]{64}\.tif", name):
            raise ValueError("Invalid immutable source filename")
        path = config.SOURCES_DIR / kind / name
        if (meta.get("source") != config.SOURCES[kind] or name != f"{meta.get('sha256')}.tif"
                or sha256_file(path) != meta.get("sha256")):
            raise ValueError("Flood source checksum/identity mismatch")
        values = align_hazard_to_ecmwf_grid(path, lats, lons)
        return values, {**meta, "status": "ready", "finite_grid_fraction": float(np.mean(np.isfinite(values))),
            "coverage_note": "Fraction of ECMWF cells with a valid mean; not subcell source coverage"}
    except (OSError, ValueError, TypeError, KeyError, RasterioError) as error:
        return empty, {"status": "invalid", "source": config.SOURCES[kind], "reason": str(error)}


def process_run(run_id):
    if not re.fullmatch(r"\d{8}T\d{2}", run_id):
        raise ValueError("Invalid run ID")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock = config.OUTPUT_DIR / "processing.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        return _process(run_id)
    except Exception as error:
        atomic_json(config.STATUS_PATH, {"state": "failed", "error": str(error)})
        raise
    finally:
        lock.unlink(missing_ok=True)


def _process(run_id):
    root = config.TP_DIR / run_id
    available = sorted(int(p.stem) for p in root.glob("*.json") if p.stem.isdigit())
    if not available:
        raise ValueError("Retained ECMWF precipitation unavailable")
    base = load_tp(root, available[0])
    run = datetime.fromisoformat(base["run_time"])
    if run.strftime("%Y%m%dT%H") != run_id:
        raise ValueError("Run identity mismatch")
    lats, lons = base["lats"], base["lons"]
    for axis in (lats, lons):
        if (len(axis) < 2 or not np.all(np.isfinite(axis))
                or not np.allclose(np.diff(axis), axis[1] - axis[0]) or axis[1] == axis[0]):
            raise ValueError("Regular finite ECMWF grid required")
    if lons[-1] <= lons[0]:
        raise ValueError("Longitude must be ascending")
    hazard, hs = source_grid("hazard", lats, lons)
    vulnerability, vs = source_grid("vulnerability", lats, lons)
    inputs = []
    for step in available:
        data = load_tp(root, step)
        if data["run_time"] != base["run_time"]:
            raise ValueError("Mixed ECMWF runs")
        if not np.array_equal(data["lats"], lats) or not np.array_equal(data["lons"], lons):
            raise ValueError("TP grid changed within run")
        inputs.append({"step": step, "sha256": data["sha256"],
            "metadata_sha256": sha256_file(root / f"{step}.json")})
    signature = {"method": config.METHOD_VERSION, "inputs": inputs, "sources": [hs, vs],
        "bbox": config.BBOX, "zoom": [config.MINZOOM, config.MAXZOOM],
        "grid": [lats.tolist(), lons.tolist()], "model": bayuadji.model_status()}
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]
    pub = f"{run_id}-{digest}"
    target = config.RUNS_DIR / pub
    existing = read_json(target / "manifest.json")
    if existing:
        _publish(existing)
        return existing
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=config.RUNS_DIR, prefix="staging-") as staging:
        stage = Path(staging)
        rows = []
        for step in available:
            valid = run + timedelta(hours=step)
            row = {"step": step, "valid_time": valid.isoformat(),
                "window_start": (valid - timedelta(hours=24)).isoformat(),
                "window_end": valid.isoformat(), "ready": False, "completeness": 0.0}
            try:
                result = trailing_p24(root, step, available)
                if not result["ready"]:
                    row["reason"] = result["reason"]
                    rows.append(row)
                    continue
                rain = result["values"]
                antecedent = trailing_antecedent(root, step, available)
                daily = np.stack([w["values"] if w["ready"] else np.full_like(rain, np.nan)
                    for w in antecedent["daily_windows"]])
                total = daily.sum(axis=0)
                np.savez_compressed(stage / f"step_{step:03d}.npz", lats=lats, lons=lons,
                    rainfall=rain, hazard=hazard, vulnerability=vulnerability, antecedent_daily=daily,
                    antecedent_total=total)
                for kind, field in (("rainfall", rain), ("hazard", hazard), ("vulnerability", vulnerability)):
                    write_tiles(stage, step, kind, field, lats, lons)
                row.update(ready=True, completeness=result["completeness"],
                    antecedent_completeness=antecedent["completeness"],
                    antecedent_complete_pixel_fraction=antecedent["complete_pixel_fraction"],
                    antecedent_windows=[{k: v for k, v in w.items() if k != "values"}
                        for w in antecedent["daily_windows"]],
                    data_sha256=sha256_file(stage / f"step_{step:03d}.npz"))
            except (ValueError, FileNotFoundError) as error:
                row["reason"] = str(error)
            rows.append(row)
        manifest = {"product": "indonesia_flood_potential", "status": "experimental",
            "method_version": config.METHOD_VERSION, "run_id": run_id, "run_time": run.isoformat(),
            "publication_id": pub, "generated_at": datetime.now(timezone.utc).isoformat(),
            "bbox": list(config.BBOX), "minzoom": config.MINZOOM, "maxzoom": config.MAXZOOM,
            "steps": rows, "indices": {"hazard": hs, "vulnerability": vs},
            "rainfall": screening.status(), "models": {"bayuadji": bayuadji.model_status()},
            "integration": integration.status(), "provenance": inputs,
            "display_scales": {"rainfall": [0, 200], "hazard": [0, 1], "vulnerability": [0, 1]},
            "display_note": "Continuous display ramps only; not official category boundaries. Rainfall saturated above 200 mm.",
            "disclaimer": config.DISCLAIMER}
        atomic_json(stage / "manifest.json", manifest)
        os.replace(stage, target)
    _publish(manifest)
    return manifest


def _publish(manifest):
    previous = read_json(config.LATEST_PATH)
    ready = any(row.get("ready") for row in manifest["steps"])
    if ready and (not previous or previous.get("method_version") != config.METHOD_VERSION
            or datetime.fromisoformat(previous["run_time"]) <= datetime.fromisoformat(manifest["run_time"])):
        atomic_json(config.LATEST_PATH, manifest)
    atomic_json(config.STATUS_PATH, {"state": "ready" if ready else "incomplete",
        "publication_id": manifest["publication_id"]})
