"""Render decoded grids into XYZ WebP tiles (Web Mercator, EPSG:3857).

Design:
- For each zoom, a bilinear resampling map (source-grid indices + weights)
  is built ONCE from the domain geometry and reused for every timestep.
- Each (variable, timestep) is rendered once into a full-domain RGBA canvas,
  then sliced into 256x256 tiles with PIL. This is far faster than
  rendering per tile.
- Pixels outside the Indonesia bbox get alpha 0 (transparent).
"""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image

from . import config

# ---------------------------------------------------------------- mercator

def _merc_y(lat_deg: float) -> float:
    lat = math.radians(max(min(lat_deg, 85.05112878), -85.05112878))
    return math.log(math.tan(math.pi / 4 + lat / 2))


def _inv_merc_y(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def _tile_x_range(zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x0 = math.floor((config.DOMAIN["lon_min"] + 180) / 360 * n)
    x1 = math.floor((config.DOMAIN["lon_max"] + 180) / 360 * n)
    return x0, x1


def _tile_y_range(zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    # y=0 at north pole; lat_max (north edge) -> smaller y.
    y0 = math.floor((1 - _merc_y(config.DOMAIN["lat_max"]) / math.pi) / 2 * n)
    y1 = math.floor((1 - _merc_y(config.DOMAIN["lat_min"]) / math.pi) / 2 * n)
    return y0, y1


# ---------------------------------------------------------------- resampling

class Resampler:
    """Bilinear index maps from a (lat, lon) source grid to a canvas."""

    _cache: dict = {}

    def __init__(self, zoom: int, src_lat: np.ndarray, src_lon: np.ndarray):
        self.zoom = zoom
        self.x0, self.x1 = _tile_x_range(zoom)
        self.y0, self.y1 = _tile_y_range(zoom)
        self.nx = (self.x1 - self.x0 + 1) * config.TILE_SIZE
        self.ny = (self.y1 - self.y0 + 1) * config.TILE_SIZE
        n = 2 ** zoom

        # Canvas pixel -> lon/lat (pixel centres).
        px = (np.arange(self.nx, dtype=np.float64) + 0.5) / config.TILE_SIZE + self.x0
        py = (np.arange(self.ny, dtype=np.float64) + 0.5) / config.TILE_SIZE + self.y0
        lon2d = -180.0 + (px / n) * 360.0
        yfrac = py / n
        lat2d = np.array([_inv_merc_y(math.pi * (1 - 2 * yf)) for yf in yfrac])
        lon_grid, lat_grid = np.meshgrid(lon2d, lat2d)

        # Mask: inside Indonesia bbox?
        dom = config.DOMAIN
        self.inside = (
            (lon_grid >= dom["lon_min"]) & (lon_grid <= dom["lon_max"])
            & (lat_grid >= dom["lat_min"]) & (lat_grid <= dom["lat_max"])
        )

        # lon/lat -> fractional source-grid indices (lat/lon ascending).
        dlat = float(src_lat[1] - src_lat[0])
        dlon = float(src_lon[1] - src_lon[0])
        fi = (lat_grid - src_lat[0]) / dlat
        fj = (lon_grid - src_lon[0]) / dlon
        self.i0 = np.clip(np.floor(fi).astype(np.int32), 0, len(src_lat) - 2)
        self.j0 = np.clip(np.floor(fj).astype(np.int32), 0, len(src_lon) - 2)
        self.wi = np.clip(fi - self.i0, 0.0, 1.0)
        self.wj = np.clip(fj - self.j0, 0.0, 1.0)

    @classmethod
    def get(cls, zoom: int, src_lat: np.ndarray, src_lon: np.ndarray) -> "Resampler":
        key = (zoom, src_lat.tobytes(), src_lon.tobytes())
        if key not in cls._cache:
            cls._cache[key] = cls(zoom, src_lat, src_lon)
        return cls._cache[key]

    def resample(self, field: np.ndarray) -> np.ndarray:
        """Bilinear resample of a (lat, lon) field onto the canvas.
        NaNs propagate as NaN (rendered transparent)."""
        f = field
        a = f[self.i0, self.j0]
        b = f[self.i0, self.j0 + 1]
        c = f[self.i0 + 1, self.j0]
        d = f[self.i0 + 1, self.j0 + 1]
        top = a * (1 - self.wj) + b * self.wj
        bot = c * (1 - self.wj) + d * self.wj
        return top * (1 - self.wi) + bot * self.wi


# ---------------------------------------------------------------- colormaps

def _build_lut(var) -> np.ndarray:
    """256-entry RGB lookup table from the variable's control-point stops."""
    import matplotlib
    from matplotlib.colors import LinearSegmentedColormap

    stops = var.stops
    vals = np.array([s[0] for s in stops], dtype=np.float64)
    colors = np.array([s[1] for s in stops], dtype=np.float64) / 255.0
    pos = (vals - var.vmin) / (var.vmax - var.vmin)
    cmap = LinearSegmentedColormap.from_list(var.key, list(zip(pos, colors)))
    return (cmap(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)


_LUT_CACHE: dict[str, np.ndarray] = {}


def _lut(var) -> np.ndarray:
    if var.key not in _LUT_CACHE:
        _LUT_CACHE[var.key] = _build_lut(var)
    return _LUT_CACHE[var.key]


NUMERIC_OFFSET = 1000.0
NUMERIC_SCALE = 10.0


def encode_numeric_rgba(values: np.ndarray) -> np.ndarray:
    """Terrain-RGB-like: val = ((R<<16 | G<<8 | B) / 10) - 1000. Alpha 0 = nodata."""
    h, w = values.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(values)
    if not np.any(valid):
        return rgba
    val_int = np.clip(
        (values[valid] + NUMERIC_OFFSET) * NUMERIC_SCALE, 0, 16777215
    ).astype(np.uint32)
    rgba[valid, 0] = ((val_int >> 16) & 255).astype(np.uint8)
    rgba[valid, 1] = ((val_int >> 8) & 255).astype(np.uint8)
    rgba[valid, 2] = (val_int & 255).astype(np.uint8)
    rgba[valid, 3] = 255
    return rgba


def colorize(var, values: np.ndarray) -> np.ndarray:
    """Map data values to an RGBA uint8 canvas.

    Returns (H, W, 4) uint8. NaN / out-of-bbox -> alpha 0.
    Alpha modes: opaque | threshold (rain) | coverage (clouds).
    """
    lut = _lut(var)
    norm = np.clip((np.nan_to_num(values, nan=var.vmin) - var.vmin) / (var.vmax - var.vmin), 0.0, 1.0)
    idx = (norm * 255).astype(np.uint8)
    rgb = lut[idx]
    h, w = values.shape
    alpha = np.full((h, w), 255, dtype=np.uint8)
    safe = np.nan_to_num(values, nan=-1e9)
    if var.alpha == "threshold":
        ramp = np.clip((safe - var.alpha_threshold) / 0.9, 0.0, 1.0)
        alpha = (ramp * 255).astype(np.uint8)
    elif var.alpha == "coverage":
        alpha = (np.clip(safe, 0, 100) * 255.0 / 100.0).astype(np.uint8)
    alpha = np.where(np.isnan(values), 0, alpha).astype(np.uint8)
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)
    return rgba


# ---------------------------------------------------------------- tile writer

def render_timestep(
    grids: dict,
    out_root: str,
    numeric_root: str | None = None,
    keys: list[str] | None = None,
) -> dict[str, int]:
    """Render all variables of one timestep to tiles.

    grids: output of decode.decode_timestep (incl. '_lat'/'_lon').
    out_root: directory for this valid time, e.g. tiles/gfs/<run>/<valid>/.
    numeric_root: optional lossless RGB-encoded values for click inspect.
    Returns {variable_key: number_of_tiles_written}.
    """
    src_lat = grids["_lat"]
    src_lon = grids["_lon"]
    counts: dict[str, int] = {}
    wanted = keys if keys is not None else list(config.VARIABLES)
    for key in wanted:
        var = config.VARIABLES.get(key)
        if var is None or key not in grids:
            continue
        field = grids[key]
        written = 0
        for zoom in range(config.ZOOM_MIN, config.ZOOM_MAX + 1):
            rs = Resampler.get(zoom, src_lat, src_lon)
            canvas_values = rs.resample(field)
            canvas_values = np.where(rs.inside, canvas_values, np.nan)
            rgba = colorize(var, canvas_values)
            img = Image.fromarray(rgba, mode="RGBA")
            num_img = None
            if numeric_root:
                num_img = Image.fromarray(encode_numeric_rgba(canvas_values), mode="RGBA")
            for ty in range(rs.y1 - rs.y0 + 1):
                for tx in range(rs.x1 - rs.x0 + 1):
                    box = (
                        tx * config.TILE_SIZE, ty * config.TILE_SIZE,
                        (tx + 1) * config.TILE_SIZE, (ty + 1) * config.TILE_SIZE,
                    )
                    tile = img.crop(box)
                    visual_empty = tile.getextrema()[3] == (0, 0)
                    if not visual_empty:
                        path = os.path.join(
                            out_root, key, str(zoom),
                            str(rs.x0 + tx), f"{rs.y0 + ty}.webp",
                        )
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        tile.save(path, format="WEBP",
                                  quality=config.WEBP_QUALITY, method=config.WEBP_METHOD)
                        written += 1
                    if num_img is not None:
                        ntile = num_img.crop(box)
                        if ntile.getextrema()[3] == (0, 0):
                            continue
                        npath = os.path.join(
                            numeric_root, key, str(zoom),
                            str(rs.x0 + tx), f"{rs.y0 + ty}.webp",
                        )
                        os.makedirs(os.path.dirname(npath), exist_ok=True)
                        ntile.save(npath, format="WEBP", lossless=True)
        counts[key] = written
    return counts
