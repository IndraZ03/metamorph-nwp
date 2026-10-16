# BMKG NWP Viewer — Data Endpoint Documentation

Comprehensive technical documentation for data endpoints discovered from the BMKG NWP Viewer (`https://cuaca.bmkg.go.id/data/public/nwp-viewer/`).

All endpoints documented below have been captured from live browser network traffic, inspected in frontend source code (`radar-layer.js`, `tile-layer.js`, `app.js`), and verified via standalone automated Python tests.

---

## 1. Weather Radar — Balikpapan (CMAX)

### Overview
- **Dataset Name**: Weather Radar Composite Max Reflectivity (CMAX) — Balikpapan
- **Station Code**: `BAL`
- **Station Label**: Balikpapan
- **Station Official Name**: `Stasiun Meteorologi Sepinggan Balikpapan`
- **Station Location**: Latitude `-1.259733`, Longitude `116.897`
- **Product Type**: `CMAX` (Column Maximum Reflectivity)
- **Data Delivery Method**: Single static image overlay (`L.imageOverlay`) per timestamp covering the fixed station bounding box.
- **Verification Status**: **VERIFIED**

### Endpoints

#### A. Radar Catalog API
- **URL**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/radar.json`
- **HTTP Method**: `GET`
- **Purpose**: Supplies the list of supported radar stations, base data paths, static bounding boxes, geographic coordinates, refresh intervals, and reflectivity color scale metadata.
- **Response Format**: JSON
- **Headers**:
  - `User-Agent`: Any standard modern browser UA.
  - `Referer`: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/`
- **Key Fields in Response**:
  - `base`: Base path for radar assets (`https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr`).
  - `product`: Default product (`CMAX`).
  - `refresh_seconds`: `300` (5 minutes).
  - `legends`: dBZ thresholds `[5, 10, 15, ..., 70]` and corresponding hex codes.
  - `sites[]`: Station records containing `code`, `label`, `Stasiun`, `lat`, `lon`, and `bounds`.

#### B. Dynamic Manifest & Timeline API
- **URL**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr/BAL/CMAX/BAL_CMAX_latest.json`
- **Path Pattern**: `{base}/{CODE}/{PRODUCT}/{CODE}_{PRODUCT}_latest.json`
- **HTTP Method**: `GET`
- **Purpose**: Provides the current latest frame name and a chronological list of historical frames currently hosted on the server.
- **Response Format**: JSON
- **Example Response**:
  ```json
  {
    "latest": {
      "file": "BAL-20261013-2015.png",
      "timeUTC": "2026-10-13 20:15 UTC"
    },
    "history": {
      "files": [
        "BAL-20261010-2015.png",
        "...",
        "BAL-20261013-2005.png",
        "BAL-20261013-2015.png"
      ]
    }
  }
  ```

#### C. Imagery Overlay Endpoint
- **URL Pattern**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr/BAL/CMAX/{FILENAME}`
- **Example URL**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr/BAL/CMAX/BAL-20261013-2015.png`
- **HTTP Method**: `GET`
- **Content-Type**: `image/png` (Cloudflare may serve optimized WebP `image/webp` to browser clients accepting WebP).
- **Native Dimensions**: 4084 x 4084 px (RGBA image with transparent background outside echoes).
- **File Size**: Typically 9 KB to 95 KB per image depending on precipitation coverage.

### Spatial Reference & Geographic Coverage
- **Coordinate Reference System**: WGS84 (EPSG:4326)
- **Station Bounding Box** (from `meta/radar.json`):
  - Top-Left Corner (TLC / NW): `Lat 0.9878822801877207, Lon 114.64938471981229`
  - Bottom-Right Corner (BRC / SE): `Lat -3.5073482801877205, Lon 119.14461528018772`
- **Leaflet Overlay Calculation** (`radar-layer.js:74`):
  ```javascript
  bounds = [[overlayBRC[0], overlayTLC[1]], [overlayTLC[0], overlayBRC[1]]];
  // [[-3.507348, 114.649385], [0.987882, 119.144615]]
  ```

### Reflectivity Scale (Legend)
- **Unit**: dBZ
- **Levels**: `[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]`
- **Colors**:
  - `5`: `#07fef6` (Cyan)
  - `10`: `#0096ff` (Light Blue)
  - `15`: `#0002fe` (Blue)
  - `20`: `#01fe03` (Light Green)
  - `25`: `#00c703` (Green)
  - `30`: `#009902` (Dark Green)
  - `35`: `#fffe00` (Yellow)
  - `40`: `#ffc801` (Gold)
  - `45`: `#ff7707` (Orange)
  - `50`: `#fb0103` (Red)
  - `55`: `#c90002` (Deep Red)
  - `60`: `#980001` (Dark Red)
  - `65`: `#ff00ff` (Magenta)
  - `70`: `#9800fe` (Purple)

---

## 2. Himawari-9 Satellite — Visible (VS)

### Overview
- **Dataset Name**: Himawari-9 High-Resolution Visible
- **Catalog Identifier**: `himawari9-vs`
- **API Model Parameter**: `modelname=himawari9hires`
- **API Param Value**: `param=VS`
- **Data Delivery Method**: XYZ / TMS Slippy Map Tiles (256x256 PNG)
- **Tile Scheme**: **TMS (OSGeo Tile Map Service)** — Y axis is inverted relative to standard Web Mercator XYZ (`y_tms = (2^zoom - 1) - y_xyz`).
- **Coordinate Reference System**: Spherical Mercator (EPSG:3857)
- **Zoom Range**: Min Zoom `4`, Max Zoom `11`
- **Verification Status**: **VERIFIED**

