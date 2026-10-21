from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image

from . import config
from .classify import CATEGORY_NAMES, hazard_class_from_index
from .storage import read_json

router = APIRouter(prefix="/api/landslide/forecast", tags=["landslide-experimental"])
RUN_PATTERN = re.compile(r"^\d{8}T\d{2}(?:-[a-f0-9]{16})?$")


def current_manifest(manifest):
    # Never label a publication from the previous hazard method as vulnerability.
    return bool(manifest and manifest.get("method_version") == config.METHOD_VERSION
                and manifest.get("index_type") == "vulnerability"
                and manifest.get("hazard_source", {}).get("source") == config.BNPB_IMAGESERVER_URL)


def run_manifest(run):
    if not RUN_PATTERN.fullmatch(run):
        raise HTTPException(422, "Invalid run")
    manifest = read_json(config.RUNS_DIR / run / "manifest.json")
    if not current_manifest(manifest):
        raise HTTPException(404, "Forecast run unavailable for current vulnerability method")
    return manifest


def step_metadata(manifest, step):
    row = next((r for r in manifest["steps"] if r["step"] == step and r.get("ready")), None)
    if row is None:
        raise HTTPException(404, "Forward 24-hour window unavailable")
    return row


@router.get("/status")
def status():
    manifest = read_json(config.LATEST_PATH)
    available = current_manifest(manifest)
    return {"available": available, "run_id": manifest.get("run_id") if available else None,
            "processing": read_json(config.STATUS_PATH), "hazard_cached": config.BNPB_CACHE_TIF.exists(),
            "experimental": True}


@router.get("/metadata")
def metadata():
    manifest = read_json(config.LATEST_PATH)
    if not current_manifest(manifest):
        raise HTTPException(503, "Data BNPB/ECMWF forward-24h belum tersedia untuk indeks kerentanan")
    return manifest


@router.get("/tile/{run}/{step}/{z}/{x}/{y}")
@router.get("/tile/{run}/{step}/{z}/{x}/{y}.webp")
def tile(run: str, step: int, z: int, x: int, y: int):
    manifest = run_manifest(run)
    step_metadata(manifest, step)
    if not 0 <= z <= 18 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise HTTPException(422, "Invalid tile coordinate")
    path = config.RUNS_DIR / run / "tiles" / str(step) / str(z) / str(x) / f"{y}.webp"
    if not path.exists():
        if not manifest["minzoom"] <= z <= manifest["maxzoom"]:
            raise HTTPException(404, "Zoom unavailable")
        # Valid step, outside product extent only. Missing in-domain tile is an error.
        from .tiles import _tiles_for_bbox
        inside = any(tx == x and ty == y for _, tx, ty in _tiles_for_bbox(*manifest["bbox"], range(z, z+1)))
        if inside:
            raise HTTPException(503, "Forecast tile missing")
        image = BytesIO()
        Image.new("RGBA", (256, 256)).save(image, format="WEBP", lossless=True)
        return Response(image.getvalue(), media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/point")
def point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
          step: int = Query(..., ge=0), run: str | None = None):
    if run is None:
        latest = metadata()
        run = latest.get("publication_id", latest["run_id"])
    manifest = run_manifest(run)
    row = step_metadata(manifest, step)
    path = config.RUNS_DIR / run / f"step_{step:03d}.npz"
    if not path.exists():
        raise HTTPException(503, "Point data unavailable")
    with np.load(path, allow_pickle=False) as data:
        lats, lons = data["lats"], data["lons"]
        code, hazard, rain = 255, None, None
        la, lo = (lats[::-1], lons) if lats[0] > lats[-1] else (lats, lons)
        dy = (la[-1] - la[0]) / (len(la) - 1)
        dx = (lo[-1] - lo[0]) / (len(lo) - 1)
        if la[0] - dy/2 <= lat < la[-1] + dy/2 and lo[0] - dx/2 <= lon < lo[-1] + dx/2:
            fy = (lat - la[0]) / dy
            fx = (lon - lo[0]) / dx
            iy = int(np.floor(fy + 0.5))
            ix = int(np.floor(fx + 0.5))
            row_idx = len(la) - 1 - iy if lats[0] > lats[-1] else iy
            code = int(data["cat"][row_idx, ix])
            h, r = float(data["hazard"][row_idx, ix]), float(data["rain"][row_idx, ix])
            hazard, rain = (h if np.isfinite(h) else None), (r if np.isfinite(r) else None)
    low_max = manifest.get("hazard_low_max", config.HAZARD_LOW_MAX)
    med_max = manifest.get("hazard_medium_max", config.HAZARD_MEDIUM_MAX)
    return {"product": "landslide_potential", "status": "experimental", "model": "ECMWF_IFS",
        "run_id": manifest["run_id"], "publication_id": manifest.get("publication_id", run),
        "run_time": manifest["run_time"], "forecast_step": step,
        "forecast_start": row["forecast_start"], "forecast_end": row["forecast_end"],
        "latitude": lat, "longitude": lon, "rainfall_24h_mm": rain,
        "hazard_index": hazard, "hazard_class": hazard_class_from_index(hazard, low_max=low_max, medium_max=med_max),
        "rainfall_trigger": rain >= manifest["rain_threshold_24h_mm"] if rain is not None else None,
        "rain_threshold_24h_mm": manifest["rain_threshold_24h_mm"],
        "category": CATEGORY_NAMES.get(code, "nodata"), "category_code": code,
        "method_version": manifest["method_version"], "hazard_index_representation": "mean on ECMWF grid",
        "index_type": "vulnerability"}
