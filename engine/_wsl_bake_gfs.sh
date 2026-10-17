#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
python3 -c "import numpy, PIL, eccodes; print('gfs imports ok')"
python3 -m engine.gfs.run latest
python3 -m engine.gfs.run all --run auto --max-hours 3
echo "gfs bake done"
ls -l data/gfs/latest.json 2>/dev/null || true
python3 - <<'PY'
import json, os
p = "data/gfs/latest.json"
if os.path.exists(p):
    d = json.load(open(p))
    print("run", d.get("run"), "timesteps", len(d.get("timesteps") or []))
else:
    print("no latest.json")
PY
