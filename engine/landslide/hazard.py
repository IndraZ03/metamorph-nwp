"""Chunked raw Float32 exports; source cache never depends on forecast time."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from rasterio.windows import Window, bounds as window_bounds
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config
from .storage import atomic_json, read_json

log = logging.getLogger("landslide.hazard")


def session():
    client = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], respect_retry_after_header=True)
    client.mount("https://", HTTPAdapter(max_retries=retries))
    return client


def metadata(client=None, source_url=None):
    client = client or session()
    response = client.get(source_url or config.BNPB_IMAGESERVER_URL, params={"f": "json"}, timeout=(10, 60))
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"BNPB metadata: {data['error']}")
    if data.get("pixelType") != "F32" or data.get("bandCount") != 1:
        raise ValueError("BNPB source must be single-band Float32")
    if not data.get("extent", {}).get("spatialReference"):
        raise ValueError("BNPB CRS missing")
    return data


def fingerprint(data):
    # Hash full service metadata, including any service update timestamp.
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def export_chunk(client, bbox, width, height, crs, directory, source_url=None):
    response = client.get((source_url or config.BNPB_IMAGESERVER_URL) + "/exportImage", params={
        "f": "image", "bbox": ",".join(map(str, bbox)), "bboxSR": crs,
        "imageSR": crs, "size": f"{width},{height}", "format": "tiff",
        "pixelType": "F32", "interpolation": "RSP_NearestNeighbor",
        "renderingRule": json.dumps({"rasterFunction": "None"}),
        "noDataInterpretation": "esriNoDataMatchAny",
    }, timeout=(10, 120), stream=True)
    # Bound download memory and disk independently of response Content-Length.
    path = Path(directory) / "source.tif"
    limit = width * height * 8 + 1024 * 1024
    try:
        response.raise_for_status()
        received = 0
        with path.open("wb") as stream:
            for block in response.iter_content(chunk_size=65536):
                received += len(block)
                if received > limit:
                    raise ValueError("BNPB export exceeds bounded raster payload")
                stream.write(block)
    finally:
        response.close()
    with rasterio.open(path) as source:
        if source.count != 1 or source.dtypes[0] != "float32" or source.crs != rasterio.crs.CRS.from_epsg(crs):
            raise ValueError("Export is not raw Float32 raster in requested CRS")
        if (source.width, source.height) != (width, height):
            raise ValueError("BNPB changed requested export dimensions")
        expected = rasterio.transform.from_bounds(*bbox, width, height)
        if not source.transform.almost_equals(expected, precision=0.01):
            raise ValueError("BNPB export georeferencing mismatch")
        raw = source.read(1)
        # Server exports Float32 with ESRI NoData sentinel (-3.4028235e+38) without GDAL_NODATA tag.
        nodata_mask = (raw <= -1e30) | (~np.isfinite(raw)) | (source.read_masks(1) == 0)
        values = np.where(nodata_mask, np.nan, raw).astype(np.float32)
        valid = values[np.isfinite(values)]
        if valid.size and (valid.min() < -1e-5 or valid.max() > 1.0001):
            raise ValueError("BNPB raw index outside 0..1")
        return np.clip(values, 0.0, 1.0)


def ingest(bbox=config.BBOX, chunk_size=1024, force=False, max_age_days=30):
    if chunk_size < 1:
        raise ValueError("Chunk size must be positive")
    config.HAZARD_DIR.mkdir(parents=True, exist_ok=True)
    client = session()
    data = metadata(client)
    signature = fingerprint(data)
    previous = read_json(config.BNPB_META_PATH)
    if previous and config.BNPB_CACHE_TIF.exists() and not force:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(previous["checked_at"])
        if (previous.get("source") == config.BNPB_IMAGESERVER_URL
                and previous.get("fingerprint") == signature and previous.get("bbox") == list(bbox)
                and age.days < max_age_days):
            return config.BNPB_CACHE_TIF
    extent = data["extent"]
    crs = extent["spatialReference"].get("latestWkid") or extent["spatialReference"]["wkid"]
    west, south, east, north = transform_bounds("EPSG:4326", f"EPSG:{crs}", *bbox, densify_pts=21)
    # Snap to source grid, clip to true source extent.
    resolution = float(data["pixelSizeX"])
    if resolution <= 0 or abs(float(data["pixelSizeY"]) - resolution) > 0.01:
        raise ValueError("Unsupported BNPB source grid")
    west = max(extent["xmin"], extent["xmin"] + math.floor((west - extent["xmin"]) / resolution) * resolution)
    east = min(extent["xmax"], extent["xmin"] + math.ceil((east - extent["xmin"]) / resolution) * resolution)
    north = min(extent["ymax"], extent["ymax"] - math.floor((extent["ymax"] - north) / resolution) * resolution)
    south = max(extent["ymin"], extent["ymax"] - math.ceil((extent["ymax"] - south) / resolution) * resolution)
    width, height = round((east - west) / resolution), round((north - south) / resolution)
    if width <= 0 or height <= 0:
        raise ValueError("AOI outside BNPB coverage")
    chunk_size = min(chunk_size, int(data.get("maxImageWidth", 1024)), int(data.get("maxImageHeight", 1024)))
    transform = from_origin(west, north, resolution, resolution)
    # Separate empty staging directory; previous valid cache survives all failures.
    with tempfile.TemporaryDirectory(dir=config.HAZARD_DIR, prefix="ingest-") as staging:
        output = Path(staging) / "hazard.tif"
        with rasterio.open(output, "w", driver="GTiff", width=width, height=height, count=1,
                           dtype="float32", crs=f"EPSG:{crs}", transform=transform, nodata=np.nan,
                           tiled=True, blockxsize=256, blockysize=256, compress="deflate", BIGTIFF="IF_SAFER") as dest:
            for row in range(0, height, chunk_size):
                for col in range(0, width, chunk_size):
                    w, h = min(chunk_size, width-col), min(chunk_size, height-row)
                    window = Window(col, row, w, h)
                    with tempfile.TemporaryDirectory(prefix="bnpb-download-") as download:
                        values = export_chunk(client, window_bounds(window, transform), w, h, crs, download)
                    dest.write(values, 1, window=window)
                    log.info("BNPB chunk row=%s col=%s", row, col)
            dest.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.nearest)
        sha = hashlib.sha256()
        with output.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(block)
        output.replace(config.BNPB_CACHE_TIF)
        atomic_json(config.BNPB_META_PATH, {"source": config.BNPB_IMAGESERVER_URL,
            "fingerprint": signature, "sha256": sha.hexdigest(), "metadata": data,
            "bbox": list(bbox), "checked_at": datetime.now(timezone.utc).isoformat(),
            "index_type": "vulnerability",
            "class_boundaries": "provisional; see forecast publication thresholds; official methodology not confirmed",
            "license": "No license supplied by service metadata; check BNPB terms before redistribution"})
    return config.BNPB_CACHE_TIF
