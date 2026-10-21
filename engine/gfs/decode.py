"""Decode a downloaded GRIB2 timestep into per-variable Indonesia grids.

Input: one concatenated GRIB2 file from ``source.download_timestep``.
Output: dict variable_key -> 2-D numpy array (lat ascending, lon ascending)
covering the configured Indonesia domain, already converted to display units.

Implementation uses ``eccodes`` directly (not cfgrib's Dataset builder,
which fails on files mixing stepTypes). Messages are identified by
(paramId, level, stepType). Missing variables (e.g. APCP at f000) return
a zeros grid for rain.
"""
from __future__ import annotations

import numpy as np

from . import config

# (paramId, preferred stepType or None)
# paramIds verified against real GFS 0.25 files (Oct 2026). paramId alone
# identifies each variable in the picked-message file; level keys are
# NOT used because eccodes returns them inconsistently (e.g. 'sfc' vs 101).
WANTED = {
    "temperature": (167, None),      # TMP 2 m (t2m)
    "dew_point": (168, None),        # DPT 2 m (d2m)
    "rh": (260242, None),            # RH 2 m (r2)
    "pressure": (260074, None),      # PRMSL (mean sea level)
    "rain": (228228, "accum"),       # APCP surface (tp)
    "cape": (59, None),              # CAPE surface
    "clouds": (228164, "avg"),       # TCDC entire atmosphere (avg)
    "u10": (165, None),              # UGRD 10 m (10u)
    "v10": (166, None),              # VGRD 10 m (10v)
}


def _convert(key: str, values: np.ndarray) -> np.ndarray:
    mode = config.VARIABLES[key].convert
    if mode == "kelvin_to_c":
        return values - 273.15
    if mode == "pa_to_hpa":
        return values / 100.0
    return values


def _read_messages(path: str) -> list[dict]:
    from eccodes import codes_get, codes_get_values, codes_grib_new_from_file, codes_release

    def _get(gid, key, default=None):
        try:
            return codes_get(gid, key)
        except Exception:
            return default

    out = []
    with open(path, "rb") as fh:
        while True:
            gid = codes_grib_new_from_file(fh)
            if gid is None:
                break
            try:
                msg = {
                    "paramId": _get(gid, "paramId"),
                    "stepType": _get(gid, "stepType"),
                    "Ni": _get(gid, "Ni"),
                    "Nj": _get(gid, "Nj"),
                    "lat1": _get(gid, "latitudeOfFirstGridPointInDegrees"),
                    "lon1": _get(gid, "longitudeOfFirstGridPointInDegrees"),
                    "lat2": _get(gid, "latitudeOfLastGridPointInDegrees"),
                    "lon2": _get(gid, "longitudeOfLastGridPointInDegrees"),
                    "values": np.array(codes_get_values(gid), dtype=np.float64),
                }
            finally:
                codes_release(gid)
            out.append(msg)
    return out


def _grid_axes(msg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Latitude/longitude axes for a message, ascending, lon in -180..180."""
    ni, nj = msg["Ni"], msg["Nj"]
    # linspace follows the scan order (lat1/lat2 are the scan endpoints),
    # so this is correct regardless of jDirectionPositive.
    lat = np.linspace(msg["lat1"], msg["lat2"], nj)
    lon = np.linspace(msg["lon1"], msg["lon2"], ni)
    lon = np.where(lon > 180, lon - 360, lon)
    order_lat = np.argsort(lat)
    order_lon = np.argsort(lon)
    return lat[order_lat], lon[order_lon], order_lat, order_lon


def decode_timestep(path: str, keys: list[str] | None = None) -> dict[str, np.ndarray]:
    msgs = _read_messages(path)
    dom = config.DOMAIN
    result: dict[str, np.ndarray] = {}
    ref_axes: tuple | None = None
    wanted = WANTED if keys is None else {k: WANTED[k] for k in keys if k in WANTED}

    for key, (param_id, step_type) in wanted.items():
        cands = [m for m in msgs if m["paramId"] == param_id]
        if step_type is not None:
            pref = [m for m in cands if m["stepType"] == step_type]
            cands = pref or cands
        if not cands:
            if key == "rain":
                continue  # APCP absent at f000 -> zeros (handled below)
            raise RuntimeError(f"variable {key} (paramId {param_id}) not found in {path}")
        msg = cands[0]
        lat, lon, o_lat, o_lon = _grid_axes(msg)
        grid = msg["values"].reshape(msg["Nj"], msg["Ni"])
        grid = grid[np.ix_(o_lat, o_lon)]
        grid = np.where(grid > 1e30, np.nan, grid)
        result[key] = _convert(key, grid)
        if ref_axes is None:
            ref_axes = (lat, lon)

    if ref_axes is None:
        raise RuntimeError(f"no usable messages in {path}")
    lat, lon = ref_axes

    lat_mask = (lat >= dom["lat_min"] - 0.5) & (lat <= dom["lat_max"] + 0.5)
    lon_mask = (lon >= dom["lon_min"] - 0.5) & (lon <= dom["lon_max"] + 0.5)
    lat_idx = np.where(lat_mask)[0]
    lon_idx = np.where(lon_mask)[0]

    out: dict[str, np.ndarray] = {}
    for key, grid in result.items():
        out[key] = grid[np.ix_(lat_idx, lon_idx)]
    if (keys is None or "rain" in keys) and "rain" not in out:
        out["rain"] = np.zeros((len(lat_idx), len(lon_idx)), dtype=np.float64)
    if "u10" in out and "v10" in out and (keys is None or "wind" in keys):
        out["wind"] = np.sqrt(out["u10"] ** 2 + out["v10"] ** 2)
    out["_lat"] = lat[lat_idx]
    out["_lon"] = lon[lon_idx]
    return out
