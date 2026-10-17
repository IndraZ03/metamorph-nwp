#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
python3 -c "import numpy, PIL, eccodes, scipy; print('icon imports ok')"
python3 backend/run_engine.py --run-all --max-steps 3
echo "icon bake done"
ls -l data/tiles/icon/latest_manifest.json 2>/dev/null || ls data/tiles/icon 2>/dev/null || true
python3 - <<'PY'
import json, os
from pathlib import Path
p = Path("data/tiles/icon/latest_manifest.json")
if not p.exists():
    runs = sorted([d for d in Path("data/tiles/icon").glob("*") if d.is_dir()], reverse=True)
    if runs:
        p = runs[0] / "manifest.json"
if p.exists():
    d = json.load(open(p))
    print("run", d.get("run_id"), "steps", len(d.get("timesteps") or []))
else:
    print("no icon manifest")
PY