### Endpoints

#### A. Satellite Catalog Configuration API
- **URL**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json`
- **HTTP Method**: `GET`
- **Purpose**: Defines source URL templates, query parameters, time stepping, history limits, and TMS flag.

#### B. Tile Imagery Endpoint
- **URL Template**: `https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=himawari9&modelname=himawari9hires&param=VS&baserun={baserun}`
- **HTTP Method**: `GET`
- **Query Parameters**:
  - `tiletype`: `himawari9`
  - `modelname`: `himawari9hires`
  - `param`: `VS`
  - `baserun`: ISO 8601 UTC timestamp URL-encoded, e.g. `2026-10-13T20%3A00%3A00Z`
- **Headers Required for Direct Access**:
  - `Referer`: `https://cuaca.bmkg.go.id/` (Required. Requests lacking this referer receive `HTTP 403 Forbidden`).
  - `User-Agent`: Any standard modern browser UA.
- **Response Format**: `image/png` (256x256 px raster tile)

### Temporal Characteristics
- **Cadence (Time Step)**: 10 minutes (`step_minutes: 10`).
- **History Coverage**: 6 hours (`history_hours: 6`).
- **Processing Lag**: 10 to 20 minutes (`lag_minutes: 10`).
- **Timestamp Formula** (from `tile-layer.js:56`):
  ```javascript
  const latestMs = Math.floor((Date.now() - lag_minutes * 60000) / (step_minutes * 60000)) * (step_minutes * 60000);
  const baserun = new Date(latestMs).toISOString().replace(/\.\d{3}Z$/, "Z");
  ```
- **Error Behavior**: If a requested `baserun` has not yet been processed by the satellite processing cluster, the endpoint returns:
  `HTTP 400 Bad Request` with body `{"error": "baserun YYYY-MM-DD HH:MM:SS +0000 UTC not found in model himawari9hires"}`.
  Clients should fall back by decrementing by 10 minutes until a 200 response is received.

---

## 3. Himawari-9 Satellite — Enhanced (EH)

### Overview
- **Dataset Name**: Himawari-9 Enhanced Infrared (IR)
- **Catalog Identifier**: `himawari9-ir`
- **API Model Parameter**: `modelname=himawari9` (Note: standard `himawari9`, not `himawari9hires`)
- **API Param Value**: `param=EH`
- **Product Meaning**: Enhanced Infrared (EH / BD enhancement equivalent palette). Cloud-top brightness temperature false-color enhancement highlighting deep convective storms and cold cloud tops.
- **Data Delivery Method**: XYZ / TMS Slippy Map Tiles (256x256 PNG)
- **Tile Scheme**: **TMS (Inverted Y axis)**
- **Coordinate Reference System**: Spherical Mercator (EPSG:3857)
- **Zoom Range**: Min Zoom `4`, Max Zoom `11`
- **Verification Status**: **VERIFIED**

### Endpoints

#### A. Satellite Catalog Configuration API
- **URL**: `https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json`
- **Source Entry**:
  ```json
  {
    "id": "himawari9-ir",
    "label": "Himawari-9 EH",
    "group": "Himawari-9",
    "url": "https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=himawari9&modelname=himawari9&param=EH&baserun={baserun}",
    "param": "EH",
    "step_minutes": 10,
    "history_hours": 6,
    "lag_minutes": 10,
    "min_zoom": 4,
    "max_zoom": 11,
    "opacity": 1,
    "attribution": "BMKG / Himawari-9",
    "tms": true
  }
  ```

#### B. Tile Imagery Endpoint
- **URL Template**: `https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=himawari9&modelname=himawari9&param=EH&baserun={baserun}`
- **HTTP Method**: `GET`
- **Query Parameters**:
  - `tiletype`: `himawari9`
  - `modelname`: `himawari9`
  - `param`: `EH`
  - `baserun`: ISO 8601 UTC timestamp URL-encoded, e.g. `2026-10-13T20%3A00%3A00Z`
- **Headers Required for Direct Access**:
  - `Referer`: `https://cuaca.bmkg.go.id/` (Required. Requests lacking this referer receive `HTTP 403 Forbidden`).
  - `User-Agent`: Any standard modern browser UA.
- **Response Format**: `image/png` (Pre-rendered color-enhanced 256x256 px tile).
- **Enhancement/Legend Notes**:
  - The tiles are rendered server-side with the EH color enhancement table already burned into the RGBA pixels.
  - The frontend displays only attribution text `"BMKG / Himawari-9"` without an interactive palette bar (`tile-layer.js:144`).

---

## 4. Security, Access Controls & Reproducibility

1. **Authentication & Session State**:
   - Neither API requires session cookies, API tokens, or OAuth authentication.
   - Publicly accessible over HTTPS.
2. **Anti-Hotlinking / Access Protection**:
   - Both `cuaca.bmkg.go.id` and `satellite.bmkg.go.id` enforce HTTP `Referer` validation.
   - A request without `Referer` or with an unapproved origin is rejected with `HTTP 403 Forbidden`.
   - Passing `Referer: https://cuaca.bmkg.go.id/` satisfies the access control check in Python, curl, and Node.js.
3. **CORS Headers**:
   - `cuaca.bmkg.go.id`: Contains `access-control-allow-origin: *`.
   - `satellite.bmkg.go.id`: Contains `access-control-allow-origin: *`.
4. **Caching**:
   - Catalog JSON: `cache-control: max-age=60`.
   - Manifest JSON: `cache-control: max-age=60`.
   - Radar and Satellite images: `cache-control: max-age=300`.
