"""CLI for the GFS tile engine.

Usage (from the repository root):
  python -m engine.gfs.run all [--run auto|YYYYMMDDHH] [--max-hours N]
  python -m engine.gfs.run latest
  python -m engine.gfs.run list
  python -m engine.gfs.run serve [--port 8080] [--host 0.0.0.0]
  python -m engine.gfs.run cleanup [--keep 2]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import pipeline, server, source


def _parse_run(value: str) -> datetime:
    if value == "auto":
        return source.find_latest_run()
    return datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="engine.gfs.run")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("all", help="process one run end-to-end")
    p_all.add_argument("--run", default="auto", help="auto or YYYYMMDDHH")
    p_all.add_argument("--max-hours", type=int, default=None,
                       help="only process forecast hours <= N (testing)")
    p_all.add_argument("--force", action="store_true",
                       help="rebuild even if the run is already complete")
    p_all.add_argument("--vars", default=None,
                       help="comma-separated variable keys (e.g. u10,v10,wind)")

    sub.add_parser("latest", help="show latest available run on S3")
    sub.add_parser("list", help="list processed runs on disk")
    p_srv = sub.add_parser("serve", help="start the tile server")
    p_srv.add_argument("--port", type=int, default=8080)
    p_srv.add_argument("--host", default="0.0.0.0")
    p_cl = sub.add_parser("cleanup", help="delete old runs, keep N newest")
    p_cl.add_argument("--keep", type=int, default=2)

    args = ap.parse_args(argv)
    if args.cmd == "all":
        keys = [s.strip() for s in args.vars.split(",") if s.strip()] if args.vars else None
        if args.run == "auto":
            pipeline.run_auto(max_hours=args.max_hours, force=args.force, keys=keys)
        else:
            run = _parse_run(args.run)
            with pipeline._lock():
                pipeline.process_run(
                    run, max_hours=args.max_hours, force=args.force, keys=keys
                )
    elif args.cmd == "latest":
        run = source.find_latest_run()
        print(f"latest run: {source.run_dir_name(run)} ({run:%Y-%m-%dT%H:%M:%SZ})")
    elif args.cmd == "list":
        for r in pipeline.list_runs():
            print(r)
    elif args.cmd == "serve":
        server.serve(port=args.port, host=args.host)
    elif args.cmd == "cleanup":
        print("removed:", pipeline._cleanup_old_runs(keep=args.keep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
