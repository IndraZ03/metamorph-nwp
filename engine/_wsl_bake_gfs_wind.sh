#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
echo "gfs wind bake start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import numpy, PIL, eccodes; print('gfs imports ok')"
# Pin the already-baked 48h run. Do not auto-switch to a newer cycle.
python3 -m engine.gfs.run all --run 2026101712 --max-hours 48 --vars u10,v10,wind
echo "gfs wind bake done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("data/gfs/latest.json")
if p.exists():
    d = json.load(open(p))
    print("gfs run", d.get("run"), "timesteps", len(d.get("timesteps") or []))
else:
    print("no gfs latest.json")
root = Path("data/gfs/tiles_numeric/gfs/2026101712")
u = list(root.glob("*/u10/**/*.webp")) if root.exists() else []
v = list(root.glob("*/v10/**/*.webp")) if root.exists() else []
print("numeric u10 files", len(u), "v10 files", len(v))
PY
