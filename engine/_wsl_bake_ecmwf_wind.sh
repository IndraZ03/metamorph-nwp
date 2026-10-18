#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
echo "ecmwf wind bake start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import numpy, PIL; print('ecmwf imports ok')"
# Fill missing 10 m wind on the published run. Do not rebuild other vars.
python3 -m engine.run --run 20261016T18 --vars wind10m,u10,v10
echo "ecmwf wind bake done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("engine/output/latest.json")
if p.exists():
    d = json.load(open(p))
    steps = d.get("steps") or []
    wind = sum(1 for s in steps if "wind10m" in (s.get("vars") or []))
    print("ecmwf run", d.get("run_id"), "steps", len(steps), "with wind10m", wind)
else:
    print("no ecmwf latest.json")
root = Path("engine/output/numeric/20261016T18")
u = list(root.glob("u10/**/*.webp")) if root.exists() else []
v = list(root.glob("v10/**/*.webp")) if root.exists() else []
w = list(root.glob("wind10m/**/*.webp")) if root.exists() else []
print("numeric u10", len(u), "v10", len(v), "wind10m", len(w))
PY
