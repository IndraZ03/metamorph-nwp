"""Read-only health checks. Freshness compares published runs, never wall-clock age."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
MODELS = ("ecmwf", "gfs", "icon")


def timestamp(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    for fmt in ("%Y%m%dT%H", "%Y%m%d%H", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return timestamp(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def _http(url, timeout, listing=False):
    # Import lazily: no provider libraries, configuration side effects or insecure TLS.
    import ssl
    from urllib.request import Request, urlopen
    try:
        from .network import ssl_context
    except ImportError:
        ssl_context = ssl.create_default_context
    with urlopen(Request(url, method="GET" if listing else "HEAD",
                         headers={"User-Agent": "metamorph-health/1"}),
                 timeout=timeout, context=ssl_context()) as response:
        if listing:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("provider listing exceeds size limit")
            return body.decode("utf-8")
        return ""


def probe_provider(model, now=None, budget=40, request_timeout=4):
    """At most nine cycle probes (four listings for ICON), within time budget.

    Only 404 means unpublished. Network/TLS/permission errors make result unknown:
    a failed newer probe must never turn an older successful probe into fresh.
    """
    from urllib.error import HTTPError
    now = timestamp(now or datetime.now(UTC))
    deadline = time.monotonic() + budget

    def get(url, listing=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("provider probe budget exhausted")
        return _http(url, min(request_timeout, remaining), listing)

    try:
        if model == "icon":
            runs = []
            for cycle in ("00", "06", "12", "18"):
                text = get(f"https://opendata.dwd.de/weather/nwp/icon/grib/{cycle}/t_2m/", True)
                runs.extend(timestamp(s) for s in re.findall(
                    r"icon_global_icosahedral_single-level_(\d{10})_\d{3}_T_2M\.grib2\.bz2", text))
            runs = [r for r in runs if r is not None]
            if not runs:
                raise ValueError("no published ICON runs in listings")
            latest = max(runs)
        else:
            cycle = now.replace(hour=now.hour // 6 * 6, minute=0, second=0, microsecond=0)
            latest = None
            for offset in range(9):
                run = cycle - timedelta(hours=6 * offset)
                if model == "ecmwf":
                    url = (f"https://data.ecmwf.int/forecasts/{run:%Y%m%d}/{run:%H}z/ifs/0p25/oper/"
                           f"{run:%Y%m%d%H}0000-0h-oper-fc.index")
                elif model == "gfs":
                    url = (f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{run:%Y%m%d}/"
                           f"{run:%H}/atmos/gfs.t{run:%H}z.pgrb2.0p25.f000.idx")
                else:
                    raise ValueError(f"unsupported model: {model}")
                try:
                    get(url)
                    latest = run
                    break
                except HTTPError as exc:
                    if exc.code != 404:
                        raise
            if latest is None:
                raise ValueError("no published runs in bounded search")
        return {"status": "ok", "run": latest.isoformat(), "error": None}
    except Exception as exc:
        return {"status": "unknown", "run": None, "error": str(exc)}


def normalize_manifest(model, manifest):
    """Common run/variables/steps shape for ECMWF, GFS and ICON."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    run = timestamp(manifest.get("run_time") or manifest.get("run") or manifest.get("run_id"))
    if run is None:
        raise ValueError("manifest has no valid run timestamp")
    catalog = manifest.get("variables", manifest.get("parameters", []))
    variables = list(catalog) if isinstance(catalog, dict) else [v["id"] for v in catalog]
    rows = []
    for row in manifest.get("steps", manifest.get("timesteps", [])):
        step = int(row.get("step", row.get("forecast_hour", -1)))
        if step < 0:
            raise ValueError("invalid forecast step")
        available = row.get("vars", row.get("params", row.get("tiles", {})))
        if isinstance(available, dict):
            available = [key for key, count in available.items() if isinstance(count, (int, float)) and count > 0]
        rows.append({"step": step, "valid": run + timedelta(hours=step),
                     "variables": list(available),
                     "ready": row.get("ready", True) and "error" not in row,
                     "directory": str(row.get("step_str", step))})
    return {"run": run, "run_id": manifest.get("run_id") or run.strftime("%Y%m%d%H" if model == "gfs" else "%Y%m%dT%H"),
            "variables": variables, "steps": rows}


def _has_tile(path):
    # Fixed-depth sampling, capped work; not a full tile-integrity audit.
    examined = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
        if len(Path(directory).relative_to(path).parts) >= 3:
            dirs[:] = []
        examined += len(dirs) + len(files)
        if any(f.endswith(".webp") and (Path(directory) / f).is_file()
               and (Path(directory) / f).stat().st_size > 0 for f in files):
            return True
        if examined > 2000:
            return False
    return False


