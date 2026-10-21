"""Hidden hourly forecast updater; no work runs at import time."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import subprocess
import sys
import threading
import time
from .retention import atomic_write_json, cleanup, model_lock
from .network import configure_tls
from datetime import datetime, timezone, timedelta
import json

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "updater"
LOG = logging.getLogger("hourly")
COMMANDS = {
    "ecmwf": ["-m", "engine.run", "--once"],
    "gfs": ["-m", "engine.gfs.run", "all"],
    "icon": ["-m", "engine.hourly", "--icon-once"],
}
DEPENDENCIES = ("numpy", "PIL", "eccodes", "cfgrib", "ecmwf.opendata", "scipy", "xarray", "mercantile", "matplotlib", "httpx")


def preflight():
    missing = []
    for name in DEPENDENCIES:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ModuleNotFoundError):
            missing.append(name)
    if missing:
        raise RuntimeError("Missing runtime dependencies: " + ", ".join(missing))
    configure_tls()
    import eccodes
    handle = eccodes.codes_grib_new_from_samples("GRIB2")
    try:
        eccodes.codes_get_values(handle)
    finally:
        eccodes.codes_release(handle)


def run_model(model, timeout=21600, executable=None):
    if executable is None:
        executable = str(Path(sys.executable).with_name("python.exe")) if os.name == "nt" else sys.executable
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with subprocess.Popen([executable, "-u", *COMMANDS[model]], cwd=ROOT,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace", creationflags=flags) as child:
            def drain():
                for line in child.stdout:
                    LOG.info("%s %s", model, line.rstrip())
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                LOG.error("%s timeout after %ss", model, timeout)
                return False
            finally:
                reader.join()
            LOG.info("%s exit=%s (pipeline exit, inspect manifest for completeness)", model, child.returncode)
            return child.returncode == 0
    except Exception:
        LOG.exception("%s subprocess failed", model)
        return False


def health_snapshot():
    from .health import check_all
    models = check_all(root=ROOT, timeout=20)
    now = datetime.now(timezone.utc).isoformat()
    previous = {}
    try:
        previous = json.loads((STATE / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for name, result in models.items():
        old = previous.get("models", {}).get(name, {})
        result["last_verified_at"] = now if result.get("fresh") is True and result.get("complete") else old.get("last_verified_at")
    atomic_write_json(STATE / "status.json", {"checked_at": now, "models": models})
    for name, result in models.items():
        LOG.info("health %s status=%s local=%s upstream=%s complete=%s issues=%s",
                 name, result.get("status"), result.get("local_run"),
                 result.get("upstream_run"), result.get("complete"), result.get("issues"))
    return models


def cycle(timeout=21600):
    cleanup_ok = True
    health_snapshot()
    for model in COMMANDS:
        try:
            inventory = cleanup(model)
            cleanup_ok = cleanup_ok and "error" not in inventory
            LOG.info("initial cleanup %s removed=%d error=%s", model, len(inventory.get("removed", [])), inventory.get("error"))
        except Exception:
            cleanup_ok = False
            LOG.exception("initial cleanup failed %s", model)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(zip(COMMANDS, pool.map(lambda model: run_model(model, timeout), COMMANDS)))
    for model in COMMANDS:
        try:
            inventory = cleanup(model)
            cleanup_ok = cleanup_ok and "error" not in inventory
            LOG.info("final cleanup %s removed=%d error=%s", model, len(inventory.get("removed", [])), inventory.get("error"))
        except Exception:
            LOG.exception("final cleanup failed %s", model)
            results[model] = False
    verified = health_snapshot()
    return cleanup_ok and all(results.values()) and all(
        item.get("fresh") is True and item.get("complete") for item in verified.values()
    )


def daemon(interval, timeout, once=False, clock=time.monotonic, wait=None):
    wait = wait or threading.Event().wait
    while True:
        started = clock()
        success = cycle(timeout)
        if once:
            return 0 if success else 1
        # No catch-up: long cycles wait one interval rather than spin.
        elapsed = clock() - started
        delay = interval - elapsed if elapsed < interval else interval
        if not success:
            delay = min(delay, 300)
        wait(delay)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--icon-once", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--interval", type=float, default=3600)
    parser.add_argument("--timeout", type=float, default=21600)
    args = parser.parse_args(argv)
    if args.interval <= 0 or args.timeout <= 0:
        parser.error("interval and timeout must be positive")
    STATE.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(STATE / "hourly.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    try:
        if args.preflight:
            preflight()
            return 0
        configure_tls()
        if args.icon_once:
            from backend.engine.downloader import find_latest_active_run
            from backend.engine.scheduler import process_run
            run = find_latest_active_run()
            if not run:
                return 1
            process_run(run)
            return 0
        preflight()
        with model_lock(STATE / "hourly.lock"):
            return daemon(args.interval, args.timeout, args.once)
    except Exception:
        LOG.exception("updater failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
