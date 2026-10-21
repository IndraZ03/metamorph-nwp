import json
import shutil
from engine.retention import atomic_write_json, cleanup, prune_manifest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import (
    BBOX_LAT_MIN,
    BBOX_LAT_MAX,
    BBOX_LON_MIN,
    BBOX_LON_MAX,
    PARAMETERS,
    RETENTION_RUNS,
    TILES_DIR,
    ZOOM_MIN,
    ZOOM_MAX,
)


def get_manifest_path(run_id: str) -> Path:
    return TILES_DIR / run_id / "manifest.json"


def get_global_manifest_path() -> Path:
    return TILES_DIR / "latest_manifest.json"


class ManifestManager:
    """Tracks runs, steps, and generates manifest metadata."""

    def __init__(self, run_meta: Dict):
        self.run_id = run_meta["run_id"]
        self.run_time = run_meta["run_time_iso"]
        self.run_dir = TILES_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = get_manifest_path(self.run_id)
        self.data = self._load_or_init()

    def _load_or_init(self) -> Dict:
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault(
                    "numeric_tile_url_template",
                    "/api/icon/tiles-numeric/{run}/{param}/{step}/{z}/{x}/{y}.webp",
                )
                data.setdefault(
                    "point_query_url_template",
                    "/api/icon/point?lat={lat}&lon={lon}&step={step}&run={run}&param={param}",
                )
                data.setdefault(
                    "numeric_encoding",
                    {
                        "type": "rgb_int24",
                        "offset": 1000.0,
                        "scale": 10.0,
                        "precision": 0.1,
                        "decode_formula": "((R * 65536 + G * 256 + B) / 10.0) - 1000.0",
                        "nodata_alpha": 0,
                    },
                )
                return data
            except Exception:
                pass

        params_list = [
            {
                "id": k,
                "name": v["name"],
                "unit": v["unit"],
                "range": v["range"],
                "is_accum": v["is_accum"],
            }
            for k, v in PARAMETERS.items()
        ]

        return {
            "model": "ICON-Global",
            "source": "DWD Open Data",
            "domain": {
                "name": "Indonesia",
                "bounds": [[BBOX_LAT_MIN, BBOX_LON_MIN], [BBOX_LAT_MAX, BBOX_LON_MAX]],
                "zoom_min": ZOOM_MIN,
                "zoom_max": ZOOM_MAX,
            },
            "run_id": self.run_id,
            "run_time": self.run_time,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z"),
            "tile_url_template": "/api/icon/tiles/{run}/{param}/{step}/{z}/{x}/{y}.webp",
            "numeric_tile_url_template": "/api/icon/tiles-numeric/{run}/{param}/{step}/{z}/{x}/{y}.webp",
            "point_query_url_template": "/api/icon/point?lat={lat}&lon={lon}&step={step}&run={run}&param={param}",
            "numeric_encoding": {
                "type": "rgb_int24",
                "offset": 1000.0,
                "scale": 10.0,
                "precision": 0.1,
                "decode_formula": "((R * 65536 + G * 256 + B) / 10.0) - 1000.0",
                "nodata_alpha": 0,
            },
            "parameters": params_list,
            "timesteps": [],
        }

    def record_step_ready(self, step_int: int, step_str: str, valid_time: str, param_key: str):
        """Mark a parameter for a timestep as rendered and ready."""
        steps = self.data["timesteps"]
        step_entry = next((s for s in steps if s["step"] == step_int), None)
        if not step_entry:
            step_entry = {
                "step": step_int,
                "step_str": step_str,
                "valid_time": valid_time,
                "params": [],
            }
            steps.append(step_entry)
            steps.sort(key=lambda s: s["step"])

        if param_key not in step_entry["params"]:
            step_entry["params"].append(param_key)
            step_entry["params"].sort()

        self.data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")
        self.save()

    def save(self):
        prune_manifest(self.data)
        atomic_write_json(self.manifest_path, self.data)
        latest = get_global_manifest_path()
        try:
            current = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = {}
        if current.get("run_id", "") <= self.run_id:
            atomic_write_json(latest, self.data)


def list_saved_runs() -> List[str]:
    """List all available run IDs on disk sorted descending."""
    if not TILES_DIR.exists():
        return []
    runs = []
    for p in TILES_DIR.iterdir():
        if p.is_dir() and p.name.isdigit() and len(p.name) == 10:
            if (p / "manifest.json").exists():
                runs.append(p.name)
    runs.sort(reverse=True)
    return runs


def prune_old_runs(keep: int = RETENTION_RUNS):
    """Prune runs older than the newest `keep` runs to bound disk usage."""
    return cleanup("icon", locked=True)
