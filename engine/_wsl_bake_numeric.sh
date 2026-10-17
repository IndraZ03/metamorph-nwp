#!/bin/bash
set -euo pipefail
cd /mnt/c/metamorph-nwp
export PYTHONUNBUFFERED=1
echo "python $(python3 --version)"

echo "=== GFS numeric (f000-f003) ==="
python3 -m engine.gfs.run all --run 2026101706 --max-hours 3 --force
echo "gfs numeric tiles:"
find data/gfs/tiles_numeric -name '*.webp' 2>/dev/null | wc -l

echo "=== ICON numeric (3 steps) ==="
python3 backend/run_engine.py --run-all --max-steps 3
echo "icon numeric tiles:"
find data/tiles_numeric/icon -name '*.webp' 2>/dev/null | wc -l

echo "=== ECMWF numeric (nearest ready step) ==="
python3 -m engine.run --once --run 20261016T18 --force-numeric --max-steps 1
echo "ecmwf numeric tiles:"
find engine/output/numeric -name '*.webp' 2>/dev/null | wc -l

echo "numeric bake done"
