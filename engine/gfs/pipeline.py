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


def _load_manifest(run: datetime) -> dict | None:
    path = _manifest_path(run)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def _hour_has_keys(run: datetime, forecast_hour: int, keys: list[str]) -> bool:
    valid_name = source.valid_dir_name(run, forecast_hour)
    root = os.path.join(
        config.NUMERIC_TILE_DIR, "gfs", source.run_dir_name(run), valid_name
    )
    for key in keys:
        var_dir = os.path.join(root, key)
        if not os.path.isdir(var_dir):
            return False
        found = False
        for _dirpath, _dirnames, filenames in os.walk(var_dir):
            if any(name.endswith(".webp") for name in filenames):
                found = True
                break
        if not found:
            return False
    return True


def _ordered_timesteps(hours: list[int], by_hour: dict[int, dict]) -> list[dict]:
    ordered = []
    seen = set()
    for fh in hours:
        rec = by_hour.get(fh)
        if rec is not None:
            ordered.append(rec)
            seen.add(fh)
    for fh in sorted(h for h in by_hour if h not in seen):
        ordered.append(by_hour[fh])
    return ordered


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
                 force: bool = False,
                 keys: list[str] | None = None) -> dict:
    """Process one GFS run end-to-end. Returns the manifest dict.

    ``keys`` limits fetch/decode/render (e.g. ``['u10','v10','wind']``) and
    merges into an existing run instead of rebuilding every variable.
    """
    hours = forecast_list if forecast_list is not None else config.forecast_hours()
    if max_hours is not None:
        hours = [h for h in hours if h <= max_hours]
    existing = _load_manifest(run)
    by_hour: dict[int, dict] = {
        int(t["forecast_hour"]): t
        for t in (existing or {}).get("timesteps", [])
        if "forecast_hour" in t
    }
    grib_keys = None if keys is None else [k for k in keys if k in decode.WANTED]
    check_keys = [k for k in (keys or []) if k != "wind"]
    if not force and keys is None and _is_complete(run, len(hours)):
        print(f"run {source.run_dir_name(run)} already complete, skipping")
        return existing
    if (
        not force
        and keys is not None
        and check_keys
        and hours
        and all(_hour_has_keys(run, fh, check_keys) for fh in hours)
    ):
        print(f"run {source.run_dir_name(run)} already has {','.join(check_keys)}, skipping")
        return existing or _load_manifest(run)

    os.makedirs(config.TMP_DIR, exist_ok=True)
    t_start = time.time()
    for chunk_start in range(0, len(hours), config.CHUNK_TIMESTEPS):
        chunk = hours[chunk_start:chunk_start + config.CHUNK_TIMESTEPS]
        for fh in chunk:
            if not force and check_keys and _hour_has_keys(run, fh, check_keys):
                print(f"  f{fh:03d} {','.join(check_keys)} already present, skip")
                continue
            raw_path = os.path.join(config.TMP_DIR, f"gfs_{source.run_dir_name(run)}_f{fh:03d}.grb2")
            try:
                meta = source.download_timestep(run, fh, raw_path, keys=grib_keys)
                grids = decode.decode_timestep(raw_path, keys=keys)
                valid_name = source.valid_dir_name(run, fh)
                out_root = os.path.join(_run_dir(run), valid_name)
                num_root = os.path.join(
                    config.NUMERIC_TILE_DIR, "gfs", source.run_dir_name(run), valid_name
                )
                counts = render.render_timestep(grids, out_root, num_root, keys=keys)
                rec = dict(by_hour.get(fh) or {})
                rec["forecast_hour"] = fh
                rec["valid"] = _fmt(source.valid_time(run, fh))
                if meta.get("rain_step_range"):
                    rec["rain_step_range"] = meta.get("rain_step_range")
                rec["tiles"] = {**(rec.get("tiles") or {}), **counts}
                rec.pop("error", None)
                by_hour[fh] = rec
                print(f"  f{fh:03d} valid={_fmt(source.valid_time(run, fh))} "
                      f"tiles={sum(counts.values())} bytes={meta['bytes']}")
            except Exception as e:
                print(f"  f{fh:03d} FAILED: {e}")
                if fh not in by_hour:
                    by_hour[fh] = {
                        "forecast_hour": fh,
                        "valid": _fmt(source.valid_time(run, fh)),
                        "error": str(e),
                    }
            finally:
                if os.path.exists(raw_path):
                    os.remove(raw_path)
        _write_manifest(run, _ordered_timesteps(hours, by_hour), status="partial")

    timesteps = _ordered_timesteps(hours, by_hour)
    status = (
        "complete"
        if hours and all(
            t.get("forecast_hour") in by_hour and "error" not in by_hour[t["forecast_hour"]]
            for t in ({"forecast_hour": h} for h in hours)
        )
        else "partial"
    )
    manifest = _write_manifest(run, timesteps, status=status)
    _update_latest(run, manifest)
    removed = _cleanup_old_runs()
    print(f"done run {source.run_dir_name(run)} in {time.time() - t_start:.0f}s; "
          f"cleaned old runs: {removed}")
    return manifest


def run_auto(max_hours: int | None = None, force: bool = False,
             keys: list[str] | None = None) -> dict:
    """Find the latest available run and process it (idempotent)."""
    with _lock():
        run = source.find_latest_run()
        print(f"latest run: {source.run_dir_name(run)} ({_fmt(run)})")
        return process_run(run, max_hours=max_hours, force=force, keys=keys)


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
