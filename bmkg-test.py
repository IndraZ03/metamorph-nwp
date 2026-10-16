"""BMKG NWP Viewer - Automated Endpoint Test Utility
Direct retrieval verification for:
  1. Weather Radar - Balikpapan (CMAX)
  2. Himawari-9 Satellite - Visible (VS)
  3. Himawari-9 Satellite - Enhanced (EH)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
os.makedirs(OUT_DIR, exist_ok=True)

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cuaca.bmkg.go.id/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

def fetch(url, headers=None):
    hdrs = dict(COMMON_HEADERS)
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
        return resp.status, resp.headers.get("Content-Type", ""), content

def test_radar_balikpapan():
    print("=" * 60)
    print("[TEST 1] Weather Radar — Balikpapan (CMAX)")
    print("=" * 60)

    # 1. Catalog
    cat_url = "https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/radar.json"
    status, ctype, body = fetch(cat_url)
    cat = json.loads(body.decode("utf-8"))
    site = next((s for s in cat.get("sites", []) if s.get("code") == "BAL"), None)
    if not site:
        raise RuntimeError("BAL site not found in radar.json catalog")
    print(f"Catalog URL: {cat_url} [HTTP {status}, {ctype}]")
    print(f"Station: {site.get('label')} ({site.get('code')}) - {site.get('Stasiun')}")
    print(f"Location: Lat {site.get('lat')}, Lon {site.get('lon')}")
    print(f"Bounds TLC: {site['bounds']['overlayTLC']}, BRC: {site['bounds']['overlayBRC']}")

    # 2. Manifest
    base = cat.get("base", "https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr").rstrip("/")
    prod = cat.get("product", "CMAX")
    manifest_url = f"{base}/BAL/{prod}/BAL_{prod}_latest.json"
    status, ctype, body = fetch(manifest_url)
    manifest = json.loads(body.decode("utf-8"))
    latest_file = manifest.get("latest", {}).get("file")
    latest_time = manifest.get("latest", {}).get("timeUTC")
    history_files = manifest.get("history", {}).get("files", [])
    print(f"Manifest URL: {manifest_url} [HTTP {status}, {ctype}]")
    print(f"Latest frame: {latest_file} ({latest_time})")
    print(f"History frame count: {len(history_files)}")

    # 3. Latest image
    img_url = f"{base}/BAL/{prod}/{latest_file}"
    status, ctype, img_data = fetch(img_url)
    out_path = os.path.join(OUT_DIR, latest_file)
    with open(out_path, "wb") as f:
        f.write(img_data)
    print(f"Image URL: {img_url}")
    print(f"Saved: {out_path} ({len(img_data):,} bytes, HTTP {status}, Content-Type: {ctype})")

    # 4. A previous history frame
    prev_file = history_files[-2] if len(history_files) >= 2 else None
    if prev_file:
        prev_url = f"{base}/BAL/{prod}/{prev_file}"
        status, ctype, prev_data = fetch(prev_url)
        prev_path = os.path.join(OUT_DIR, prev_file)
        with open(prev_path, "wb") as f:
            f.write(prev_data)
        print(f"Previous Image URL: {prev_url}")
        print(f"Saved: {prev_path} ({len(prev_data):,} bytes, HTTP {status})")

    return True

def compute_himawari_baserun(step_minutes=10, lag_minutes=10, history_hours=6):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    step_ms = step_minutes * 60 * 1000
    lag_ms = lag_minutes * 60 * 1000
    latest_ms = ((now_ms - lag_ms) // step_ms) * step_ms
    dt = datetime.fromtimestamp(latest_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:00Z")

def resolve_valid_tile(src_template, initial_baserun, z=7, x=105, y=63, max_back_steps=6):
    """Try initial baserun and step back by 10 minutes if server returns 400."""
    dt = datetime.strptime(initial_baserun, "%Y-%m-%dT%H:%M:00Z").replace(tzinfo=timezone.utc)
    for i in range(max_back_steps):
        target_dt = datetime.fromtimestamp(dt.timestamp() - (i * 600), tz=timezone.utc)
        target_iso = target_dt.strftime("%Y-%m-%dT%H:%M:00Z")
        url = (
            src_template
            .replace("{z}", str(z))
            .replace("{x}", str(x))
            .replace("{y}", str(y))
            .replace("{baserun}", urllib.parse.quote(target_iso))
        )
        try:
            status, ctype, data = fetch(url)
            return target_iso, url, status, ctype, data
        except urllib.error.HTTPError as e:
            if e.code == 400:
                continue
            raise
    raise RuntimeError(f"Could not find available baserun starting from {initial_baserun}")

def test_himawari9_visible():
    print("\n" + "=" * 60)
    print("[TEST 2] Himawari-9 Satellite — Visible (VS)")
    print("=" * 60)

    # 1. Catalog
    cat_url = "https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json"
    status, ctype, body = fetch(cat_url)
    cat = json.loads(body.decode("utf-8"))
    src = next((s for s in cat.get("sources", []) if s.get("id") == "himawari9-vs"), None)
    if not src:
        raise RuntimeError("himawari9-vs not found in satellite.json")
    print(f"Catalog URL: {cat_url} [HTTP {status}, {ctype}]")
    print(f"Product: {src.get('label')} (id={src.get('id')}, param={src.get('param')})")
    print(f"Tile URL Template: {src.get('url')}")
    print(f"Zoom range: {src.get('min_zoom')} - {src.get('max_zoom')}, TMS: {src.get('tms')}")

    # 2. Compute baserun & resolve latest available
    est_baserun = compute_himawari_baserun(src.get("step_minutes", 10), src.get("lag_minutes", 10))
    print(f"Estimated Latest Baserun: {est_baserun}")

    z, x, y = 7, 105, 63
    resolved_baserun, tile_url, status, ctype, tile_data = resolve_valid_tile(
        src.get("url"), est_baserun, z=z, x=x, y=y
    )
    print(f"Resolved Available Baserun: {resolved_baserun}")
    fname = f"himawari9_VS_z{z}_x{x}_y{y}_{resolved_baserun.replace(':', '').replace('-', '')}.png"
    out_path = os.path.join(OUT_DIR, fname)
    with open(out_path, "wb") as f:
        f.write(tile_data)
    print(f"Tile URL: {tile_url}")
    print(f"Saved: {out_path} ({len(tile_data):,} bytes, HTTP {status}, Content-Type: {ctype})")

    # 3. Previous timestamp (-10 minutes)
    dt_latest = datetime.strptime(resolved_baserun, "%Y-%m-%dT%H:%M:00Z").replace(tzinfo=timezone.utc)
    dt_prev = datetime.fromtimestamp(dt_latest.timestamp() - 600, tz=timezone.utc)
    prev_baserun = dt_prev.strftime("%Y-%m-%dT%H:%M:00Z")
    prev_tile_url = (
        src.get("url")
        .replace("{z}", str(z))
        .replace("{x}", str(x))
        .replace("{y}", str(y))
        .replace("{baserun}", urllib.parse.quote(prev_baserun))
    )
    status, ctype, prev_tile = fetch(prev_tile_url)
    prev_fname = f"himawari9_VS_z{z}_x{x}_y{y}_{prev_baserun.replace(':', '').replace('-', '')}.png"
    prev_path = os.path.join(OUT_DIR, prev_fname)
    with open(prev_path, "wb") as f:
        f.write(prev_tile)
    print(f"Previous Tile URL (-10m): {prev_tile_url}")
    print(f"Saved: {prev_path} ({len(prev_tile):,} bytes, HTTP {status})")

    return True

def test_himawari9_eh():
    print("\n" + "=" * 60)
    print("[TEST 3] Himawari-9 Satellite — Enhanced (EH)")
    print("=" * 60)

    # 1. Catalog
    cat_url = "https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json"
    status, ctype, body = fetch(cat_url)
    cat = json.loads(body.decode("utf-8"))
    src = next((s for s in cat.get("sources", []) if s.get("id") == "himawari9-ir"), None)
    if not src:
        raise RuntimeError("himawari9-ir (EH) not found in satellite.json")
    print(f"Catalog URL: {cat_url} [HTTP {status}, {ctype}]")
    print(f"Product: {src.get('label')} (id={src.get('id')}, param={src.get('param')})")
    print(f"Tile URL Template: {src.get('url')}")
    print(f"Zoom range: {src.get('min_zoom')} - {src.get('max_zoom')}, TMS: {src.get('tms')}")

    # 2. Compute baserun & resolve latest available
    est_baserun = compute_himawari_baserun(src.get("step_minutes", 10), src.get("lag_minutes", 10))
    print(f"Estimated Latest Baserun: {est_baserun}")

    z, x, y = 7, 105, 63
    resolved_baserun, tile_url, status, ctype, tile_data = resolve_valid_tile(
        src.get("url"), est_baserun, z=z, x=x, y=y
    )
    print(f"Resolved Available Baserun: {resolved_baserun}")
    fname = f"himawari9_EH_z{z}_x{x}_y{y}_{resolved_baserun.replace(':', '').replace('-', '')}.png"
    out_path = os.path.join(OUT_DIR, fname)
    with open(out_path, "wb") as f:
        f.write(tile_data)
    print(f"Tile URL: {tile_url}")
    print(f"Saved: {out_path} ({len(tile_data):,} bytes, HTTP {status}, Content-Type: {ctype})")

    # 3. Previous timestamp (-10 minutes)
    dt_latest = datetime.strptime(resolved_baserun, "%Y-%m-%dT%H:%M:00Z").replace(tzinfo=timezone.utc)
    dt_prev = datetime.fromtimestamp(dt_latest.timestamp() - 600, tz=timezone.utc)
    prev_baserun = dt_prev.strftime("%Y-%m-%dT%H:%M:00Z")
    prev_tile_url = (
        src.get("url")
        .replace("{z}", str(z))
        .replace("{x}", str(x))
        .replace("{y}", str(y))
        .replace("{baserun}", urllib.parse.quote(prev_baserun))
    )
    status, ctype, prev_tile = fetch(prev_tile_url)
    prev_fname = f"himawari9_EH_z{z}_x{x}_y{y}_{prev_baserun.replace(':', '').replace('-', '')}.png"
    prev_path = os.path.join(OUT_DIR, prev_fname)
    with open(prev_path, "wb") as f:
        f.write(prev_tile)
    print(f"Previous Tile URL (-10m): {prev_tile_url}")
    print(f"Saved: {prev_path} ({len(prev_tile):,} bytes, HTTP {status})")

    return True

def main():
    print("Testing BMKG NWP Viewer Target Datasets...")
    ok1 = test_radar_balikpapan()
    ok2 = test_himawari9_visible()
    ok3 = test_himawari9_eh()
    print("\n" + "=" * 60)
    print(f"ALL TESTS PASSED: Radar BAL={ok1}, Himawari-9 VS={ok2}, Himawari-9 EH={ok3}")
    print(f"Downloaded samples saved in: {OUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
