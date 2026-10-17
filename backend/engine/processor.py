import eccodes
import numpy as np
from typing import Tuple

from .config import PARAMETERS
from .grid import GridRemapper

_remapper_instance = None


def get_remapper() -> GridRemapper:
    global _remapper_instance
    if _remapper_instance is None:
        _remapper_instance = GridRemapper()
    return _remapper_instance


def process_grib_to_grid(raw_grib_bytes: bytes, param_key: str) -> Tuple[np.ndarray, dict]:
    """
    Parse raw GRIB2 bytes, convert physical units, and remap to Indonesia 2D grid.
    Returns: (grid_2d, metadata)
    """
    param_cfg = PARAMETERS[param_key]

    gh = eccodes.codes_new_from_message(raw_grib_bytes)
    try:
        raw_values = eccodes.codes_get_values(gh)
        date = eccodes.codes_get(gh, "dataDate")
        time = eccodes.codes_get(gh, "dataTime")
        step_range = eccodes.codes_get(gh, "stepRange")
        meta = {
            "date": date,
            "time": time,
            "step_range": step_range,
        }
    finally:
        eccodes.codes_release(gh)

    # Convert unit (e.g. Kelvin -> Celsius, Pa -> hPa)
    conv_values = param_cfg["convert"](raw_values)

    # Remap onto Indonesia regular grid (541 x 1201)
    remapper = get_remapper()
    grid_2d = remapper.remap(conv_values)

    return grid_2d.astype(np.float32), meta
