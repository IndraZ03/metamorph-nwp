import time
from functools import wraps
from engine.retention import cleanup, keep_step, layouts, model_lock


def _retained_run(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with model_lock(layouts("icon")[2]):
            cleanup("icon", locked=True)
            try:
                return fn(*args, **kwargs)
            finally:
                cleanup("icon", locked=True)
    return wrapped
from typing import Dict, List, Optional

from .config import PARAMETERS, POLL_INTERVAL_SECONDS
from .downloader import (
    download_step_grib,
    find_latest_active_run,
    get_latest_run_metadata,
)
from .manifest import ManifestManager, prune_old_runs
from .processor import process_grib_to_grid
from .sampler import save_grid_to_disk
from .tiler import TileGenerator

_tiler_instance = None


def get_tiler() -> TileGenerator:
    global _tiler_instance
    if _tiler_instance is None:
        _tiler_instance = TileGenerator()
    return _tiler_instance


def process_step_parameter(
    run_meta: Dict,
    step_int: int,
    param_key: str,
    manifest_mgr: Optional[ManifestManager] = None,
) -> bool:
    """Download, process, tile and record a single parameter at a timestep."""
    if not keep_step(run_meta["run_time_iso"], step_int):
        return False
    res = download_step_grib(run_meta, param_key, step_int)
    if not res:
        return False

    raw_grib, step_info = res
    grid_2d, _ = process_grib_to_grid(raw_grib, param_key)

    if not keep_step(run_meta["run_time_iso"], step_int):
        return False
    # Save 2D grid for sub-millisecond point queries
    save_grid_to_disk(grid_2d, run_meta["run_id"], param_key, step_info["step_str"])

    tiler = get_tiler()
    tiler.generate_tiles_for_step(
        grid_2d,
        param_key,
        run_meta["run_id"],
        step_info["step_str"],
    )

    if manifest_mgr:
        manifest_mgr.record_step_ready(
            step_int=step_int,
            step_str=step_info["step_str"],
            valid_time=step_info["valid_time"],
            param_key=param_key,
        )

    return True


def process_full_step(
    run_meta: Dict,
    step_int: int,
    params: Optional[List[str]] = None,
    manifest_mgr: Optional[ManifestManager] = None,
) -> int:
    """Process all requested parameters for one forecast timestep."""
    if params is None:
        params = list(PARAMETERS.keys())

    if manifest_mgr is None:
        manifest_mgr = ManifestManager(run_meta)

    success_count = 0
    for p in params:
        try:
            ok = process_step_parameter(run_meta, step_int, p, manifest_mgr)
            if ok:
                success_count += 1
        except Exception as e:
            print(f"Error processing {p} step {step_int}: {e}")

    return success_count


@_retained_run
def process_run(
    run_meta: Dict,
    max_steps: Optional[int] = None,
    params: Optional[List[str]] = None,
):
    """
    Ingest a run cycle from DWD.
    Iterates timesteps (e.g. 0 to 120/180).
    Updates manifest after each step so client can immediately view early steps.
    """
    timesteps = run_meta["timesteps"]
    if max_steps is not None:
        timesteps = timesteps[:max_steps]

    print(
        f"Starting ingestion for run {run_meta['run_id']} "
        f"({len(timesteps)} timesteps, params: {params or 'all'})..."
    )

    manifest_mgr = ManifestManager(run_meta)
    wanted = params if params is not None else list(PARAMETERS.keys())

    for i, step in enumerate(timesteps):
        if not keep_step(run_meta["run_time_iso"], step):
            continue
        existing = next(
            (s for s in manifest_mgr.data.get("timesteps", []) if s.get("step") == step),
            None,
        )
        have = existing.get("params", []) if existing else []
        missing = [p for p in wanted if p not in have]
        if not missing:
            print(f"[{i+1}/{len(timesteps)}] Step {step:03d} already complete, skip")
            continue
        t0 = time.time()
        ok_count = process_full_step(run_meta, step, missing, manifest_mgr)
        elapsed = time.time() - t0
        print(
            f"[{i+1}/{len(timesteps)}] Step {step:03d} completed "
            f"({ok_count} params) in {elapsed:.1f}s"
        )

    # Prune older runs
    prune_old_runs()
    print(f"Finished processing run {run_meta['run_id']}!")


def run_poller_daemon(poll_interval: int = POLL_INTERVAL_SECONDS, max_steps: Optional[int] = None):
    """
    Daemon loop polling DWD for new ICON runs.
    """
    print(f"ICON NWP poller daemon active (interval: {poll_interval}s)...")
    last_processed_run = None

    while True:
        try:
            latest_run = find_latest_active_run()
            if latest_run:
                run_id = latest_run["run_id"]
                process_run(latest_run, max_steps=max_steps)
            else:
                print("No active ICON run found on DWD.")
        except Exception as e:
            print(f"Error in poller daemon: {e}")

        time.sleep(poll_interval)
