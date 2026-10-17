import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
TILES_DIR = DATA_DIR / "tiles" / "icon"

for d in (CACHE_DIR, TILES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Indonesia Bounding Box with buffer
BBOX_LAT_MIN = -15.0
BBOX_LAT_MAX = 12.0
BBOX_LON_MIN = 88.0
BBOX_LON_MAX = 148.0

GRID_RES_DEG = 0.05  # ~5.5 km regular grid

ZOOM_MIN = 4
ZOOM_MAX = 7

DWD_BASE_URL = "https://opendata.dwd.de/weather/nwp/icon/grib"

# Parameter configurations
PARAMETERS = {
    "t_2m": {
        "dwd_folder": "t_2m",
        "dwd_var": "T_2M",
        "name": "Temperature 2m",
        "unit": "°C",
        "convert": lambda val: val - 273.15,
        "range": [-10.0, 45.0],
        "is_accum": False,
    },
    "relhum_2m": {
        "dwd_folder": "relhum_2m",
        "dwd_var": "RELHUM_2M",
        "name": "Relative Humidity",
        "unit": "%",
        "convert": lambda val: val,
        "range": [0.0, 100.0],
        "is_accum": False,
    },
    "tot_prec": {
        "dwd_folder": "tot_prec",
        "dwd_var": "TOT_PREC",
        "name": "Rain Accumulation",
        "unit": "mm",
        "convert": lambda val: val,
        "range": [0.0, 250.0],
        "is_accum": True,
    },
    "pmsl": {
        "dwd_folder": "pmsl",
        "dwd_var": "PMSL",
        "name": "Mean Sea Level Pressure",
        "unit": "hPa",
        "convert": lambda val: val / 100.0,
        "range": [996.0, 1020.0],
        "is_accum": False,
    },
    "td_2m": {
        "dwd_folder": "td_2m",
        "dwd_var": "TD_2M",
        "name": "Dew Point 2m",
        "unit": "°C",
        "convert": lambda val: val - 273.15,
        "range": [10.0, 32.0],
        "is_accum": False,
    },
    "cape_ml": {
        "dwd_folder": "cape_ml",
        "dwd_var": "CAPE_ML",
        "name": "CAPE (Mixed Layer)",
        "unit": "J/kg",
        "convert": lambda val: val,
        "range": [0.0, 4000.0],
        "is_accum": False,
    },
    "clct": {
        "dwd_folder": "clct",
        "dwd_var": "CLCT",
        "name": "Total Cloud Cover",
        "unit": "%",
        "convert": lambda val: val,
        "range": [0.0, 100.0],
        "is_accum": False,
    },
}

RETENTION_RUNS = 2
POLL_INTERVAL_SECONDS = 900  # 15 minutes
