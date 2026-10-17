from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from . import config
from .colormaps import colorize

log = logging.getLogger("ecmwf.tiles")


def _mercator_lonlat(z: int, x: int, y: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2**z
    px = (x * size + (np.arange(size, dtype=np.float64) + 0.5)) / (n * size)
    py = (y * size + (np.arange(size, dtype=np.float64) + 0.5)) / (n * size)
    lon = px * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * py))))
    lon2d, lat2d = np.meshgrid(lon, lat)
    return lon2d, lat2d


def _tiles_for_bbox(west, south, east, north, zooms: range):
    try:
        import mercantile

        for z in zooms:
            for t in mercantile.tiles(west, south, east, north, [z]):
                yield t.z, t.x, t.y
        return
    except ImportError:
        pass

    def lon_to_x(lon, z):
        return int(math.floor((lon + 180.0) / 360.0 * (1 << z)))

    def lat_to_y(lat, z):
        lat = max(min(lat, 85.05112878), -85.05112878)
        s = math.sin(math.radians(lat))
        return int(math.floor((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * (1 << z)))

    for z in zooms:
        x0 = lon_to_x(west, z)
        x1 = lon_to_x(east, z)
        y0 = lat_to_y(north, z)
        y1 = lat_to_y(south, z)
        n = 1 << z
        for x in range(max(0, x0), min(n, x1 + 1)):
            for y in range(max(0, y0), min(n, y1 + 1)):
                yield z, x, y


def bilinear_sample(values: np.ndarray, lats: np.ndarray, lons: np.ndarray, qlat, qlon) -> np.ndarray:
    """Vectorized bilinear sample. Out-of-grid → nan."""
    v = np.asarray(values, dtype=np.float64)
    la = np.asarray(lats, dtype=np.float64)
    lo = np.asarray(lons, dtype=np.float64)
    if la[0] > la[-1]:
        la = la[::-1]
        v = v[::-1, :]

    nlat, nlon = v.shape
    lat0, lat1 = la[0], la[-1]
    lon0, lon1 = lo[0], lo[-1]
    fy = (qlat - lat0) / (lat1 - lat0) * (nlat - 1)
    fx = (qlon - lon0) / (lon1 - lon0) * (nlon - 1)

    outside = (qlat < min(lat0, lat1)) | (qlat > max(lat0, lat1)) | (qlon < lon0) | (qlon > lon1)

    y0 = np.floor(fy).astype(np.int32)
    x0 = np.floor(fx).astype(np.int32)
    y0 = np.clip(y0, 0, nlat - 2)
    x0 = np.clip(x0, 0, nlon - 2)
    y1 = y0 + 1
    x1 = x0 + 1
    wy = fy - y0
    wx = fx - x0

    v00 = v[y0, x0]
    v10 = v[y1, x0]
    v01 = v[y0, x1]
    v11 = v[y1, x1]
    sampled = v00 * (1 - wy) * (1 - wx) + v10 * wy * (1 - wx) + v01 * (1 - wy) * wx + v11 * wy * wx
    sampled = np.where(outside, np.nan, sampled)
    return sampled


def write_var_tiles(run_dir: Path, var_id: str, step: int, field: dict) -> int:
    west, south, east, north = config.BBOX
    dest_root = run_dir / var_id / str(step)
    staging = run_dir / ".tmp" / var_id / str(step)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    lats = field["lats"]
    lons = field["lons"]
    values = field["values"]
    count = 0

    for z, x, y in _tiles_for_bbox(west, south, east, north, range(config.MINZOOM, config.MAXZOOM + 1)):
        lon2d, lat2d = _mercator_lonlat(z, x, y, config.TILE_SIZE)
        sampled = bilinear_sample(values, lats, lons, lat2d, lon2d)
        rgba = colorize(sampled, var_id)
        img = Image.fromarray(rgba, mode="RGBA")
        out = staging / str(z) / str(x)
        out.mkdir(parents=True, exist_ok=True)
        img.save(
            out / f"{y}.webp",
            format="WEBP",
            quality=config.WEBP_QUALITY,
            method=config.WEBP_METHOD,
        )
        count += 1

    dest_root.parent.mkdir(parents=True, exist_ok=True)
    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.move(str(staging), str(dest_root))
    return count


def write_step_tiles(run_dir: Path, step: int, fields: dict[str, dict]) -> list[str]:
    ready = []
    for var_id, field in fields.items():
        n = write_var_tiles(run_dir, var_id, step, field)
        log.info("tiles %s step=%s count=%s", var_id, step, n)
        ready.append(var_id)
    tmp = run_dir / ".tmp"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    return ready
