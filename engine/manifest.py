from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config


def run_id_from_dt(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H")


def iso_z(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_manifest(run_time: datetime, steps: list[int]) -> dict:
    run_id = run_id_from_dt(run_time)
    step_rows = []
    for step in steps:
        valid = run_time.astimezone(timezone.utc) + __import__("datetime").timedelta(hours=step)
        step_rows.append(
            {
                "step": step,
                "valid_time": iso_z(valid),
                "ready": False,
                "vars": [],
            }
        )
    return {
        "schema": 1,
        "model": config.MODEL,
        "stream": config.STREAM,
        "resol": config.RESOL,
        "source": "https://data.ecmwf.int",
        "licence": config.LICENCE,
        "attribution": config.ATTRIBUTION,
        "run_time": iso_z(run_time),
        "run_id": run_id,
        "generated_at": iso_z(datetime.now(timezone.utc)),
        "bbox": list(config.BBOX),
        "crs": "EPSG:4326",
        "scheme": "xyz",
        "format": "webp",
        "tile_size": config.TILE_SIZE,
        "minzoom": config.MINZOOM,
        "maxzoom": config.MAXZOOM,
        "tiles": config.TILE_URL_TEMPLATE,
        "numeric_tiles": config.NUMERIC_TILE_URL_TEMPLATE,
        "numeric_encoding": {
            "type": "rgb_int24",
            "offset": 1000.0,
            "scale": 10.0,
            "precision": 0.1,
            "decode_formula": "((R * 65536 + G * 256 + B) / 10.0) - 1000.0",
            "nodata_alpha": 0,
        },
        "default_variable": config.DEFAULT_VARIABLE,
        "variables": [
            {
                "id": v["id"],
                "param": v["param"],
                "units": v["units"],
                "label": v["label"],
            }
            for v in config.VARIABLES
        ],
        "steps": step_rows,
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_run_manifest(manifest: dict) -> Path:
    run_id = manifest["run_id"]
    path = config.RUNS_DIR / run_id / "manifest.json"
    manifest["generated_at"] = iso_z(datetime.now(timezone.utc))
    atomic_write_json(path, manifest)
    return path


def publish_latest(manifest: dict) -> None:
    """Point latest.json at this run once at least one ready step exists."""
    if not any(s.get("ready") for s in manifest.get("steps", [])):
        return
    write_run_manifest(manifest)
    atomic_write_json(config.LATEST_PATH, manifest)


def read_latest() -> dict | None:
    if not config.LATEST_PATH.exists():
        return None
    try:
        return json.loads(config.LATEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def mark_step_ready(manifest: dict, step: int, vars_ready: list[str]) -> None:
    for row in manifest["steps"]:
        if row["step"] == step:
            row["ready"] = True
            row["vars"] = list(vars_ready)
            return
