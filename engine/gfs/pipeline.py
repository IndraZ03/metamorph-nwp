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
from engine.retention import atomic_write_json, cleanup, keep_step, model_lock, prune_manifest


# ---------------------------------------------------------------- helpers

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _lock():
    with model_lock(config.LOCK_FILE):
        cleanup("gfs", locked=True)
        try:
            yield
        finally:
            cleanup("gfs", locked=True)


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
        ts = prune_manifest(man).get("timesteps", [])
        return (
            man.get("status") == "complete"
            and ({int(t['forecast_hour']) for t in ts} == set(expected) if not isinstance(expected, int) else len(ts) == expected)
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
    prune_manifest(man)
    atomic_write_json(path, man)
    return man


def _ready_timesteps(manifest: dict | None) -> list[dict]:
    return [row for row in (manifest or {}).get("timesteps", []) if isinstance(row, dict) and "error" not in row and row.get("valid")]


def _read_latest_run() -> datetime | None:
    try:
        with open(config.LATEST_FILE, encoding="utf-8") as fh:
            raw = json.load(fh).get("run")
        if not raw:
            return None
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (OSError, ValueError, TypeError):
        return None


def _update_latest(run: datetime, manifest: dict) -> bool:
    """Publish a run that still has usable timesteps. Never move latest backward."""
    if not _ready_timesteps(manifest):
        return False
    current = _read_latest_run()
    candidate = run if run.tzinfo else run.replace(tzinfo=timezone.utc)
    if current is not None and candidate < current:
        return False
    os.makedirs(os.path.dirname(config.LATEST_FILE), exist_ok=True)
    atomic_write_json(config.LATEST_FILE, {
            "model": "GFS",
            "run": _fmt(run),
            "generated_at": _utcnow(),
            "manifest": f"/api/gfs/runs/{source.run_dir_name(run)}/manifest.json",
            "timesteps": manifest.get("timesteps", []),
        })
    return True


def _cleanup_old_runs(keep: int = config.RETENTION_RUNS) -> list[str]:
    return cleanup("gfs", locked=True)["removed"]


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
    hours = [h for h in hours if keep_step(run, h)]
    existing = _load_manifest(run)
    if existing:
        prune_manifest(existing)
    by_hour: dict[int, dict] = {
        int(t["forecast_hour"]): t
        for t in (existing or {}).get("timesteps", [])
        if "forecast_hour" in t
    }
    grib_keys = None if keys is None else [k for k in keys if k in decode.WANTED]
    check_keys = [k for k in (keys or []) if k != "wind"]
    if not force and keys is None and _is_complete(run, hours):
        print(f"run {source.run_dir_name(run)} already complete, skipping")
        _update_latest(run, existing)
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
            if not keep_step(run, fh):
                continue
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
                if not keep_step(run, fh):
                    continue
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
        _update_latest(run, _write_manifest(run, _ordered_timesteps(hours, by_hour), status="partial"))

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
