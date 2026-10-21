"""Spatial alignment shared by offline processor and tests."""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject


def align_hazard_to_ecmwf_grid(hazard_tif: Path, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Average valid continuous hazard indices onto native rainfall cells, then classify.

    This is a grid-mean index, not a local 100 m hazard assessment. Source NoData
    is excluded from the mean; cells with no source coverage remain NoData.
    """
    if len(lats) < 2 or len(lons) < 2:
        raise ValueError("Spatial alignment needs at least 2 coordinates per axis")
    dx, dy = abs(lons[1] - lons[0]), abs(lats[1] - lats[0])
    transform = from_bounds(lons.min()-dx/2, lats.min()-dy/2,
                            lons.max()+dx/2, lats.max()+dy/2, len(lons), len(lats))
    output = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    with rasterio.open(hazard_tif) as source:
        if source.crs is None or source.count != 1:
            raise ValueError("Hazard raster must have CRS and one numeric band")
        reproject(source=rasterio.band(source, 1), destination=output,
                  src_transform=source.transform, src_crs=source.crs,
                  src_nodata=source.nodata, dst_transform=transform, dst_crs="EPSG:4326",
                  resampling=Resampling.average, dst_nodata=np.nan)
    output[~np.isfinite(output) | (output < 0) | (output > 1)] = np.nan
    return output if lats[0] > lats[-1] else output[::-1]
