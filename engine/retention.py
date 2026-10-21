"""Shared valid-time retention. Unknown paths are never removed."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)
UTC = timezone.utc


def timestamp(value):
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    for fmt in ("%Y%m%dT%H", "%Y%m%d%H", "%Y%m%dT%H%M", "%Y%m%d%H%M"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else result.replace(tzinfo=UTC)
    except ValueError:
        return None


def expired(valid_time, now=None):
    valid = timestamp(valid_time)
    return valid is not None and valid < (now or datetime.now(UTC)) - timedelta(hours=15)


def keep_step(run, step, now=None):
    start = timestamp(run)
    return start is None or not expired(start + timedelta(hours=int(step)), now)


def prune_manifest(manifest, now=None):
    for key in ("steps", "timesteps"):
        if key in manifest:
            manifest[key] = [row for row in manifest[key]
                             if not expired(row.get("valid_time", row.get("valid")), now)]
    return manifest


def atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".manifest-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def model_lock(path):
    """Nonblocking OS lock; process death releases ownership, file may remain."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"already running: {path}") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def layouts(model):
    if model == "ecmwf":
        from . import config as c
        return [Path(c.RUNS_DIR), Path(c.OUTPUT_DIR) / "numeric", Path(c.CACHE_DIR)], [Path(c.LATEST_PATH)], Path(c.OUTPUT_DIR) / ".retention.lock"
    if model == "gfs":
        from .gfs import config as c
        return [Path(c.TILE_DIR) / "gfs", Path(c.NUMERIC_TILE_DIR) / "gfs", Path(c.TMP_DIR)], [Path(c.LATEST_FILE)], Path(c.LOCK_FILE)
    from backend.engine import config as c
    return [Path(c.TILES_DIR), Path(c.NUMERIC_TILES_DIR), Path(c.GRIDS_DIR), Path(c.CACHE_DIR)], [Path(c.TILES_DIR) / "latest_manifest.json"], Path(c.DATA_DIR) / ".icon.lock"


def unsafe_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _ready_rows(manifest):
    return [row for row in (manifest or {}).get("timesteps", [])
            if isinstance(row, dict) and "error" not in row and row.get("valid")]


def _retarget_gfs_latest(roots, latest, now, dry_run):
    """Point latest.json at the newest run that still has usable timesteps."""
    if not latest:
        return None
    pointer = latest[0]
    current = None
    if pointer.exists() and not pointer.is_symlink():
        try:
            current = json.loads(pointer.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            current = None
    if _ready_rows(current):
        return None
    chosen = None
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for run_dir in sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink()), reverse=True):
            if timestamp(run_dir.name) is None:
                continue
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if not _ready_rows(manifest):
                continue
            chosen = (run_dir.name, manifest)
            break
        if chosen:
            break
    if chosen is None:
        log.info("gfs latest empty and no run has timesteps")
        return None
    run_name, manifest = chosen
    run = timestamp(run_name)
    payload = {
        "model": "GFS",
        "run": run.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest": f"/api/gfs/runs/{run_name}/manifest.json",
        "timesteps": manifest.get("timesteps", []),
    }
    if not dry_run:
        atomic_write_json(pointer, payload)
    return run_name


def cleanup(model, now=None, dry_run=False, locked=False):
    roots, latest, lock = layouts(model)
    if not locked:
        with model_lock(lock):
            return cleanup(model, now, dry_run, locked=True)
    now = now or datetime.now(UTC)
    removed, unknown = [], []
    # Publish every pruned manifest, including latest copies, before deleting data.
    manifests = list(latest)
    for root in roots:
        if root.is_dir() and not root.is_symlink():
            manifests.extend(p / "manifest.json" for p in root.iterdir()
                             if p.is_dir() and not p.is_symlink())
    for path in manifests:
        if not path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
            continue
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
            updated = prune_manifest(json.loads(json.dumps(original)), now)
            if updated != original and not dry_run:
                atomic_write_json(path, updated)
        except (OSError, ValueError, TypeError):
            # Do not delete artifacts when their manifest cannot be updated safely.
            log.exception("invalid manifest; abort cleanup: %s", path)
            return {"removed": [], "unknown": [str(path)], "error": "invalid manifest"}
    for root in roots:
        if not root.exists() or root.is_symlink() or any(p.is_symlink() for p in root.parents):
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            parent = Path(directory)
            dirs[:] = [name for name in dirs if not unsafe_link(parent / name)]
            for name in list(dirs) + files:
                path = parent / name
                if unsafe_link(path) or not path.resolve().is_relative_to(root.resolve()) or name in ("manifest.json", "latest_manifest.json"):
                    continue
                relative = path.relative_to(root).parts
                run = timestamp(relative[0])
                valid = None
                if run is not None:
                    # GFS run/valid/variable; ECMWF and ICON run/variable/step.
                    if model == "gfs" and len(relative) == 2:
                        valid = timestamp(name)
                    elif model != "gfs" and ((len(relative) == 3) or (len(relative) == 2 and root == roots[-1])):
                        step = Path(name).stem
                        if step.isdigit():
                            valid = run + timedelta(hours=int(step))
                if model == "gfs" and len(relative) == 1:
                    match = re.fullmatch(r"gfs_(\d{8}T\d{2}|\d{10})_f(\d+)\.grb2", name)
                    if match:
                        valid = timestamp(match[1]) + timedelta(hours=int(match[2]))
                if valid is not None and not expired(valid, now) and name in dirs:
                    dirs.remove(name)  # Tile descendants share this valid time.
                if valid is not None and expired(valid, now):
                    removed.append(str(path))
                    if name in dirs:
                        dirs.remove(name)
                    if not dry_run:
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                elif len(relative) == 1 and run is None:
                    unknown.append(str(path))
    retargeted = _retarget_gfs_latest(roots, latest, now, dry_run) if model == "gfs" else None
    log.info("retention %s dry_run=%s removed=%d unknown=%d retargeted=%s",
             model, dry_run, len(removed), len(unknown), retargeted)
    return {"removed": removed, "unknown": unknown, "retargeted": retargeted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", choices=("ecmwf", "gfs", "icon"))
    args = parser.parse_args()
    for model in ([args.model] if args.model else ("ecmwf", "gfs", "icon")):
        print(json.dumps({model: cleanup(model, dry_run=args.dry_run)}, indent=2))


if __name__ == "__main__":
    main()
