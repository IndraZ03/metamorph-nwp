from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone

from . import config
from .decode import decode_step
from .fetch import discover_latest_run, discover_via_client, list_index_steps, retrieve_step
from .manifest import (
    empty_manifest,
    mark_step_ready,
    publish_latest,
    read_latest,
    run_id_from_dt,
    write_run_manifest,
)
from .tiles import write_step_tiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ecmwf.run")


def _parse_run(s: str) -> datetime:
    s = s.strip().replace("Z", "")
    for fmt in ("%Y%m%dT%H", "%Y-%m-%dT%H", "%Y%m%d%H"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"bad run id: {s}")


def retain_runs() -> None:
    if not config.RUNS_DIR.exists():
        return
    runs = sorted(
        [p for p in config.RUNS_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    for old in runs[config.RETAIN_RUNS :]:
        log.info("drop old run %s", old.name)
        shutil.rmtree(old, ignore_errors=True)


def _load_run_manifest(run_id: str) -> dict | None:
    path = config.RUNS_DIR / run_id / "manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def process_run(
    run_time: datetime,
    max_steps: int | None = None,
    skip_if_same: bool = True,
    only_steps: list[int] | None = None,
) -> dict | None:
    run_id = run_id_from_dt(run_time)
    hour = run_time.hour
    candidates = config.expected_steps(hour)
    extras = config.extra_steps(hour)
    probe = candidates if max_steps is None else candidates[:max_steps]
    if max_steps is None:
        probe = probe + extras
    found = list_index_steps(run_time, probe)
    if not found:
        log.warning("no index files for %s", run_id)
        found = probe

    existing = _load_run_manifest(run_id) or (
        read_latest() if (read_latest() or {}).get("run_id") == run_id else None
    )
    if existing:
        known = {s["step"] for s in existing.get("steps", [])}
        for step in found:
            if step not in known:
                existing["steps"].append(
                    {
                        "step": step,
                        "valid_time": (run_time.astimezone(timezone.utc) + timedelta(hours=step))
                        .replace(microsecond=0)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "ready": False,
                        "vars": [],
                    }
                )
        existing["steps"].sort(key=lambda s: s["step"])
        manifest = existing
    else:
        manifest = empty_manifest(run_time, found)

    ready_set = {s["step"] for s in manifest["steps"] if s.get("ready")}
    pending = [s for s in found if s not in ready_set]
    if only_steps is not None:
        want = set(only_steps)
        pending = [s for s in pending if s in want]
    if not skip_if_same:
        for row in manifest["steps"]:
            row["ready"] = False
            row["vars"] = []
        pending = list(found)
        ready_set = set()
    if skip_if_same and not pending:
        log.info("run %s already complete (%s steps) — skip", run_id, len(ready_set))
        publish_latest(manifest)
        try:
            from .landslide.processor import process_run as process_landslide
            process_landslide(run_id)
        except Exception:
            log.exception("landslide potential processing failed — prior valid output retained")
        try:
            from .flood.processor import process_run as process_flood
            process_flood(run_id)
        except Exception:
            log.exception("flood indicators processing failed — prior valid output retained")
        return manifest

    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = config.CACHE_DIR / run_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    write_run_manifest(manifest)

    # Invalidate all attempted TP steps before rebuilding. Failed retrieval/retention
    # must never leave older numeric arrays eligible for a new publication.
    from .landslide import config as landslide_config
    for step in pending:
        (landslide_config.TP_DIR / run_id / f"{step}.json").unlink(missing_ok=True)

    for step in pending:
        grib = cache_dir / f"{step}.grib2"
        try:
            retrieve_step(run_time, step, grib)
            fields = decode_step(grib)
            if not fields:
                log.warning("step %s decoded empty", step)
                continue
            if "tp" in fields:
                try:
                    from .landslide.precipitation import retain_tp
                    retain_tp(run_id, run_time, step, fields["tp"], grib)
                except Exception:
                    log.exception("TP provenance retention failed; landslide output disabled for step %s", step)
            vars_ready = write_step_tiles(run_dir, step, fields)
            mark_step_ready(manifest, step, vars_ready)
            publish_latest(manifest)
            try:
                grib.unlink(missing_ok=True)
            except OSError:
                pass
        except Exception:
            log.exception("step %s failed — continue", step)
            continue

    retain_runs()
    try:
        from .landslide.processor import process_run as process_landslide
        process_landslide(run_id)
    except Exception:
        log.exception("landslide potential processing failed — prior valid output retained")
    try:
        from .flood.processor import process_run as process_flood
        process_flood(run_id)
    except Exception:
        log.exception("flood indicators processing failed — prior valid output retained")
    if cache_dir.exists() and not any(cache_dir.iterdir()):
        shutil.rmtree(cache_dir, ignore_errors=True)
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bake ECMWF IFS Indonesia WebP tiles")
    p.add_argument("--once", action="store_true", help="process latest run and exit")
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--run", type=_parse_run, default=None, help="YYYYMMDDTHH UTC")
    p.add_argument("--force", action="store_true", help="rebuild even if latest.json matches")
    p.add_argument(
        "--force-numeric",
        action="store_true",
        help="rebake ready steps that lack numeric tiles (keeps visual)",
    )
    args = p.parse_args(argv)

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_time = args.run
    if run_time is None:
        run_time = discover_via_client() or discover_latest_run()
    if run_time is None:
        log.error("could not discover a live IFS oper run")
        return 1

    log.info("processing run_time=%s", run_time.isoformat())
    only_steps = None
    if args.force_numeric and not args.force:
        run_id = run_id_from_dt(run_time)
        man = _load_run_manifest(run_id) or read_latest()
        if man and man.get("run_id") == run_id:
            now = datetime.now(timezone.utc)
            ready_rows = [row for row in man.get("steps", []) if row.get("ready")]

            def _abs(row):
                try:
                    t = datetime.strptime(row["valid_time"], "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                    return abs((t - now).total_seconds())
                except (KeyError, TypeError, ValueError):
                    return 1e18

            ready_rows.sort(key=_abs)
            limit = args.max_steps if args.max_steps is not None else len(ready_rows)
            target = {row["step"] for row in ready_rows[:limit]}
            num_root = config.OUTPUT_DIR / "numeric" / run_id
            n_mark = 0
            unmarked = []
            for row in man.get("steps", []):
                step = row.get("step")
                if step not in target:
                    continue
                has_num = any(
                    (num_root / vid / str(step)).exists()
                    for vid in (row.get("vars") or ["t2m"])
                )
                if row.get("ready") and not has_num:
                    row["ready"] = False
                    row["vars"] = []
                    n_mark += 1
                    unmarked.append(step)
            man.setdefault("numeric_tiles", config.NUMERIC_TILE_URL_TEMPLATE)
            write_run_manifest(man)
            only_steps = unmarked
            log.info(
                "force-numeric: unmarked %s steps %s missing numeric tiles",
                n_mark,
                sorted(unmarked),
            )
    process_max = None if only_steps is not None else args.max_steps
    manifest = process_run(
        run_time,
        max_steps=process_max,
        skip_if_same=not args.force,
        only_steps=only_steps,
    )
    if manifest is None:
        return 1
    ready = sum(1 for s in manifest["steps"] if s.get("ready"))
    log.info("done run_id=%s ready_steps=%s/%s", manifest["run_id"], ready, len(manifest["steps"]))
    return 0 if ready else 2


if __name__ == "__main__":
    sys.exit(main())
