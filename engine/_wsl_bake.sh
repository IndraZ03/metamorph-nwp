#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"
python3 -c "import ecmwf.opendata, cfgrib, eccodes, mercantile, PIL, numpy, xarray; print('imports ok')"
python3 -m engine.run --once --max-steps 3
echo "bake done"
ls -l engine/output/latest.json
python3 - <<'PY'
import json
p = json.load(open("engine/output/latest.json"))
print("run_time", p["run_time"], "run_id", p["run_id"])
print("ready", [s["step"] for s in p["steps"] if s.get("ready")])
print("source", p.get("source"))
PY
