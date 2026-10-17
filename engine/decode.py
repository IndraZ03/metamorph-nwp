from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from . import config
from .derive import k_to_c, m_to_mm, magnus_rh, pa_to_hpa

log = logging.getLogger("ecmwf.decode")

# cfgrib often renames GRIB shortName
_ALIASES = {
    "2t": ("t2m", "2t"),
    "2d": ("d2m", "2d"),
    "msl": ("msl",),
    "tp": ("tp",),
    "mucape": ("mucape", "cape"),
    "tcc": ("tcc",),
}


def _lat_lon_names(da) -> tuple[str, str]:
    lat = "latitude" if "latitude" in da.coords else "lat"
    lon = "longitude" if "longitude" in da.coords else "lon"
    return lat, lon


def _squeeze(da):
    drop = [
        d
        for d in da.dims
        if d not in ("latitude", "longitude", "lat", "lon") and da.sizes[d] == 1
    ]
    if drop:
        da = da.squeeze(drop, drop=True)
    return da


def _crop(da):
    west, south, east, north = config.BBOX
    lat_name, lon_name = _lat_lon_names(da)
    lat = da[lat_name]
    lon = da[lon_name]
    lat_slice = slice(north, south) if float(lat[0]) > float(lat[-1]) else slice(south, north)
    # ECMWF open data lon is typically -180..180; 94..141.5 needs no wrap
    lon_vals = lon.values
    if float(np.nanmax(lon_vals)) > 180:
        # 0..360 — still fine for Indonesia
        pass
    da = da.sel({lat_name: lat_slice, lon_name: slice(west, east)})
    return da


def _to_latlon_array(da) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    da = _squeeze(_crop(da))
    lat_name, lon_name = _lat_lon_names(da)
    lats = np.asarray(da[lat_name].values, dtype=np.float64)
    lons = np.asarray(da[lon_name].values, dtype=np.float64)
    values = np.asarray(da.values, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(f"expected 2d field, got {values.shape}")
    return lats, lons, values


def _collect_vars(path: Path) -> dict:
    import cfgrib

    datasets = cfgrib.open_datasets(str(path), backend_kwargs={"indexpath": ""})
    by_name: dict = {}
    for ds in datasets:
        for name, da in ds.data_vars.items():
            by_name[name] = da
            short = da.attrs.get("GRIB_shortName") or da.attrs.get("shortName")
            if short:
                by_name[str(short)] = da
    return by_name


def _pick(by_name: dict, grib_name: str):
    for alias in _ALIASES.get(grib_name, (grib_name,)):
        if alias in by_name:
            return by_name[alias]
    return None


def decode_step(grib_path: Path) -> dict[str, dict]:
    """
    Return {var_id: {lats, lons, values}} in display units.
    Missing params are omitted.
    """
    by_name = _collect_vars(grib_path)
    out: dict[str, dict] = {}

    t2m_c = d2m_c = None
    lats = lons = None

    da = _pick(by_name, "2t")
    if da is not None:
        lats, lons, kelvin = _to_latlon_array(da)
        t2m_c = k_to_c(kelvin)
        out["t2m"] = {"lats": lats, "lons": lons, "values": t2m_c}

    da = _pick(by_name, "2d")
    if da is not None:
        lats, lons, kelvin = _to_latlon_array(da)
        d2m_c = k_to_c(kelvin)
        out["d2m"] = {"lats": lats, "lons": lons, "values": d2m_c}

    if t2m_c is not None and d2m_c is not None:
        out["rh"] = {"lats": lats, "lons": lons, "values": magnus_rh(t2m_c, d2m_c)}

    da = _pick(by_name, "msl")
    if da is not None:
        lats, lons, pa = _to_latlon_array(da)
        out["msl"] = {"lats": lats, "lons": lons, "values": pa_to_hpa(pa)}

    da = _pick(by_name, "tp")
    if da is not None:
        lats, lons, metres = _to_latlon_array(da)
        mm = m_to_mm(metres)
        mm = np.where(np.isfinite(mm), np.clip(mm, 0, None), mm)
        out["tp"] = {"lats": lats, "lons": lons, "values": mm}

    da = _pick(by_name, "mucape")
    if da is not None:
        lats, lons, cape = _to_latlon_array(da)
        out["cape"] = {"lats": lats, "lons": lons, "values": cape}

    da = _pick(by_name, "tcc")
    if da is not None:
        lats, lons, tcc = _to_latlon_array(da)
        # some files store 0–100; normalise to 0–1
        if np.nanmax(tcc) > 1.5:
            tcc = tcc / 100.0
        out["tcc"] = {"lats": lats, "lons": lons, "values": tcc}

    log.info("decoded vars: %s", ", ".join(sorted(out)))
    return out
