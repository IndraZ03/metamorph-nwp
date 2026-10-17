"""Configuration for the GFS tile engine (Metamorph NWP).

Single source of truth for domain, variables, rendering and pacing.
All paths are relative to the repository root unless absolute.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------- domain
DOMAIN = {
    "lat_min": -11.0,
    "lat_max": 6.0,
    "lon_min": 95.0,
    "lon_max": 141.0,
}

# ---------------------------------------------------------------- source
# NOAA GFS 0.25 deg via AWS Open Data (S3). Range-download per variable
# using the .idx byte offsets (avoids NOMADS CGI throttling).
S3_BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"
USER_AGENT = "metamorph-nwp-gfs-engine/1.0"

# GFS cycles (UTC hours) and availability lag (hours after nominal run time).
GFS_CYCLES = (0, 6, 12, 18)

# Forecast hours: maximal timesteps — hourly 0-120, then 3-hourly to 384.
def forecast_hours() -> list[int]:
    return list(range(0, 121)) + list(range(123, 385, 3))

# ---------------------------------------------------------------- paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.environ.get("GFS_DATA_DIR", os.path.join(REPO_ROOT, "data", "gfs"))
TILE_DIR = os.path.join(DATA_DIR, "tiles")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
LATEST_FILE = os.path.join(DATA_DIR, "latest.json")
LOCK_FILE = os.path.join(DATA_DIR, ".pipeline.lock")

# ---------------------------------------------------------------- tiles
TILE_SIZE = 256
ZOOM_MIN = 0
ZOOM_MAX = 6            # pre-rendered zooms (increase with care: tile count grows ~4x/zoom)
WEBP_QUALITY = 80
WEBP_METHOD = 4

# Keep this many processed runs on disk (older runs are deleted).
RETENTION_RUNS = 2

# ---------------------------------------------------------------- pacing (be polite: S3/NOMADS throttle aggressive clients)
REQUEST_DELAY_S = 0.25      # delay between HTTP requests
MAX_RETRIES = 5
RETRY_BACKOFF_S = 5.0       # multiplied by attempt number
HTTP_TIMEOUT_S = 180
DOWNLOAD_WORKERS = 4        # parallel Range downloads inside one chunk
CHUNK_TIMESTEPS = 8         # process N timesteps per chunk (bounds temp disk)

# ---------------------------------------------------------------- variables
# grib_key: (GRIB shortName/level as in the .idx file) used to select messages.
# step_type: preferred GRIB stepType when a variable has several messages.
# convert: applied to raw values -> display units.
# alpha: 'opaque' | 'threshold' | 'coverage'
# stops: (value, (r, g, b)) control points of the colormap (0-255).

@dataclass
class Variable:
    key: str
    label: str
    unit: str
    grib_var: str
    grib_level: str
    step_type: str | None = None
    convert: str = "identity"   # identity | kelvin_to_c | pa_to_hpa | m_to_mm
    vmin: float = 0.0
    vmax: float = 100.0
    alpha: str = "opaque"
    alpha_threshold: float = 0.0
    stops: list = field(default_factory=list)

def _rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

VARIABLES: dict[str, Variable] = {
    "temperature": Variable(
        key="temperature", label="Temperature 2 m", unit="°C",
        grib_var="TMP", grib_level="2 m above ground",
        convert="kelvin_to_c", vmin=-5, vmax=40,
        stops=[(-5, _rgb("#08306b")), (0, _rgb("#2171b5")), (10, _rgb("#6baed6")),
               (15, _rgb("#c7e9c0")), (20, _rgb("#ffffcc")), (25, _rgb("#ffeda0")),
               (28, _rgb("#fed976")), (30, _rgb("#feb24c")), (33, _rgb("#fd8d3c")),
               (36, _rgb("#fc4e2a")), (40, _rgb("#b10026"))],
    ),
    "dew_point": Variable(
        key="dew_point", label="Dew Point 2 m", unit="°C",
        grib_var="DPT", grib_level="2 m above ground",
        convert="kelvin_to_c", vmin=-5, vmax=30,
        stops=[(-5, _rgb("#08306b")), (0, _rgb("#2171b5")), (10, _rgb("#6baed6")),
               (15, _rgb("#a1d99b")), (20, _rgb("#ffffcc")), (25, _rgb("#feb24c")),
               (30, _rgb("#b10026"))],
    ),
    "rh": Variable(
        key="rh", label="Relative Humidity 2 m", unit="%",
        grib_var="RH", grib_level="2 m above ground",
        vmin=0, vmax=100,
        stops=[(0, _rgb("#ffffff")), (20, _rgb("#e5f5e0")), (40, _rgb("#a1d99b")),
               (60, _rgb("#41ab5d")), (80, _rgb("#238b45")), (90, _rgb("#005a32")),
               (100, _rgb("#002607"))],
    ),
    "pressure": Variable(
        key="pressure", label="Mean Sea Level Pressure", unit="hPa",
        grib_var="PRMSL", grib_level="mean sea level",
        convert="pa_to_hpa", vmin=990, vmax=1020,
        stops=[(990, _rgb("#313695")), (995, _rgb("#4575b4")), (1000, _rgb("#74add1")),
               (1005, _rgb("#abd9e9")), (1010, _rgb("#ffffbf")), (1013, _rgb("#fee090")),
               (1015, _rgb("#fdae61")), (1018, _rgb("#f46d43")), (1020, _rgb("#d73027"))],
    ),
    "rain": Variable(
        key="rain", label="Rain Accumulation (APCP)", unit="mm",
        grib_var="APCP", grib_level="surface", step_type="accum",
        # GFS APCP unit is kg/m², and 1 kg/m² == 1 mm of rain -> identity.
        convert="identity", vmin=0, vmax=50,
        alpha="threshold", alpha_threshold=0.1,
        stops=[(0, _rgb("#ffffff")), (0.1, _rgb("#cfe8ff")), (1, _rgb("#7fbfff")),
               (2.5, _rgb("#3f8fff")), (5, _rgb("#0057d9")), (10, _rgb("#00c853")),
               (20, _rgb("#ffeb00")), (30, _rgb("#ff7b00")), (50, _rgb("#b10026"))],
    ),
    "cape": Variable(
        key="cape", label="CAPE", unit="J/kg",
        grib_var="CAPE", grib_level="surface",
        vmin=0, vmax=4000,
        stops=[(0, _rgb("#ffffff")), (250, _rgb("#ffffcc")), (500, _rgb("#ffeda0")),
               (1000, _rgb("#fed976")), (1500, _rgb("#feb24c")), (2000, _rgb("#fd8d3c")),
               (2500, _rgb("#fc4e2a")), (3000, _rgb("#e31a1c")), (4000, _rgb("#800026"))],
    ),
    "clouds": Variable(
        key="clouds", label="Total Cloud Cover", unit="%",
        grib_var="TCDC", grib_level="entire atmosphere", step_type="avg",
        vmin=0, vmax=100, alpha="coverage",
        stops=[(0, _rgb("#ffffff")), (100, _rgb("#d9d9d9"))],
    ),
}

# Tile URL template (relative to the tile server root).
TILE_URL_TEMPLATE = "/tiles/gfs/{run}/{valid}/{variable}/{z}/{x}/{y}.webp"
