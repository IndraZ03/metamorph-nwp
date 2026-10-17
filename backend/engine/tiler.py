import math
import numpy as np
from pathlib import Path
from PIL import Image
from scipy.ndimage import map_coordinates
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from .config import (
    BBOX_LAT_MIN,
    BBOX_LAT_MAX,
    BBOX_LON_MIN,
    BBOX_LON_MAX,
    GRID_RES_DEG,
    PARAMETERS,
    TILES_DIR,
    NUMERIC_TILES_DIR,
    ZOOM_MIN,
    ZOOM_MAX,
)
from .colormaps import apply_colormap, encode_numeric_rgba


def lonlat_to_tile(lon: float, lat: float, z: int) -> Tuple[int, int]:
    """Convert longitude, latitude to tile x, y at zoom z."""
    lat_rad = math.radians(lat)
    n = 2.0 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lonlat_bounds(x: int, y: int, z: int) -> Tuple[float, float, float, float]:
    """
    Returns (lon_min, lat_min, lon_max, lat_max) for tile (x, y, z).
    """
    n = 2.0 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0

    lat_rad_max = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
    lat_max = math.degrees(lat_rad_max)

    lat_rad_min = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 1) / n)))
    lat_min = math.degrees(lat_rad_min)

    return lon_min, lat_min, lon_max, lat_max


def get_tile_range_for_bbox(z: int) -> Tuple[int, int, int, int]:
    """Find min/max tile (x, y) covering Indonesia BBox."""
    x_min, y_min = lonlat_to_tile(BBOX_LON_MIN, BBOX_LAT_MAX, z)
    x_max, y_max = lonlat_to_tile(BBOX_LON_MAX, BBOX_LAT_MIN, z)
    return min(x_min, x_max), max(x_min, x_max), min(y_min, y_max), max(y_min, y_max)


class TileGenerator:
    """Pre-renders 2D meteorology raster into Slippy Map WebP tiles."""

    def __init__(self, target_shape=(541, 1201)):
        self.shape = target_shape
        self.H, self.W = target_shape

    def generate_tiles_for_step(
        self,
        grid_2d: np.ndarray,
        param_key: str,
        run_id: str,
        step_str: str,
        zooms: List[int] = None,
    ) -> int:
        """
        Slices grid_2d and generates WebP tiles for zooms ZOOM_MIN..ZOOM_MAX.
        Returns total tiles written.
        """
        if zooms is None:
            zooms = list(range(ZOOM_MIN, ZOOM_MAX + 1))

        param_cfg = PARAMETERS[param_key]
        vmin, vmax = param_cfg["range"]

        base_dir = TILES_DIR / run_id / param_key / step_str
        num_base_dir = NUMERIC_TILES_DIR / run_id / param_key / step_str

        def _render_and_save(tile_coords, tile_lats, tile_lons, z, x, y):
            col_indices = (tile_lons - BBOX_LON_MIN) / GRID_RES_DEG
            row_indices = (tile_lats - BBOX_LAT_MIN) / GRID_RES_DEG
            coords = np.array(np.meshgrid(row_indices, col_indices, indexing="ij"))

            sampled = map_coordinates(
                grid_2d,
                coords,
                order=1,
                mode="constant",
                cval=np.nan,
            )
            rgba = apply_colormap(sampled, param_key, vmin, vmax)
            if rgba[:, :, 3].max() == 0:
                return 0

            # 1. Save visual WebP tile
            tile_dir = base_dir / str(z) / str(x)
            tile_dir.mkdir(parents=True, exist_ok=True)
            tile_path = tile_dir / f"{y}.webp"

            img = Image.fromarray(rgba, "RGBA")
            img.save(tile_path, format="WEBP", quality=85, method=4)

            # 2. Save numeric WebP tile (lossless)
            rgba_num = encode_numeric_rgba(sampled)
            num_dir = num_base_dir / str(z) / str(x)
            num_dir.mkdir(parents=True, exist_ok=True)
            num_path = num_dir / f"{y}.webp"

            img_num = Image.fromarray(rgba_num, "RGBA")
            img_num.save(num_path, format="WEBP", lossless=True)

            return 1

        tasks = []
        for z in zooms:
            x_min, x_max, y_min, y_max = get_tile_range_for_bbox(z)
            n = 2.0 ** z
            px_linear = (np.arange(256) + 0.5) / 256.0

            for x in range(x_min, x_max + 1):
                lon_tile_min = x / n * 360.0 - 180.0
                lon_tile_max = (x + 1) / n * 360.0 - 180.0
                tile_lons = lon_tile_min + px_linear * (lon_tile_max - lon_tile_min)

                if tile_lons[-1] < BBOX_LON_MIN or tile_lons[0] > BBOX_LON_MAX:
                    continue

                for y in range(y_min, y_max + 1):
                    y_frac = y + px_linear
                    lat_rad = np.arctan(np.sinh(np.pi * (1.0 - 2.0 * y_frac / n)))
                    tile_lats = np.degrees(lat_rad)

                    if tile_lats[0] < BBOX_LAT_MIN or tile_lats[-1] > BBOX_LAT_MAX:
                        continue

                    tasks.append((z, x, y, tile_lats, tile_lons))

        tiles_count = 0
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(_render_and_save, None, t[3], t[4], t[0], t[1], t[2])
                for t in tasks
            ]
            for f in futures:
                tiles_count += f.result()

        return tiles_count
