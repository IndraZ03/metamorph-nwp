"""CLI commands for experimental landslide potential."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import config
from .hazard import ingest
from .processor import process_run
from .storage import read_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("landslide.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experimental landslide potential pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_p = subparsers.add_parser("ingest", help="Fetch and cache official BNPB vulnerability raster")
    ingest_p.add_argument("--force", action="store_true", help="Force refresh even if valid cache exists")
    ingest_p.add_argument("--chunk-size", type=int, default=1024, help="Download chunk dimension")

    proc_p = subparsers.add_parser("process", help="Process an ECMWF run into landslide potential")
    proc_p.add_argument("run_id", help="ECMWF run ID (YYYYMMDDTHH)")

    subparsers.add_parser("status", help="Show current landslide processing and data status")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        log.info("Starting BNPB vulnerability raster ingestion...")
        path = ingest(force=args.force, chunk_size=args.chunk_size)
        log.info("Vulnerability raster cached successfully at %s", path)
        return 0

    if args.command == "process":
        log.info("Processing landslide potential for run %s", args.run_id)
        manifest = process_run(args.run_id)
        ready_count = sum(1 for s in manifest["steps"] if s.get("ready"))
        log.info("Successfully published landslide run %s (ready steps: %d/%d)",
                 manifest.get("publication_id", manifest["run_id"]), ready_count, len(manifest["steps"]))
        return 0

    if args.command == "status":
        latest = read_json(config.LATEST_PATH)
        status = read_json(config.STATUS_PATH)
        meta = read_json(config.BNPB_META_PATH)
        if not (latest and latest.get("method_version") == config.METHOD_VERSION
                and latest.get("index_type") == "vulnerability"
                and latest.get("hazard_source", {}).get("source") == config.BNPB_IMAGESERVER_URL):
            latest = None
        output = {
            "index_type": "vulnerability",
            "hazard_cached": config.BNPB_CACHE_TIF.exists(),
            "hazard_metadata": bool(meta),
            "latest_run": latest.get("run_id") if latest else None,
            "publication_id": latest.get("publication_id") if latest else None,
            "status": status,
        }
        print(json.dumps(output, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
