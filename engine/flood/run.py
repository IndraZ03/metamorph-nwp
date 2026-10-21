"""CLI commands for experimental flood indicators pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from . import config, bnpb
from .processor import process_run
from engine.landslide.storage import read_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("flood.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experimental Indonesia flood indicators pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke_p = subparsers.add_parser("smoke-export", help="Smoke test small raw Float32 TIFF export from BNPB")
    smoke_p.add_argument("--kind", choices=["hazard", "vulnerability"], default="hazard")
    smoke_p.add_argument("--out-dir", default="data/tmp_flood_smoke")

    ingest_p = subparsers.add_parser("ingest", help="Ingest official national continuous BNPB raster")
    ingest_p.add_argument("--kind", choices=["hazard", "vulnerability"], required=True)
    ingest_p.add_argument("--force", action="store_true", help="Force refresh even if cache valid")
    ingest_p.add_argument("--chunk-size", type=int, default=1024)

    proc_p = subparsers.add_parser("process", help="Precompute trailing P24, antecedent, and flood indicators")
    proc_p.add_argument("run_id", help="ECMWF run ID (YYYYMMDDTHH)")

    subparsers.add_parser("status", help="Show current flood indicator status")

    prune_p = subparsers.add_parser("prune", help="Safely prune old publication runs")
    prune_p.add_argument("--keep", type=int, default=3, help="Number of latest publications to retain")
    prune_p.add_argument("--apply", action="store_true", help="Reserved; deletion disabled until active-reader leases exist")

    args = parser.parse_args(argv)

    if args.command == "smoke-export":
        url = config.SOURCES[args.kind]
        log.info("Smoke testing raw Float32 export for %s...", args.kind)
        res = bnpb.smoke_test_raw_export(url, args.out_dir)
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "ingest":
        url = config.SOURCES[args.kind]
        target_tif = config.SOURCES_DIR / args.kind / "raw.tif"
        meta_json = config.SOURCES_DIR / args.kind / "latest.json"
        log.info("Ingesting BNPB %s raster...", args.kind)
        p = bnpb.ingest_layer(url, target_tif, meta_json, config.BBOX, layer_type=args.kind,
                              chunk_size=args.chunk_size, force=args.force)
        log.info("Successfully ingested %s to %s", args.kind, p)
        return 0

    if args.command == "process":
        log.info("Processing flood indicators for run %s...", args.run_id)
        manifest = process_run(args.run_id)
        ready_count = sum(1 for s in manifest["steps"] if s.get("ready"))
        log.info("Published flood run %s (ready steps: %d/%d)",
                 manifest["publication_id"], ready_count, len(manifest["steps"]))
        return 0

    if args.command == "status":
        latest = read_json(config.LATEST_PATH)
        status = read_json(config.STATUS_PATH)
        output = {
            "product": "indonesia_flood_potential",
            "method_version": config.METHOD_VERSION,
            "latest_run": latest.get("run_id") if latest else None,
            "publication_id": latest.get("publication_id") if latest else None,
            "status": status,
        }
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "prune":
        from .prune import prune_runs
        summary = prune_runs(keep=args.keep, dry_run=not args.apply)
        print(json.dumps(summary, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
