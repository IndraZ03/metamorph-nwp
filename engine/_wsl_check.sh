#!/bin/bash
set -e
python3 - <<'PY'
import sys
print("python", sys.version)
mods = ["cfgrib", "xarray", "numpy", "PIL", "eccodes", "mercantile"]
for m in mods:
    try:
        __import__(m)
        print("ok", m)
    except Exception as e:
        print("missing", m, type(e).__name__, e)
try:
    import ecmwf.opendata
    print("ok ecmwf.opendata")
except Exception as e:
    print("missing ecmwf.opendata", e)
PY
python3 -m pip show ecmwf-opendata mercantile pillow 2>/dev/null | grep -E 'Name:|Version:' || true
