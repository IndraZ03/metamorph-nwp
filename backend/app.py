import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .engine.config import NUMERIC_TILES_DIR, PARAMETERS, TILES_DIR
from .engine.geocoder import get_geocoder
from .engine.manifest import (
    get_global_manifest_path,
    get_manifest_path,
    list_saved_runs,
)
from .engine.sampler import load_grid_from_disk, sample_point_value

app = FastAPI(
    title="Metamorph NWP — ICON Engine API",
    description="Realtime WebP tile serving & metadata for DWD ICON (Indonesia Domain)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from engine.landslide.api import router as landslide_router

app.include_router(landslide_router)

from engine.flood.api import router as flood_router

app.include_router(flood_router)

# 1x1 transparent WebP fallback
TRANSPARENT_WEBP = (
    b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0e\x00\x00\x00/g\x00\x00\x00\x04\x88\x88\x08\x00"
)


@app.get("/health")
def health():
    return {"status": "ok", "model": "ICON-Global", "domain": "Indonesia"}


@app.get("/api/icon/runs")
def get_runs():
    """List all available run IDs on disk."""
    runs = list_saved_runs()
    return {"runs": runs}


@app.get("/api/icon/manifest")
def get_latest_manifest():
    """Get metadata manifest for the latest processed run."""
    manifest_path = get_global_manifest_path()
    if not manifest_path.exists():
        runs = list_saved_runs()
        if runs:
            manifest_path = get_manifest_path(runs[0])
        else:
            raise HTTPException(status_code=404, detail="No ICON runs processed yet.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/icon/manifest/{run_id}")
def get_run_manifest(run_id: str):
    """Get metadata manifest for a specific run."""
    manifest_path = get_manifest_path(run_id)
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/icon/tiles/{run}/{param}/{step}/{z}/{x}/{y}.webp")
def get_visual_tile(run: str, param: str, step: str, z: int, x: int, y: int):
    """
    Serve pre-rendered visual WebP tile for MapLibre/Leaflet.
    Fast path direct from disk with immutable client cache.
    """
    tile_path = TILES_DIR / run / param / step / str(z) / str(x) / f"{y}.webp"
    if not tile_path.exists():
        return Response(
            content=TRANSPARENT_WEBP,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    return FileResponse(
        path=str(tile_path),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.get("/api/icon/tiles-numeric/{run}/{param}/{step}/{z}/{x}/{y}.webp")
def get_numeric_tile(run: str, param: str, step: str, z: int, x: int, y: int):
    """
    Serve RGB-encoded numeric WebP tile (lossless) for zero-latency client-side inspection.
    Formula: val = ((R * 65536 + G * 256 + B) / 10.0) - 1000.0
    """
    tile_path = NUMERIC_TILES_DIR / run / param / step / str(z) / str(x) / f"{y}.webp"
    if not tile_path.exists():
        return Response(
            content=TRANSPARENT_WEBP,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    return FileResponse(
        path=str(tile_path),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.get("/api/icon/point")
def get_point_popup(
    lat: float = Query(..., description="Latitude (-15 to 12)"),
    lon: float = Query(..., description="Longitude (88 to 148)"),
    step: str = Query("000", description="Forecast step e.g. 000, 001"),
    run: Optional[str] = Query(None, description="Model run ID e.g. 2026101700"),
    param: Optional[str] = Query("all", description="Parameter ID (or 'all' for all 7 parameters)"),
):
    """
    Point sampling API for map click popup.
    Returns:
      - Tanggal (Run time, Valid time UTC & WIB formatted)
      - Koordinat (Lat, Lon)
      - Lokasi (Kecamatan, Kabupaten/Kota, Provinsi, Negara)
      - Nilai (Parameter values & units)
    """
    # 1. Resolve run_id
    if not run:
        runs = list_saved_runs()
        if not runs:
            raise HTTPException(status_code=404, detail="No processed ICON runs available.")
        run = runs[0]

    step_str = f"{int(step):03d}" if step.isdigit() else step
    step_int = int(step_str)

    # 2. Compute timestamps
    try:
        run_dt = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        valid_dt = run_dt + timedelta(hours=step_int)
        run_time_iso = run_dt.strftime("%Y-%m-%dT%H:%M:00Z")
        valid_time_iso = valid_dt.strftime("%Y-%m-%dT%H:%M:00Z")
        # WIB format: UTC + 7
        wib_dt = valid_dt + timedelta(hours=7)
        bulan_indo = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        tanggal_wib = f"{wib_dt.day} {bulan_indo[wib_dt.month]} {wib_dt.year}, {wib_dt.strftime('%H:%M')} WIB"
    except Exception:
        run_time_iso = run
        valid_time_iso = "-"
        tanggal_wib = "-"

    # 3. Resolve location (Kecamatan, Kabupaten/Kota, Provinsi)
    geocoder = get_geocoder()
    lokasi = geocoder.resolve(lat, lon)

    # 4. Sample numeric weather values
    params_to_query = list(PARAMETERS.keys()) if param == "all" else [param]
    nilai_dict = {}

    for p in params_to_query:
        if p not in PARAMETERS:
            continue
        p_cfg = PARAMETERS[p]
        grid_2d = load_grid_from_disk(run, p, step_str)
        val = sample_point_value(grid_2d, lat, lon) if grid_2d is not None else None
        nilai_dict[p] = {
            "name": p_cfg["name"],
            "value": val,
            "unit": p_cfg["unit"],
            "is_accum": p_cfg["is_accum"],
        }

    return {
        "status": "success",
        "run_id": run,
        "run_time": run_time_iso,
        "valid_time": valid_time_iso,
        "tanggal": tanggal_wib,
        "koordinat": {
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
        },
        "lokasi": {
            "kecamatan": lokasi.get("kecamatan", "-"),
            "kabupaten_kota": lokasi.get("kabupaten_kota", "-"),
            "provinsi": lokasi.get("provinsi", "-"),
            "negara": lokasi.get("negara", "Indonesia"),
            "display_name": lokasi.get("display_name", f"{lat:.4f}, {lon:.4f}"),
        },
        "nilai": nilai_dict,
    }
