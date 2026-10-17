import numpy as np
from pathlib import Path
from scipy.ndimage import map_coordinates
from typing import Dict, Optional, Tuple

from .config import (
    BBOX_LAT_MIN,
    BBOX_LAT_MAX,
    BBOX_LON_MIN,
    BBOX_LON_MAX,
    GRID_RES_DEG,
    GRIDS_DIR,
    PARAMETERS,
)

_grid_cache: Dict[str, np.ndarray] = {}


def get_grid_file_path(run_id: str, param_key: str, step_str: str) -> Path:
    d = GRIDS_DIR / run_id / param_key
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{step_str}.npy"


def save_grid_to_disk(grid_2d: np.ndarray, run_id: str, param_key: str, step_str: str):
    """Save 2D grid array to disk."""
    path = get_grid_file_path(run_id, param_key, step_str)
    np.save(path, grid_2d.astype(np.float32))
    cache_key = f"{run_id}:{param_key}:{step_str}"
    _grid_cache[cache_key] = grid_2d


def load_grid_from_disk(run_id: str, param_key: str, step_str: str) -> Optional[np.ndarray]:
    """Load 2D grid array from disk or memory cache."""
    cache_key = f"{run_id}:{param_key}:{step_str}"
    if cache_key in _grid_cache:
        return _grid_cache[cache_key]

    path = get_grid_file_path(run_id, param_key, step_str)
    if not path.exists():
        return None

    try:
        grid_2d = np.load(path)
        _grid_cache[cache_key] = grid_2d
        return grid_2d
    except Exception as e:
        print(f"Error loading grid {path}: {e}")
        return None


def sample_point_value(
    grid_2d: np.ndarray, lat: float, lon: float
) -> Optional[float]:
    """
    Bilinear interpolation to sample value at exact (lat, lon).
    Returns None if point is outside Indonesia bounding box.
    """
    if not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX and BBOX_LON_MIN <= lon <= BBOX_LON_MAX):
        return None

    row = (lat - BBOX_LAT_MIN) / GRID_RES_DEG
    col = (lon - BBOX_LON_MIN) / GRID_RES_DEG

    coords = np.array([[row], [col]])
    val = map_coordinates(grid_2d, coords, order=1, mode="constant", cval=np.nan)[0]

    if np.isnan(val):
        return None
    return round(float(val), 2)
