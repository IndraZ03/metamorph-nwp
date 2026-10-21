from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from . import config

log = logging.getLogger("landslide.tiles")


def _mercator_lonlat(z: int, x: int, y: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2**z
    px = (x * size + (np.arange(size, dtype=np.float64) + 0.5)) / (n * size)
    py = (y * size + (np.arange(size, dtype=np.float64) + 0.5)) / (n * size)
    lon = px * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * py))))
    lon2d, lat2d = np.meshgrid(lon, lat)
    return lon2d, lat2d


def _tiles_for_bbox(west: float, south: float, east: float, north: float, zooms: range):
    try:
        import mercantile

        for z in zooms:
            for t in mercantile.tiles(west, south, east, north, [z]):
                yield t.z, t.x, t.y
        return
    except ImportError:
        pass

    for z in zooms:
        x0 = int(math.floor((west + 180.0) / 360.0 * (1 << z)))
        x1 = int(math.floor((east + 180.0) / 360.0 * (1 << z)))
        s0 = math.sin(math.radians(max(min(north, 85.05112878), -85.05112878)))
        y0 = int(math.floor((0.5 - math.log((1 + s0) / (1 - s0)) / (4 * math.pi)) * (1 << z)))
        s1 = math.sin(math.radians(max(min(south, 85.05112878), -85.05112878)))
        y1 = int(math.floor((0.5 - math.log((1 + s1) / (1 - s1)) / (4 * math.pi)) * (1 << z)))
        n = 1 << z
        for x in range(max(0, x0), min(n, x1 + 1)):
            for y in range(max(0, y0), min(n, y1 + 1)):
                yield z, x, y


def nearest_sample(
    values: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    qlat: np.ndarray,
    qlon: np.ndarray,
    nodata_val: int = 255,
) -> np.ndarray:
    """
    Vectorized nearest-neighbor sample for categorical raster data.
    """
    v = np.asarray(values)
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

    dy, dx = (lat1-lat0)/(nlat-1), (lon1-lon0)/(nlon-1)
    outside = ((qlat < lat0-dy/2) | (qlat >= lat1+dy/2)
               | (qlon < lon0-dx/2) | (qlon >= lon1+dx/2)
               | ~np.isfinite(qlat) | ~np.isfinite(qlon))

    # Half-open cells; exact ties choose northern/eastern center, for tiles and points.
    iy = np.floor(np.where(np.isfinite(fy), fy, 0) + 0.5).astype(np.int32)
    ix = np.floor(np.where(np.isfinite(fx), fx, 0) + 0.5).astype(np.int32)

    iy = np.clip(iy, 0, nlat - 1)
    ix = np.clip(ix, 0, nlon - 1)

    sampled = v[iy, ix]
    sampled = np.where(outside, nodata_val, sampled)
    return sampled.astype(v.dtype)


def colorize_categories(cat_array: np.ndarray) -> np.ndarray:
    """
    Map categorical array (0, 1, 2, 3, 255) to RGBA uint8 image.
    0: Transparent (no trigger)
    1: Waspada #EAB308 (234, 179, 8, 255)
    2: Siaga   #F97316 (249, 115, 22, 255)
    3: Bahaya  #DC2626 (220, 38, 38, 255)
    255: NoData Transparent (0, 0, 0, 0)
    """
    h, w = cat_array.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # 1 - Waspada
    m1 = cat_array == config.CODE_WASPADA
    rgba[m1] = config.COLOR_TABLE[config.CODE_WASPADA]

    # 2 - Siaga
    m2 = cat_array == config.CODE_SIAGA
    rgba[m2] = config.COLOR_TABLE[config.CODE_SIAGA]

    # 3 - Bahaya
    m3 = cat_array == config.CODE_BAHAYA
    rgba[m3] = config.COLOR_TABLE[config.CODE_BAHAYA]

    return rgba


def write_step_tiles(
    run_dir: Path,
    step: int,
    cat_field: dict,
    minzoom: int = config.MINZOOM,
    maxzoom: int = config.MAXZOOM,
) -> int:
    """
    Generate visual WebP tiles for a forecast step category field.
    cat_field has {"lats": 1d array, "lons": 1d array, "values": 2d uint8 array}
    """
    west, south, east, north = config.BBOX
    dest_root = run_dir / str(step)
    staging = run_dir / f".tmp_{step}"

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    lats = cat_field["lats"]
    lons = cat_field["lons"]
    categories = cat_field["values"]
    count = 0

    for z, x, y in _tiles_for_bbox(west, south, east, north, range(minzoom, maxzoom + 1)):
        lon2d, lat2d = _mercator_lonlat(z, x, y, config.TILE_SIZE)
        sampled_cat = nearest_sample(categories, lats, lons, lat2d, lon2d, nodata_val=config.CODE_NODATA)

        # Optimization: if all pixels are 0 or 255 (completely transparent), we can write minimal transparent WebP
        if np.all((sampled_cat == config.CODE_NO_TRIGGER) | (sampled_cat == config.CODE_NODATA)):
            rgba = np.zeros((config.TILE_SIZE, config.TILE_SIZE, 4), dtype=np.uint8)
        else:
            rgba = colorize_categories(sampled_cat)

        img = Image.fromarray(rgba, mode="RGBA")
        out_dir = staging / str(z) / str(x)
        out_dir.mkdir(parents=True, exist_ok=True)
        img.save(
            out_dir / f"{y}.webp",
            format="WEBP",
            quality=config.WEBP_QUALITY,
            lossless=True,
        )
        count += 1

    dest_root.parent.mkdir(parents=True, exist_ok=True)
    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.move(str(staging), str(dest_root))
    return count
