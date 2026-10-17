#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
echo "icon resume start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import numpy, PIL, eccodes, scipy; print('icon imports ok')"
python3 - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(".").resolve()))

from backend.engine.scheduler import process_run

run_dt = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
run_meta = {
    "cycle": "12",
    "date_str": "20261017",
    "run_id": "2026101712",
    "run_time_iso": "2026-10-17T12:00:00Z",
    "run_dt": run_dt,
    "timesteps": list(range(48)),
    "count": 48,
}
process_run(run_meta, max_steps=48)
PY
echo "icon resume done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("data/tiles/icon/latest_manifest.json")
if p.exists():
    d = json.load(open(p))
    print("icon run", d.get("run_id"), "steps", len(d.get("timesteps") or []))
else:
    print("no icon latest_manifest.json")
PY
