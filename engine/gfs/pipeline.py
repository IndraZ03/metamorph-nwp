"""Pipeline orchestration: fetch -> decode -> render -> manifest.

Idempotent: a run with a complete manifest is skipped.
Chunked: timesteps are processed in small chunks so temp disk stays low.
Lock file prevents two pipelines from running at once.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config, decode, render, source


# ---------------------------------------------------------------- helpers

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _lock():
    os.makedirs(os.path.dirname(config.LOCK_FILE), exist_ok=True)
    if os.path.exists(config.LOCK_FILE):
        raise RuntimeError(f"pipeline already running (lock exists: {config.LOCK_FILE})")
    with open(config.LOCK_FILE, "w") as fh:
        fh.write(str(os.getpid()))
    try:
        yield
    finally:
        if os.path.exists(config.LOCK_FILE):
            os.remove(config.LOCK_FILE)


def _run_dir(run: datetime) -> str:
    return os.path.join(config.TILE_DIR, "gfs", source.run_dir_name(run))


def _manifest_path(run: datetime) -> str:
    return os.path.join(_run_dir(run), "manifest.json")


def _is_complete(run: datetime, expected: int) -> bool:
    path = _manifest_path(run)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as fh:
            man = json.load(fh)
        ts = man.get("timesteps", [])
        return (
            man.get("status") == "complete"
            and len(ts) == expected
            and all("error" not in t for t in ts)
        )
    except Exception:
        return False


def _variable_meta() -> dict:
    out = {}
    for key, var in config.VARIABLES.items():
        out[key] = {
            "label": var.label,
            "unit": var.unit,
            "min": var.vmin,
            "max": var.vmax,
            "alpha": var.alpha,
            "stops": [[v, list(rgb)] for v, rgb in var.stops],
        }
    return out


def _write_manifest(run: datetime, timesteps: list[dict], status: str) -> dict:
    man = {
        "model": "GFS",
        "resolution_deg": 0.25,
        "run": _fmt(run),
        "generated_at": _utcnow(),
        "status": status,
        "domain": dict(config.DOMAIN),
        "tile_url_template": config.TILE_URL_TEMPLATE,
        "numeric_tile_url_template": config.NUMERIC_TILE_URL_TEMPLATE,
        "numeric_encoding": {
            "type": "rgb_int24",
            "offset": 1000.0,
            "scale": 10.0,
            "precision": 0.1,
            "decode_formula": "((R * 65536 + G * 256 + B) / 10.0) - 1000.0",
            "nodata_alpha": 0,
        },
        "zoom_min": config.ZOOM_MIN,
        "zoom_max": config.ZOOM_MAX,
        "timesteps": timesteps,
        "variables": _variable_meta(),
    }
    path = _manifest_path(run)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(man, fh, indent=1)
    return man


def _update_latest(run: datetime, manifest: dict) -> None:
    os.makedirs(os.path.dirname(config.LATEST_FILE), exist_ok=True)
    with open(config.LATEST_FILE, "w") as fh:
        json.dump({
            "model": "GFS",
            "run": _fmt(run),
            "generated_at": _utcnow(),
            "manifest": f"/api/gfs/runs/{source.run_dir_name(run)}/manifest.json",
            "timesteps": manifest.get("timesteps", []),
        }, fh, indent=1)


def _cleanup_old_runs(keep: int = config.RETENTION_RUNS) -> list[str]:
    removed = []
    for base in (
        os.path.join(config.TILE_DIR, "gfs"),
        os.path.join(config.NUMERIC_TILE_DIR, "gfs"),
    ):
        if not os.path.isdir(base):
            continue
        runs = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
        for old in runs[:-keep] if len(runs) > keep else []:
            shutil.rmtree(os.path.join(base, old), ignore_errors=True)
            if old not in removed:
                removed.append(old)
    return removed


# ---------------------------------------------------------------- main

def process_run(run: datetime, max_hours: int | None = None,
                 forecast_list: list[int] | None = None,
                 force: bool = False) -> dict:
    """Process one GFS run end-to-end. Returns the manifest dict."""
    hours = forecast_list if forecast_list is not None else config.forecast_hours()
    if max_hours is not None:
        hours = [h for h in hours if h <= max_hours]
    if not force and _is_complete(run, len(hours)):
        print(f"run {source.run_dir_name(run)} already complete, skipping")
        with open(_manifest_path(run)) as fh:
            return json.load(fh)

    os.makedirs(config.TMP_DIR, exist_ok=True)
    timesteps: list[dict] = []
    t_start = time.time()
    for chunk_start in range(0, len(hours), config.CHUNK_TIMESTEPS):
        chunk = hours[chunk_start:chunk_start + config.CHUNK_TIMESTEPS]
        for fh in chunk:
            raw_path = os.path.join(config.TMP_DIR, f"gfs_{source.run_dir_name(run)}_f{fh:03d}.grb2")
            try:
                meta = source.download_timestep(run, fh, raw_path)
                grids = decode.decode_timestep(raw_path)
                valid_name = source.valid_dir_name(run, fh)
                out_root = os.path.join(_run_dir(run), valid_name)
                num_root = os.path.join(
                    config.NUMERIC_TILE_DIR, "gfs", source.run_dir_name(run), valid_name
                )
                counts = render.render_timestep(grids, out_root, num_root)
                timesteps.append({
                    "forecast_hour": fh,
                    "valid": _fmt(source.valid_time(run, fh)),
                    "rain_step_range": meta.get("rain_step_range"),
                    "tiles": counts,
                })
                print(f"  f{fh:03d} valid={_fmt(source.valid_time(run, fh))} "
                      f"tiles={sum(counts.values())} bytes={meta['bytes']}")
            except Exception as e:
                print(f"  f{fh:03d} FAILED: {e}")
                timesteps.append({"forecast_hour": fh,
                                  "valid": _fmt(source.valid_time(run, fh)),
                                  "error": str(e)})
            finally:
                if os.path.exists(raw_path):
                    os.remove(raw_path)
        # progress manifest after every chunk (resumable)
        _write_manifest(run, timesteps, status="partial")

    manifest = _write_manifest(run, timesteps, status="complete")
    _update_latest(run, manifest)
    removed = _cleanup_old_runs()
    print(f"done run {source.run_dir_name(run)} in {time.time() - t_start:.0f}s; "
          f"cleaned old runs: {removed}")
    return manifest


def run_auto(max_hours: int | None = None, force: bool = False) -> dict:
    """Find the latest available run and process it (idempotent)."""
    with _lock():
        run = source.find_latest_run()
        print(f"latest run: {source.run_dir_name(run)} ({_fmt(run)})")
        return process_run(run, max_hours=max_hours, force=force)


def list_runs() -> list[dict]:
    base = os.path.join(config.TILE_DIR, "gfs")
    out = []
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        mpath = os.path.join(base, d, "manifest.json")
        if os.path.exists(mpath):
            try:
                with open(mpath) as fh:
                    man = json.load(fh)
                out.append({"run": man.get("run"), "dir": d,
                            "status": man.get("status"),
                            "timesteps": len(man.get("timesteps", []))})
            except Exception:
                out.append({"run": d, "dir": d, "status": "unreadable", "timesteps": 0})
    return out
