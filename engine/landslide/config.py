from __future__ import annotations

import math
import os
from pathlib import Path

# Paths
LANDSLIDE_DIR = Path(__file__).resolve().parent
ROOT_DIR = LANDSLIDE_DIR.parent.parent
OUTPUT_DIR = ROOT_DIR / "engine" / "output" / "landslide"
HAZARD_DIR = OUTPUT_DIR / "hazard"
RUNS_DIR = OUTPUT_DIR / "runs"
LATEST_PATH = OUTPUT_DIR / "latest.json"

# BNPB InaRISK ImageServer (Indeks Kerentanan Tanah Longsor)
BNPB_IMAGESERVER_URL = "https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_KERENTANAN_TANAH_LONGSOR/ImageServer"
BNPB_CACHE_TIF = HAZARD_DIR / "bnpb_vulnerability.tif"
BNPB_META_PATH = HAZARD_DIR / "bnpb_meta.json"

# Geographic Domain (matches Indonesia ECMWF domain)
# WGS84 [west, south, east, north]
BBOX = (94.0, -11.5, 141.5, 6.5)

# Yuniawan et al. (2022) baseline threshold (mm/24h)
RAIN_THRESHOLD_24H = float(os.environ.get("LANDSLIDE_RAIN_THRESHOLD_MM", "30.0"))
HAZARD_LOW_MAX = float(os.environ.get("LANDSLIDE_HAZARD_LOW_MAX", "0.333"))
HAZARD_MEDIUM_MAX = float(os.environ.get("LANDSLIDE_HAZARD_MEDIUM_MAX", "0.666"))
if not (0 < HAZARD_LOW_MAX < HAZARD_MEDIUM_MAX < 1) or not math.isfinite(RAIN_THRESHOLD_24H) or RAIN_THRESHOLD_24H <= 0:
    raise ValueError("Invalid experimental landslide thresholds")
METHOD_VERSION = "experimental_v2_vulnerability"
MAX_FORECAST_START = 72
TP_DIR = OUTPUT_DIR / "precipitation"
STATUS_PATH = OUTPUT_DIR / "status.json"

# Vulnerability classes (0..1); HAZARD_* names retained for compatibility.
HAZARD_THRESHOLDS = {
    "low": (0.0, HAZARD_LOW_MAX),
    "medium": (HAZARD_LOW_MAX, HAZARD_MEDIUM_MAX),
    "high": (HAZARD_MEDIUM_MAX, 1.0),
}

# Categorical codes
CODE_NO_TRIGGER = 0
CODE_WASPADA = 1
CODE_SIAGA = 2
CODE_BAHAYA = 3
CODE_NODATA = 255

# RGBA mapping for raster tiles
# 0: Transparent
# 1: Waspada #EAB308
# 2: Siaga   #F97316
# 3: Bahaya  #DC2626
# 255: NoData Transparent
COLOR_TABLE = {
    CODE_NO_TRIGGER: (0, 0, 0, 0),
    CODE_WASPADA: (234, 179, 8, 255),
    CODE_SIAGA: (249, 115, 22, 255),
    CODE_BAHAYA: (220, 38, 38, 255),
    CODE_NODATA: (0, 0, 0, 0),
}

# Tile settings
MINZOOM = 3
MAXZOOM = 6
TILE_SIZE = 256
WEBP_QUALITY = 85
