# BMKG NWP Viewer — Endpoint Discovery Summary

## Overview Comparison Table

| Dataset | Catalog API | Data Endpoint | Format | Direct Access | Status |
|---|---|---|---|---|---|
| **Radar Balikpapan** | `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/radar.json` | `https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr/BAL/CMAX/{filename}` | PNG (Single image overlay, 4084×4084) | Yes (Requires `Referer: https://cuaca.bmkg.go.id/data/public/nwp-viewer/`) | **VERIFIED** |
| **Himawari-9 Visible** | `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json` | `https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=himawari9&modelname=himawari9hires&param=VS&baserun={baserun}` | Slippy Map Tile (TMS scheme, 256×256 PNG) | Yes (Requires `Referer: https://cuaca.bmkg.go.id/`) | **VERIFIED** |
| **Himawari-9 EH** | `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json` | `https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=himawari9&modelname=himawari9&param=EH&baserun={baserun}` | Slippy Map Tile (TMS scheme, 256×256 PNG) | Yes (Requires `Referer: https://cuaca.bmkg.go.id/`) | **VERIFIED** |

---

## Key Discovery Takeaways

1. **Radar Delivery Mechanism**:
   - Rather than tile pyramids (XYZ) or WMS, BMKG serves individual full-coverage composite radar frames (4084x4084 px PNG/WebP).
   - Frames are placed via Leaflet `L.imageOverlay` using pre-calculated bounding coordinates specified in `meta/radar.json`.
   - Station identifier for Balikpapan is `BAL` (`Stasiun Meteorologi Sepinggan Balikpapan`).
   - Timestamps and history are tracked in dynamic manifest `BAL_CMAX_latest.json`.

2. **Satellite Tile Mechanism & Coordinate Inversion**:
   - Satellite imagery is served by a dedicated backend: `https://satellite.bmkg.go.id/api22/tile/`.
   - Both Visible and EH channels use Slippy Map tiles, but follow the **TMS (Tile Map Service)** specification where the Y axis is inverted from standard Google/OSM XYZ tiles (`tms: true`).
   - Himawari-9 Visible uses model `himawari9hires` and parameter `VS`.
   - Himawari-9 EH uses model `himawari9` and parameter `EH`.

3. **Access Controls**:
   - Neither service requires authentication tokens, cookies, or API keys.
   - An anti-hotlinking check enforces `Referer: https://cuaca.bmkg.go.id/`. Requests with missing or external referers receive `403 Forbidden`.
   - When querying non-existent or unprocessed satellite baseruns, the server returns `400 Bad Request` with an explicit error message stating the baserun was not found in the model.

4. **Automation Script**:
   - The test script `bmkg-test.py` was executed directly and successfully downloaded real image samples into `C:\metamorph-nwp\samples\`.
