import argparse
import sys
from pathlib import Path

# Ensure backend package in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.engine.config import PARAMETERS
from backend.engine.downloader import find_latest_active_run
from backend.engine.manifest import ManifestManager
from backend.engine.scheduler import (
    process_full_step,
    process_run,
    process_step_parameter,
    run_poller_daemon,
)


def main():
    parser = argparse.ArgumentParser(
        description="Metamorph NWP — ICON Engine CLI & Tile Server"
    )
    parser.add_argument(
        "--test-step",
        type=int,
        help="Process a single test step (e.g. 0 for step 000).",
    )
    parser.add_argument(
        "--param",
        type=str,
        choices=list(PARAMETERS.keys()),
        help="Specific parameter to process. If omitted, all 7 parameters are processed.",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Download and process all timesteps for the latest run.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        help="Cap maximum steps when using --run-all or --daemon.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start background poller daemon to auto-update on new runs.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start FastAPI tile server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for tile server (default: 8000).",
    )

    args = parser.parse_args()

    if args.serve:
        import uvicorn

        print(f"Starting Metamorph NWP ICON Tile API on port {args.port}...")
        uvicorn.run("backend.app:app", host="0.0.0.0", port=args.port, reload=False)
        return

    if args.daemon:
        run_poller_daemon(max_steps=args.max_steps)
        return

    if args.test_step is not None:
        print("Locating latest ICON run on DWD...")
        run_meta = find_latest_active_run()
        if not run_meta:
            print("Failed: No active run found on DWD.")
            sys.exit(1)

        print(
            f"Processing step {args.test_step:03d} for run {run_meta['run_id']} "
            f"(param: {args.param or 'all 7 parameters'})..."
        )
        manifest_mgr = ManifestManager(run_meta)

        if args.param:
            ok = process_step_parameter(run_meta, args.test_step, args.param, manifest_mgr)
            print(f"Result: {'SUCCESS' if ok else 'FAILED'}")
        else:
            count = process_full_step(run_meta, args.test_step, None, manifest_mgr)
            print(f"Processed {count}/{len(PARAMETERS)} parameters successfully.")
        return

    if args.run_all:
        run_meta = find_latest_active_run()
        if not run_meta:
            print("Failed: No active run found on DWD.")
            sys.exit(1)

        params = [args.param] if args.param else None
        process_run(run_meta, max_steps=args.max_steps, params=params)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
