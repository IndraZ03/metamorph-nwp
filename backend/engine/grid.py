import bz2
import io
import urllib.request
import numpy as np
from pathlib import Path
from scipy.spatial import cKDTree
import eccodes

from .config import (
    CACHE_DIR,
    DWD_BASE_URL,
    BBOX_LAT_MIN,
    BBOX_LAT_MAX,
    BBOX_LON_MIN,
    BBOX_LON_MAX,
    GRID_RES_DEG,
)

GRID_FILE = CACHE_DIR / "icon_indo_grid.npz"


def fetch_invariant_coord(var_name, cycle="00"):
    """Fetch CLAT or CLON from DWD Open Data."""
    url = f"{DWD_BASE_URL}/{cycle}/{var_name.lower()}/"
    req = urllib.request.Request(url, headers={"User-Agent": "metamorph-nwp/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    import re
    match = re.search(r'href=["\']([^"\']+' + var_name.upper() + r'\.grib2\.bz2)["\']', html)
    if not match:
        raise RuntimeError(f"Could not find invariant {var_name} file in {url}")

    file_url = f"{url}{match.group(1)}"
    print(f"Downloading invariant grid: {file_url}")
    file_req = urllib.request.Request(file_url, headers={"User-Agent": "metamorph-nwp/1.0"})
    with urllib.request.urlopen(file_req, timeout=60) as resp:
        compressed = resp.read()

    raw = bz2.decompress(compressed)
    gh = eccodes.codes_new_from_message(raw)
    values = eccodes.codes_get_values(gh)
    eccodes.codes_release(gh)

    # Values are in degrees
    return values


def init_grid_index(force=False, cycle="00"):
    """
    Ensure Indonesia spatial index and KDTree IDW interpolation weights are ready.
    Loads from cache or builds and caches.
    """
    if GRID_FILE.exists() and not force:
        data = np.load(GRID_FILE)
        return (
            data["cell_indices"],
            data["target_lats"],
            data["target_lons"],
            data["k_indices"],
            data["weights"],
            data["shape"],
        )

    print("Initializing ICON Indonesia grid index & interpolation matrix...")
    lats = fetch_invariant_coord("CLAT", cycle)
    lons = fetch_invariant_coord("CLON", cycle)

    # Buffer bounding box slightly to avoid interpolation border artifacts
    pad = 1.0
    mask = (
        (lats >= BBOX_LAT_MIN - pad)
        & (lats <= BBOX_LAT_MAX + pad)
        & (lons >= BBOX_LON_MIN - pad)
        & (lons <= BBOX_LON_MAX + pad)
    )
    cell_indices = np.where(mask)[0]
    sub_lats = lats[cell_indices]
    sub_lons = lons[cell_indices]
    print(f"Indexed {len(cell_indices)} cells covering Indonesia domain.")

    # Create target regular lat/lon grid
    target_lats = np.arange(BBOX_LAT_MIN, BBOX_LAT_MAX + GRID_RES_DEG / 2.0, GRID_RES_DEG)
    target_lons = np.arange(BBOX_LON_MIN, BBOX_LON_MAX + GRID_RES_DEG / 2.0, GRID_RES_DEG)
    grid_shape = (len(target_lats), len(target_lons))

    # Meshgrid (H, W) -> flat
    glon, glat = np.meshgrid(target_lons, target_lats)
    target_pts = np.column_stack([glat.ravel(), glon.ravel()])
    source_pts = np.column_stack([sub_lats, sub_lons])

    # Build KDTree and compute IDW weights for k=4
    print("Computing KDTree IDW interpolation weights (k=4)...")
    tree = cKDTree(source_pts)
    distances, k_indices = tree.query(target_pts, k=4)

    # IDW weights
    eps = 1e-6
    weights = 1.0 / (distances + eps)
    weights /= np.sum(weights, axis=-1, keepdims=True)

    # Save to npz cache
    np.savez_compressed(
        GRID_FILE,
        cell_indices=cell_indices,
        target_lats=target_lats,
        target_lons=target_lons,
        k_indices=k_indices,
        weights=weights,
        shape=np.array(grid_shape),
    )
    print(f"Saved precomputed grid weights to {GRID_FILE}")

    return cell_indices, target_lats, target_lons, k_indices, weights, grid_shape


class GridRemapper:
    """Fast in-memory remapper for ICON unstructured array -> Indonesia 2D grid."""

    def __init__(self):
        (
            self.cell_indices,
            self.target_lats,
            self.target_lons,
            self.k_indices,
            self.weights,
            self.shape,
        ) = init_grid_index()
        self.shape = tuple(self.shape)

    def remap(self, full_values):
        """
        Input: full_values (1D array of 2,949,120 floats).
        Output: 2D array of shape self.shape (Lat x Lon) covering Indonesia.
        """
        sub_vals = full_values[self.cell_indices]
        interpolated = np.sum(sub_vals[self.k_indices] * self.weights, axis=-1)
        return interpolated.reshape(self.shape)