def check_model(model, manifest_path, tile_root, numeric_root=None, upstream=None):
    result = {"model": model, "status": "unknown", "local_run": None,
              "upstream_run": None, "freshness": "unknown", "complete": False,
              "issues": []}
    upstream = upstream if upstream is not None else probe_provider(model)
    result["upstream_run"] = upstream.get("run")
    try:
        path = Path(manifest_path)
        if path.stat().st_size > 4_000_000:
            raise ValueError("manifest exceeds size limit")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if model == "gfs" and isinstance(raw, dict) and "variables" not in raw:
            run = timestamp(raw.get("run"))
            if run is None:
                raise ValueError("GFS latest pointer has no valid run")
            canonical = Path(tile_root) / run.strftime("%Y%m%d%H") / "manifest.json"
            if canonical.stat().st_size > 4_000_000:
                raise ValueError("manifest exceeds size limit")
            raw = json.loads(canonical.read_text(encoding="utf-8"))
            if timestamp(raw.get("run")) != run:
                raise ValueError("GFS latest pointer and run manifest disagree")
        local = normalize_manifest(model, raw)
        result["local_run"] = local["run"].isoformat()
        published = timestamp(upstream.get("run"))
        if upstream.get("status") == "ok" and published is not None:
            result["freshness"] = "stale" if local["run"] < published else "fresh"
        else:
            result["issues"].append("provider unknown: " + str(upstream.get("error")))
        if not local["steps"]:
            result["issues"].append("empty manifest: no steps")
        if not local["variables"]:
            result["issues"].append("empty variable catalog")
        for row in local["steps"]:
            expected = local["variables"] or row["variables"]
            missing = sorted(set(expected) - set(row["variables"]))
            if not row["ready"] or missing:
                result["issues"].append(f"step {row['step']} incomplete; missing variables: {missing}")
            for variable in row["variables"]:
                # Reject path components from untrusted manifests.
                components = [str(local["run_id"]), str(variable), row["directory"]]
                if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", c) or c in (".", "..") for c in components):
                    raise ValueError("unsafe artifact path component")
                if model == "gfs":
                    relative = Path(local["run_id"]) / row["valid"].strftime("%Y%m%d%H") / variable
                else:
                    relative = Path(*components)
                for root in [tile_root] + ([numeric_root] if numeric_root is not None else []):
                    if not _has_tile(Path(root) / relative):
                        result["issues"].append(f"missing artifact: {Path(root) / relative}")
        local_issues = [s for s in result["issues"] if not s.startswith("provider unknown:")]
        result["complete"] = not local_issues
        result["status"] = ("unknown" if result["freshness"] == "unknown" else
                            "stale" if result["freshness"] == "stale" else
                            "incomplete" if local_issues else "healthy")
    except Exception as exc:
        result["issues"].append(str(exc))
    result["fresh"] = (None if result["freshness"] == "unknown" else result["freshness"] == "fresh")
    return result


def check_all(root=None, timeout=15):
    """Return model-keyed results; concurrent probes each bounded by timeout seconds."""
    from concurrent.futures import ThreadPoolExecutor
    layouts = default_layouts(root)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {model: pool.submit(probe_provider, model, budget=timeout,
                                     request_timeout=min(4, timeout)) for model in MODELS}
        return {model: check_model(model, *layouts[model], upstream=futures[model].result())
                for model in MODELS}


def default_layouts(root=None):
    # Do not import backend.engine.config: importing it creates directories.
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    gfs = Path(os.environ.get("GFS_DATA_DIR", root / "data" / "gfs"))
    return {
        "ecmwf": (root / "engine/output/latest.json", root / "engine/output/runs", root / "engine/output/numeric"),
        "gfs": (gfs / "latest.json", gfs / "tiles/gfs", gfs / "tiles_numeric/gfs"),
        "icon": (root / "data/tiles/icon/latest_manifest.json", root / "data/tiles/icon", root / "data/tiles_numeric/icon"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="read-only check (default)")
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    parser.add_argument("--model", choices=MODELS)
    args = parser.parse_args(argv)
    if args.model:
        results = [check_model(args.model, *default_layouts()[args.model],
                               upstream=probe_provider(args.model, budget=15))]
    else:
        results = list(check_all().values())
    payload = {"checked_at": datetime.now(UTC).isoformat(), "models": results,
               "healthy": all(r["status"] == "healthy" for r in results)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for result in results:
            print(f"{result['model']}: {result['status']} " + "; ".join(result["issues"]))
    return 0 if payload["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
