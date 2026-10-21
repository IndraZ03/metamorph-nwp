"""Safe immutable publication directory retention and dry-run pruning."""
import re
from engine.landslide.storage import read_json
from . import config


def prune_runs(keep=3, dry_run=True):
    if keep < 1:
        raise ValueError("Must keep at least 1 publication")
    if not dry_run:
        raise ValueError("Deletion disabled: active-reader leases are not yet implemented; use dry-run")
    if not config.RUNS_DIR.exists():
        return {"kept": [], "pruned": [], "dry_run": dry_run}
    latest = read_json(config.LATEST_PATH)
    latest_pub = latest.get("publication_id") if latest else None
    runs = sorted([p for p in config.RUNS_DIR.iterdir()
                   if p.is_dir() and re.fullmatch(r"\d{8}T\d{2}-[a-f0-9]{16}", p.name)],
                  key=lambda p: p.stat().st_mtime, reverse=True)
    kept, pruned = [], []
    for idx, run_path in enumerate(runs):
        if idx < keep or run_path.name == latest_pub:
            kept.append(run_path.name)
        else:
            pruned.append(run_path.name)
    return {"kept": kept, "pruned": pruned, "dry_run": dry_run}
