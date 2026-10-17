#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
echo "start $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== GFS 48h (visual + numeric) ==="
python3 -c "import numpy, PIL, eccodes; print('gfs imports ok')"
python3 -m engine.gfs.run latest
python3 -m engine.gfs.run all --run auto --max-hours 48
echo "gfs bake done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PY'
import json, os
p = "data/gfs/latest.json"
if os.path.exists(p):
    d = json.load(open(p))
    print("gfs run", d.get("run"), "timesteps", len(d.get("timesteps") or []))
else:
    print("no gfs latest.json")
PY

echo "=== ICON 48 steps (visual + numeric) ==="
python3 -c "import numpy, PIL, eccodes, scipy; print('icon imports ok')"
python3 backend/run_engine.py --run-all --max-steps 48
echo "icon bake done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
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

echo "long bake done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
