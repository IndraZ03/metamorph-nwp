"""GFS data source: NOAA GFS 0.25 deg via AWS Open Data (S3).

Strategy (learned the hard way, Oct 2026):
- NOMADS `filter_gfs_0p25.pl` throttles aggressively: after a short burst of
  requests it starts answering 404 to everything, and its `subregion`
  parameter is rejected by the server in its current form.
- The S3 bucket `noaa-gfs-bdp-pds` serves the same GRIB2 files plus a small
  `.idx` index per file. The index lists the byte offset of every GRIB
  message, so we download ONLY the byte ranges of the 7 variables we need
  (HTTP Range requests) instead of the ~150 MB full file.
- Requests are paced (delay + retries with backoff) to stay polite.
"""
from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import config


def _request(url: str, headers: dict | None = None, timeout: int = config.HTTP_TIMEOUT_S):
    hdrs = {"User-Agent": config.USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    return urllib.request.urlopen(req, timeout=timeout)


def _fetch_with_retry(url: str, headers: dict | None = None) -> bytes:
    """GET with retries + backoff. Returns response bytes."""
    last_err: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            with _request(url, headers) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF_S * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def _head_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------- run discovery

def _cycle_candidates(now: datetime | None = None) -> list[datetime]:
    """GFS cycles newest-first: current cycle, then previous ones (max 4 back)."""
    now = now or datetime.now(timezone.utc)
    base = now.replace(minute=0, second=0, microsecond=0)
    # round down to the most recent 6h cycle
    base = base.replace(hour=(base.hour // 6) * 6)
    return [base - timedelta(hours=6 * i) for i in range(4)]


def find_latest_run(now: datetime | None = None) -> datetime:
    """Return the newest GFS run whose f000 .idx exists on S3."""
    for cand in _cycle_candidates(now):
        url = _grib_url(cand, 0) + ".idx"
        if _head_ok(url):
            return cand
    raise RuntimeError("no GFS run available on S3 (checked last 4 cycles)")


# ---------------------------------------------------------------- paths / urls

def _grib_url(run: datetime, forecast_hour: int) -> str:
    fh = f"f{forecast_hour:03d}"
    return (
        f"{config.S3_BASE}/gfs.{run:%Y%m%d}/{run:%H}/atmos/"
        f"gfs.t{run:%H}z.pgrb2.0p25.{fh}"
    )


def run_dir_name(run: datetime) -> str:
    return run.strftime("%Y%m%d%H")


def valid_time(run: datetime, forecast_hour: int) -> datetime:
    return run + timedelta(hours=forecast_hour)


def valid_dir_name(run: datetime, forecast_hour: int) -> str:
    return valid_time(run, forecast_hour).strftime("%Y%m%d%H")


# ---------------------------------------------------------------- .idx parsing

def fetch_idx(run: datetime, forecast_hour: int) -> list[dict]:
    """Download and parse the .idx index for one forecast file.

    Each line: ``num:offset:date:VAR:LEVEL:forecast_info:...``.
    Returns messages with start/end byte offsets.
    """
    raw = _fetch_with_retry(_grib_url(run, forecast_hour) + ".idx")
    lines = raw.decode("utf-8", "ignore").strip().split("\n")
    msgs: list[dict] = []
    for i, line in enumerate(lines):
        parts = line.split(":")
        if len(parts) < 6:
            continue
        start = int(parts[1])
        end = int(lines[i + 1].split(":")[1]) if i + 1 < len(lines) else None
        msgs.append({
            "var": parts[3],
            "level": parts[4],
            "info": parts[5],
            "start": start,
            "end": end,
        })
    return msgs


def pick_messages(idx_msgs: list[dict]) -> dict[str, dict]:
    """Pick one GRIB message per configured variable.

    Rules:
    - match (grib_var, grib_level) from config
    - if several match and a step_type is configured, prefer messages whose
      .idx info contains that stepType marker ('accum' -> 'acc fcst',
      'avg' -> 'ave fcst'); otherwise take the first match
      (GFS writes APCP twice with identical metadata — either copy is fine).
    """
    picked: dict[str, dict] = {}
    for key, var in config.VARIABLES.items():
        cands = [m for m in idx_msgs
                 if m["var"] == var.grib_var and m["level"] == var.grib_level]
        if not cands:
            continue
        if var.step_type == "accum":
            pref = [m for m in cands if "acc fcst" in m["info"]]
            picked[key] = pref[0] if pref else cands[0]
        elif var.step_type == "avg":
            pref = [m for m in cands if "ave fcst" in m["info"]]
            picked[key] = pref[0] if pref else cands[0]
        else:
            picked[key] = cands[0]
    return picked


# ---------------------------------------------------------------- download

def _download_range(url: str, start: int, end: int | None) -> bytes:
    headers = {"Range": f"bytes={start}-{end - 1}"} if end else {"Range": f"bytes={start}-"}
    data = _fetch_with_retry(url, headers)
    if end and len(data) != end - start:
        raise RuntimeError(f"short Range download: got {len(data)}, want {end - start}")
    return data


def download_timestep(run: datetime, forecast_hour: int, out_path: str) -> dict:
    """Download one forecast hour: only the 7 variables, concatenated as one
    GRIB2 file. Returns {variable_key: grib_metadata} for the manifest
    (incl. rain stepRange parsed from the .idx info)."""
    url = _grib_url(run, forecast_hour)
    idx = fetch_idx(run, forecast_hour)
    picked = pick_messages(idx)

    # rain: record the accumulation window (e.g. "0-1 hour acc fcst")
    meta: dict = {"forecast_hour": forecast_hour}
    if "rain" in picked:
        info = picked["rain"]["info"]
        meta["rain_step_range"] = info.split(" acc fcst")[0] if "acc fcst" in info else info

    jobs = []
    for key, msg in picked.items():
        jobs.append((key, msg))
    jobs.sort(key=lambda kv: kv[1]["start"])  # keep file order

    def _one(job):
        key, msg = job
        time.sleep(config.REQUEST_DELAY_S)
        return key, _download_range(url, msg["start"], msg["end"])

    parts: dict[str, bytes] = {}
    with ThreadPoolExecutor(max_workers=config.DOWNLOAD_WORKERS) as pool:
        for key, blob in pool.map(_one, jobs):
            parts[key] = blob

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        for key, _msg in jobs:
            fh.write(parts[key])
    meta["variables"] = sorted(parts.keys())
    meta["bytes"] = sum(len(b) for b in parts.values())
    return meta
