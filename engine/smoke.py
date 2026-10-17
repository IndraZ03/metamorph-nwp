"""Synthetic Indonesia fields → WebP tiles. No eccodes / network. For MapLibre hook."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from . import config
from .manifest import empty_manifest, mark_step_ready, publish_latest
from .tiles import write_step_tiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ecmwf.smoke")


def _grid() -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = config.BBOX
    lons = np.arange(west, east + 1e-9, 0.25)
    lats = np.arange(north, south - 1e-9, -0.25)
    return lats, lons


def _fields(lats, lons) -> dict:
    lon2d, lat2d = np.meshgrid(lons, lats)
    t2m = 26.0 - 0.15 * np.abs(lat2d) + 4.0 * np.sin(np.radians(lon2d))
    d2m = t2m - 4.0
    rh = np.clip(70.0 + 10.0 * np.cos(np.radians(lon2d)), 0, 100)
    msl = 1010.0 + 4.0 * np.sin(np.radians(lat2d * 8))
    tp = np.clip(20.0 * np.exp(-((lon2d - 110) ** 2 + (lat2d + 2) ** 2) / 80.0), 0, None)
    cape = np.clip(1500.0 * np.exp(-((lon2d - 120) ** 2 + lat2d**2) / 60.0), 0, None)
    tcc = np.clip(0.4 + 0.4 * np.sin(np.radians(lon2d * 3)), 0, 1)
    pack = lambda v: {"lats": lats, "lons": lons, "values": v}
    return {
        "t2m": pack(t2m),
        "d2m": pack(d2m),
        "rh": pack(rh),
        "msl": pack(msl),
        "tp": pack(tp),
        "cape": pack(cape),
        "tcc": pack(tcc),
    }


def main() -> int:
    run_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    run_time = run_time.replace(hour=(run_time.hour // 6) * 6)
    steps = [0, 3]
    manifest = empty_manifest(run_time, steps)
    run_dir = config.RUNS_DIR / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    lats, lons = _grid()
    fields = _fields(lats, lons)
    for step in steps:
        vars_ready = write_step_tiles(run_dir, step, fields)
        mark_step_ready(manifest, step, vars_ready)
        publish_latest(manifest)
        log.info("smoke step %s vars=%s", step, vars_ready)
    log.info("wrote %s", config.LATEST_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
