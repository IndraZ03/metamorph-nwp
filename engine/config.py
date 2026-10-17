from __future__ import annotations

from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ENGINE_DIR / "output"
CACHE_DIR = OUTPUT_DIR / "cache"
RUNS_DIR = OUTPUT_DIR / "runs"
LATEST_PATH = OUTPUT_DIR / "latest.json"

# WGS84 [west, south, east, north] — Sumatra–Papua + EEZ pad
BBOX = (94.0, -11.5, 141.5, 6.5)

MINZOOM = 3
MAXZOOM = 6
TILE_SIZE = 256
WEBP_QUALITY = 80
WEBP_METHOD = 4

MODEL = "ecmwf-ifs"
STREAM = "oper"
RESOL = "0p25"
SOURCE = "ecmwf"
LICENCE = "CC-BY-4.0"
ATTRIBUTION = "© ECMWF IFS 0.25° (CC-BY-4.0)"

TILE_URL_TEMPLATE = "/ecmwf/runs/{run_id}/{var}/{step}/{z}/{x}/{y}.webp"
NUMERIC_TILE_URL_TEMPLATE = "/ecmwf/numeric/{run_id}/{var}/{step}/{z}/{x}/{y}.webp"

# GRIB shortNames actually retrieved (RH is derived from 2t+2d)
FETCH_PARAMS = ["2t", "2d", "msl", "tp", "mucape", "tcc"]

# App ids ↔ GRIB. Colormaps key off `id`.
VARIABLES = [
    {"id": "t2m", "param": "2t", "units": "C", "label": "Temperature"},
    {"id": "rh", "param": "derived", "units": "%", "label": "Relative Humidity"},
    {"id": "tp", "param": "tp", "units": "mm", "label": "Rain accumulation"},
    {"id": "msl", "param": "msl", "units": "hPa", "label": "Pressure"},
    {"id": "d2m", "param": "2d", "units": "C", "label": "Dew Point"},
    {"id": "cape", "param": "mucape", "units": "J/kg", "label": "CAPE"},
    {"id": "tcc", "param": "tcc", "units": "frac", "label": "Clouds"},
]

DEFAULT_VARIABLE = "t2m"
RETAIN_RUNS = 2
POLL_SECONDS = 600
INDEX_ROOT = "https://data.ecmwf.int/forecasts"

# 00/12: 0–144 /3h, 150–240 /6h; probe 246–360 if present
# 06/18 (cycle 50r1): 0–144 /3h
def expected_steps(cycle_hour: int) -> list[int]:
    if cycle_hour in (0, 12):
        return list(range(0, 145, 3)) + list(range(150, 241, 6))
    return list(range(0, 145, 3))


def extra_steps(cycle_hour: int) -> list[int]:
    if cycle_hour in (0, 12):
        return list(range(246, 361, 6))
    return []
