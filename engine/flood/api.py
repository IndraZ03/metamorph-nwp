"""Precomputed flood indicators. No source raster processing during requests."""
from io import BytesIO
import re
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image
from engine.landslide.storage import read_json, sha256_file
from engine.landslide.tiles import nearest_sample, _tiles_for_bbox
from . import config, bayuadji, screening, integration

router = APIRouter(prefix="/api/flood/forecast", tags=["flood-experimental"])
PUBLICATION = re.compile(r"^\d{8}T\d{2}-[a-f0-9]{16}$")


def valid_manifest(data):
    return bool(data and data.get("method_version") == config.METHOD_VERSION
        and data.get("product") == "indonesia_flood_potential"
        and all(data.get("indices", {}).get(kind, {}).get("source") == url
            for kind, url in config.SOURCES.items()))


def get_manifest(run=None):
    if run is None:
        data = read_json(config.LATEST_PATH)
        if not valid_manifest(data):
            raise HTTPException(503, "Data banjir ECMWF/InaRISK belum tersedia")
        return data
    if not PUBLICATION.fullmatch(run):
        raise HTTPException(422, "Immutable publication ID required")
    data = read_json(config.RUNS_DIR / run / "manifest.json")
    if not valid_manifest(data) or data.get("publication_id") != run:
        raise HTTPException(404, "Flood publication unavailable")
    return data


def get_step(manifest, step):
    row = next((row for row in manifest["steps"] if row["step"] == step), None)
    if not row or not row.get("ready"):
        raise HTTPException(404, "Trailing 24-hour window incomplete or unavailable")
    return row


@router.get("/status")
def status():
    manifest = read_json(config.LATEST_PATH)
    valid = valid_manifest(manifest)
    available = bool(valid and any(row.get("ready") for row in manifest["steps"]))
    return {"product": "indonesia_flood_potential", "available": available,
        "experimental": True, "run_id": manifest["run_id"] if valid else None,
        "publication_id": manifest["publication_id"] if valid else None,
        "processing": read_json(config.STATUS_PATH),
        "modes": {"screening": "partial" if available else "unavailable",
            "bayuadji": "NOT_CONFIGURED", "integration": "exploratory_indicators"}}


@router.get("/metadata")
def metadata(run: str | None = None):
    return get_manifest(run)


@router.get("/times")
def times(run: str | None = None):
    manifest = get_manifest(run)
    return {"publication_id": manifest["publication_id"], "steps": manifest["steps"]}


@router.get("/model")
def model():
    return {"bayuadji": bayuadji.model_status(), "rainfall": screening.status(),
        "integration": integration.status()}


@router.get("/tile/{run}/{step}/{z}/{x}/{y}.webp")
def tile(run: str, step: int, z: int, x: int, y: int,
         indicator: str = Query("rainfall", pattern="^(rainfall|hazard|vulnerability)$")):
    manifest = get_manifest(run)
    get_step(manifest, step)
    if not 0 <= z <= 18 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise HTTPException(422, "Invalid tile coordinate")
    if not manifest["minzoom"] <= z <= manifest["maxzoom"]:
        raise HTTPException(404, "Zoom unavailable")
    path = config.RUNS_DIR / run / "tiles" / indicator / str(step) / str(z) / str(x) / f"{y}.webp"
    if path.exists():
        return FileResponse(path, media_type="image/webp",
            headers={"Cache-Control": "public, max-age=604800, immutable"})
    inside = any(tx == x and ty == y for _, tx, ty in _tiles_for_bbox(*manifest["bbox"], range(z, z+1)))
    if inside:
        raise HTTPException(503, "Flood tile missing")
    buffer = BytesIO()
    Image.new("RGBA", (256, 256)).save(buffer, format="WEBP", lossless=True)
    return Response(buffer.getvalue(), media_type="image/webp",
        headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/point")
def point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
          step: int = Query(..., ge=0), run: str | None = None):
    if not np.isfinite(lat) or not np.isfinite(lon):
        raise HTTPException(422, "Finite coordinates required")
    manifest = get_manifest(run)
    row = get_step(manifest, step)
    pub = manifest["publication_id"]
    path = config.RUNS_DIR / pub / f"step_{step:03d}.npz"
    if not path.exists() or sha256_file(path) != row.get("data_sha256"):
        raise HTTPException(503, "Point data unavailable or checksum mismatch")
    with np.load(path, allow_pickle=False) as data:
        def sample(key):
            value = float(nearest_sample(data[key], data["lats"], data["lons"],
                np.array(lat), np.array(lon), nodata_val=np.nan))
            return value if np.isfinite(value) else None
        rainfall = sample("rainfall")
        hazard = sample("hazard")
        vulnerability = sample("vulnerability")
        total = sample("antecedent_total")
    return {"product": manifest["product"], "status": "experimental", "model": "ECMWF_IFS",
        "run_id": manifest["run_id"], "publication_id": pub, "run_time": manifest["run_time"],
        "forecast_step": step, "valid_time": row["valid_time"],
        "window_start": row["window_start"], "window_end": row["window_end"],
        "latitude": lat, "longitude": lon, "rainfall_p24_mm": rainfall,
        "rainfall_category": None, "rainfall_category_status": "unverified",
        "antecedent_7d_mm": total, "ar7_weighted_mm": None, "decay_factor": None,
        "ar7_status": "NOT_CONFIGURED", "hazard_index": hazard,
        "vulnerability_index": vulnerability, "indices_classification_status": "unverified",
        "indices_representation": "mean on native ECMWF grid, not local 100 m assessment",
        "bayuadji_model": bayuadji.model_status(), "integration_mode": "exploratory_indicators",
        "completeness": {"p24": rainfall is not None, "antecedent": total is not None,
            "hazard": hazard is not None, "vulnerability": vulnerability is not None},
        "provenance": manifest["provenance"], "sources": manifest["indices"],
        "disclaimer": config.DISCLAIMER}
