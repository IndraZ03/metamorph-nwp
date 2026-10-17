#!/bin/bash
python3 - <<'PY'
import sys
print("python", sys.version)
for m in ["numpy", "PIL", "eccodes", "scipy"]:
    try:
        __import__(m)
        print("ok", m)
    except Exception as e:
        print("missing", m, type(e).__name__, e)
PY
python3 -m pip show numpy pillow eccodes scipy 2>/dev/null | grep -E 'Name:|Version:' || true
