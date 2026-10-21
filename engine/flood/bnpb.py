"""Reusable raster ingestion for BNPB layers."""
import hashlib
import json
import logging
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import tempfile
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from rasterio.windows import Window, bounds as window_bounds
from engine.landslide.hazard import session, metadata, fingerprint, export_chunk
from engine.landslide.storage import atomic_json, read_json, sha256_file

log = logging.getLogger("flood.bnpb")


def ingest_layer(source_url, cache_tif, meta_path, bbox, layer_type="hazard",
                 chunk_size=1024, force=False, max_age_days=30):
    if chunk_size < 1:
        raise ValueError("Chunk size must be positive")
    directory = Path(cache_tif).parent
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "ingest.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        return _ingest_layer(source_url, cache_tif, meta_path, bbox, layer_type,
            chunk_size, force, max_age_days)
    finally:
        lock.unlink(missing_ok=True)


def _ingest_layer(source_url, cache_tif, meta_path, bbox, layer_type="hazard",
                  chunk_size=1024, force=False, max_age_days=30):
    cache_tif = Path(cache_tif)
    meta_path = Path(meta_path)
    if chunk_size < 1:
        raise ValueError("Chunk size must be positive")
    cache_tif.parent.mkdir(parents=True, exist_ok=True)
    client = session()
    data = metadata(client, source_url=source_url)
    signature = fingerprint(data)
    previous = read_json(meta_path)
    if previous:
        import re
        name = previous.get("file", "")
        if re.fullmatch(r"[a-f0-9]{64}\.tif", name):
            cache_tif = cache_tif.parent / name
    if previous and cache_tif.exists() and not force:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(previous["checked_at"])
        if (previous.get("source") == source_url and previous.get("fingerprint") == signature
                and previous.get("bbox") == list(bbox) and 0 <= age.days < max_age_days
                and cache_tif.name == f"{previous.get('sha256')}.tif"
                and sha256_file(cache_tif) == previous.get("sha256")):
            return cache_tif
    extent = data["extent"]
    crs = extent["spatialReference"].get("latestWkid") or extent["spatialReference"]["wkid"]
    west, south, east, north = transform_bounds("EPSG:4326", f"EPSG:{crs}", *bbox, densify_pts=21)
    resolution = float(data["pixelSizeX"])
    if resolution <= 0 or abs(float(data["pixelSizeY"]) - resolution) > 0.01:
        raise ValueError("Unsupported source resolution")
    west = max(extent["xmin"], extent["xmin"] + math.floor((west - extent["xmin"]) / resolution) * resolution)
    east = min(extent["xmax"], extent["xmin"] + math.ceil((east - extent["xmin"]) / resolution) * resolution)
    north = min(extent["ymax"], extent["ymax"] - math.floor((extent["ymax"] - north) / resolution) * resolution)
    south = max(extent["ymin"], extent["ymax"] - math.ceil((extent["ymax"] - south) / resolution) * resolution)
    width, height = round((east - west) / resolution), round((north - south) / resolution)
    if width <= 0 or height <= 0:
        raise ValueError("AOI outside BNPB coverage")
    chunk_size = min(chunk_size, int(data.get("maxImageWidth", 1024)), int(data.get("maxImageHeight", 1024)))
    transform = from_origin(west, north, resolution, resolution)
    with tempfile.TemporaryDirectory(dir=cache_tif.parent, prefix="ingest-") as staging:
        output = Path(staging) / f"{layer_type}.tif"
        with rasterio.open(output, "w", driver="GTiff", width=width, height=height, count=1,
                           dtype="float32", crs=f"EPSG:{crs}", transform=transform, nodata=np.nan,
                           tiled=True, blockxsize=256, blockysize=256, compress="deflate", BIGTIFF="IF_SAFER") as dest:
            for row in range(0, height, chunk_size):
                for col in range(0, width, chunk_size):
                    w, h = min(chunk_size, width - col), min(chunk_size, height - row)
                    window = Window(col, row, w, h)
                    with tempfile.TemporaryDirectory(prefix="bnpb-download-") as download:
                        values = export_chunk(client, window_bounds(window, transform), w, h, crs, download, source_url=source_url)
                    dest.write(values, 1, window=window)
            dest.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.nearest)
        sha = hashlib.sha256()
        with output.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(block)
        cache_tif = cache_tif.parent / f"{sha.hexdigest()}.tif"
        if not cache_tif.exists():
            output.replace(cache_tif)
        atomic_json(meta_path, {"source": source_url, "file": cache_tif.name, "fingerprint": signature, "sha256": sha.hexdigest(),
            "metadata": data, "bbox": list(bbox), "checked_at": datetime.now(timezone.utc).isoformat(),
            "layer_type": layer_type, "classification_status": "unverified",
            "license": "No license supplied by service metadata; check BNPB terms before redistribution"})
    return cache_tif


def smoke_test_raw_export(source_url, output_dir):
    """Smoke test raw Float32 TIFF export without saving to permanent cache."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    client = session()
    data = metadata(client, source_url=source_url)
    crs = data["extent"]["spatialReference"].get("latestWkid") or data["extent"]["spatialReference"]["wkid"]
    bbox = [106.0, -7.0, 107.0, -6.0]
    west, south, east, north = transform_bounds("EPSG:4326", f"EPSG:{crs}", *bbox)
    with tempfile.TemporaryDirectory(dir=out_path) as tmp:
        values = export_chunk(client, (west, south, east, north), 10, 10, crs, tmp, source_url=source_url)
    return {"status": "ok", "shape": list(values.shape), "dtype": str(values.dtype),
        "valid_finite_fraction": float(np.mean(np.isfinite(values)))}
