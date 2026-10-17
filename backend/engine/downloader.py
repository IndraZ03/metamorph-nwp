import bz2
import re
import urllib.request
import eccodes
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .config import DWD_BASE_URL, PARAMETERS


def list_available_runs() -> List[str]:
    """Check runs currently available on DWD: e.g. ['00', '06', '12', '18']"""
    url = f"{DWD_BASE_URL}/"
    req = urllib.request.Request(url, headers={"User-Agent": "metamorph-nwp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        dirs = re.findall(r'href=["\']([0-9]{2})/["\']', html)
        return sorted(list(set(dirs)))
    except Exception as e:
        print(f"Error listing runs: {e}")
        return ["00", "06", "12", "18"]


def get_latest_run_metadata(cycle: str = "00") -> Optional[Dict]:
    """
    Inspect t_2m in a specific cycle to get latest date and available timesteps.
    Returns:
      {
        "cycle": "00",
        "date_str": "20261017",
        "run_id": "2026101700",
        "run_time_iso": "2026-10-17T00:00:00Z",
        "files": {...},
        "timesteps": [0, 1, 2, ...],
      }
    """
    url = f"{DWD_BASE_URL}/{cycle}/t_2m/"
    req = urllib.request.Request(url, headers={"User-Agent": "metamorph-nwp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")

        pattern = r'href=["\'](icon_global_icosahedral_single-level_([0-9]{8})' + cycle + r'_([0-9]{3})_T_2M\.grib2\.bz2)["\']'
        matches = re.findall(pattern, html)
        if not matches:
            return None

        # Group by date
        dates = sorted(list(set(m[1] for m in matches)), reverse=True)
        latest_date = dates[0]

        # Files for this latest date
        date_matches = [m for m in matches if m[1] == latest_date]
        timesteps = sorted([int(m[2]) for m in date_matches])

        run_dt = datetime.strptime(f"{latest_date}{cycle}", "%Y%m%d%H").replace(tzinfo=timezone.utc)
        run_time_iso = run_dt.strftime("%Y-%m-%dT%H:%M:00Z")

        return {
            "cycle": cycle,
            "date_str": latest_date,
            "run_id": f"{latest_date}{cycle}",
            "run_time_iso": run_time_iso,
            "run_dt": run_dt,
            "timesteps": timesteps,
            "count": len(timesteps),
        }
    except Exception as e:
        print(f"Error inspecting run metadata for {cycle}: {e}")
        return None


def find_latest_active_run() -> Optional[Dict]:
    """Find the newest available run across all cycles (18 -> 12 -> 06 -> 00)."""
    cycles = ["18", "12", "06", "00"]
    runs = []
    for c in cycles:
        meta = get_latest_run_metadata(c)
        if meta and meta["count"] > 0:
            runs.append(meta)

    if not runs:
        return None

    # Sort by run_id descending (e.g. 2026101706 > 2026101700)
    runs.sort(key=lambda r: r["run_id"], reverse=True)
    return runs[0]


def download_step_grib(run_meta: Dict, param_key: str, step_int: int) -> Optional[Tuple[bytes, Dict]]:
    """
    Download a single grib2.bz2 directly into memory and decompress it.
    Returns: (raw_grib2_bytes, step_info_dict)
    """
    param_cfg = PARAMETERS[param_key]
    folder = param_cfg["dwd_folder"]
    var_name = param_cfg["dwd_var"]

    cycle = run_meta["cycle"]
    date_str = run_meta["date_str"]
    step_str = f"{step_int:03d}"

    filename = f"icon_global_icosahedral_single-level_{date_str}{cycle}_{step_str}_{var_name}.grib2.bz2"
    url = f"{DWD_BASE_URL}/{cycle}/{folder}/{filename}"

    req = urllib.request.Request(url, headers={"User-Agent": "metamorph-nwp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            compressed = resp.read()

        raw = bz2.decompress(compressed)

        # Calculate valid_time
        from datetime import timedelta
        valid_dt = run_meta["run_dt"] + timedelta(hours=step_int)
        valid_time_iso = valid_dt.strftime("%Y-%m-%dT%H:%M:00Z")

        step_info = {
            "step": step_int,
            "step_str": step_str,
            "param": param_key,
            "run_id": run_meta["run_id"],
            "run_time": run_meta["run_time_iso"],
            "valid_time": valid_time_iso,
        }
        return raw, step_info
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None
