#!/bin/bash
python3 - <<'PY'
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

root = "https://data.ecmwf.int/forecasts"
now = datetime.now(timezone.utc)
print("now", now.isoformat())
for hback in range(0, 48, 6):
    t = now.replace(minute=0, second=0, microsecond=0)
    t = t.replace(hour=(t.hour // 6) * 6) - timedelta(hours=hback)
    if t.hour not in (0, 6, 12, 18):
        continue
    ymd = t.strftime("%Y%m%d")
    hh = t.strftime("%H")
    stamp = t.strftime("%Y%m%d%H0000")
    url = f"{root}/{ymd}/{hh}z/ifs/0p25/oper/{stamp}-0h-oper-fc.index"
    req = Request(url, method="HEAD", headers={"User-Agent": "metamorph-nwp"})
    try:
        with urlopen(req, timeout=15) as r:
            print(t.isoformat(), r.status, url)
    except HTTPError as e:
        print(t.isoformat(), e.code, url)
    except Exception as e:
        print(t.isoformat(), type(e).__name__, e)
PY
