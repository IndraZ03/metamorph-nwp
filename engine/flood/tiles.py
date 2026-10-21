"""Continuous display ramps only; no scientific category thresholds."""
import numpy as np
from PIL import Image
from engine.landslide.tiles import _tiles_for_bbox, _mercator_lonlat, nearest_sample
from . import config


def write_tiles(root, step, indicator, values, lats, lons):
    maximum = 200.0 if indicator == "rainfall" else 1.0
    for z, x, y in _tiles_for_bbox(*config.BBOX, range(config.MINZOOM, config.MAXZOOM + 1)):
        qlon, qlat = _mercator_lonlat(z, x, y, 256)
        sampled = nearest_sample(values, lats, lons, qlat, qlon, nodata_val=np.nan)
        finite = np.isfinite(sampled)
        t = np.nan_to_num(np.clip(sampled / maximum, 0, 1), nan=0)
        rgba = np.zeros((*sampled.shape, 4), dtype=np.uint8)
        rgba[..., 0] = (30 + 150 * t).astype(np.uint8)
        rgba[..., 1] = (180 - 130 * t).astype(np.uint8)
        rgba[..., 2] = (230 - 30 * t).astype(np.uint8)
        rgba[..., 3] = np.where(finite, 220, 0)
        path = root / "tiles" / indicator / str(step) / str(z) / str(x) / f"{y}.webp"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgba).save(path, format="WEBP", lossless=True)
