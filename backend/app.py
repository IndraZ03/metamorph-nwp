import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .engine.config import TILES_DIR
from .engine.manifest import (
    get_global_manifest_path,
    get_manifest_path,
    list_saved_runs,
)

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
def get_tile(run: str, param: str, step: str, z: int, x: int, y: int):
    """
    Serve pre-rendered WebP tile for MapLibre/Leaflet.
    Fast path direct from disk with immutable client cache.
    """
    tile_path = TILES_DIR / run / param / step / str(z) / str(x) / f"{y}.webp"
    if not tile_path.exists():
        # Return 1x1 transparent WebP to avoid 404 console noise in map viewer
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
