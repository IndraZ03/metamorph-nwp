# BMKG NWP VIEWER — RADAR & HIMAWARI-9 ENDPOINT DISCOVERY

## ROLE

You are a Senior Reverse Engineering Engineer, Browser Network Analyst, and Geospatial Data Engineer.

You have access to Chrome DevTools MCP, which allows you to navigate websites, inspect browser network traffic, execute JavaScript, inspect frontend source code, and analyze HTTP requests.

Your mission is to discover, capture, verify, and document the actual data endpoints used by the BMKG NWP Viewer.

**Target website:**
https://cuaca.bmkg.go.id/data/public/nwp-viewer/

## PRIMARY OBJECTIVES

Discover the actual network endpoints for exactly these three datasets:

1. **Weather Radar — Balikpapan**
   - Find Balikpapan in the available radar station list.
   - Identify its radar station identifier.
   - Capture the latest radar imagery and its metadata.
   - Determine how radar frames and timestamps are retrieved.
   - Determine the supported geographic coverage.

2. **Himawari-9 Satellite — Visible**
   - Identify the exact satellite product corresponding to Himawari-9 Visible.
   - Capture its imagery endpoint.
   - Determine the available timestamps, coverage, resolution, and imagery format.
   - Determine how the browser loads and renders the imagery.

3. **Himawari-9 Satellite — EH**
   - Identify the product labeled EH, Enhanced, or Enhanced Infrared, if present.
   - Verify its actual product name and identifier rather than assuming equivalence.
   - Capture its imagery endpoint.
   - Determine the available timestamps, geographic coverage, and image format.
   - Identify any legend or enhancement metadata required to render it correctly.

Do not implement a new application yet. Focus exclusively on endpoint discovery, verification, and documentation.

---

## PHASE 1 — BROWSER INITIALIZATION

1. Use Chrome DevTools MCP to open the target URL.
2. Wait until the main page, map, and application JavaScript have initialized.
3. Inspect the page structure and available controls.
4. Identify the Radar and Satellite menus.
5. Inspect the available Chrome DevTools MCP commands and choose the appropriate browser navigation, network inspection, and JavaScript evaluation tools.

Before proceeding:

- Enable network request monitoring.
- Inspect Fetch/XHR traffic.
- Include image requests.
- Include JavaScript requests.
- Include tile requests.
- Include binary requests.
- Include failed requests.
- Preserve network logs if supported.

Record the initial network activity and distinguish basemap traffic from meteorological data traffic.

## PHASE 2 — RADAR BALIKPAPAN

Perform the following browser interactions:

1. Click the Radar menu.
2. Wait for the radar station catalog to load.
3. Inspect the complete available station list.
4. Search for Balikpapan and any corresponding station identifier.
5. Select Balikpapan.
6. Click Add.
7. Wait for its radar data to render.

While performing these interactions, capture every relevant network request.

Investigate:

- Radar catalog endpoint
- Radar station metadata endpoint
- Radar availability endpoint
- Latest radar timestamp endpoint
- Radar imagery endpoint
- Radar image tiles, if applicable
- Radar animation/frame sequence endpoint
- Geographic bounds and projection metadata
- Legend or reflectivity scale metadata, if available

For each relevant request, extract:

- Full URL
- HTTP method
- Query parameters
- Request headers relevant to reproducibility
- Request body, if applicable
- Response status
- Content-Type
- Response structure
- Timestamp parameters
- Station identifier
- Bounding box parameters
- Zoom, x, y, z tile parameters, if applicable

Determine whether the radar is delivered as:

- PNG/JPEG/WebP
- XYZ/TMS raster tiles
- WMS/WMTS
- JSON metadata containing imagery URLs
- GeoTIFF or other raster formats
- Binary data
- Other formats

Inspect how the frontend converts the response into a visible map layer.

## PHASE 3 — HIMAWARI-9 VISIBLE

1. Open the Satellite menu.
2. Wait for the satellite product catalog.
3. Inspect the available satellite products.
4. Find the product corresponding to Himawari-9 Visible.
5. Capture its exact product ID and display name.
6. Select the product.
7. Click Add.
8. Wait for imagery to render.

Capture every network request triggered by selecting and displaying the layer.

Identify:

- Satellite product catalog endpoint
- Visible product identifier
- Latest imagery endpoint
- Available time list endpoint
- Image or tile endpoint
- Geographic extent
- Projection
- Temporal resolution
- Image dimensions and native format

Inspect how the timebar requests previous and next imagery frames.

Capture at least one successful imagery request and, where available, a second request for a different timestamp.

## PHASE 4 — HIMAWARI-9 EH

Repeat the full investigation for the satellite product labeled EH.

Important:

- Do not automatically assume EH means Enhanced Infrared.
- Inspect the actual catalog metadata.
- Identify the exact product definition and identifier.
- Confirm whether it is derived from Himawari-9 or another source.
- Record any enhancement palette or legend information.

Capture the latest imagery request and another available timestamp.

Determine whether Visible and EH use the same API architecture with different product IDs.

## PHASE 5 — DEEP NETWORK ANALYSIS

For every discovered dataset:

1. Separate catalog requests from imagery requests.
2. Trace requests that return URLs or metadata used by subsequent requests.
3. Inspect redirects where relevant.
4. Identify dynamic parameters.
5. Determine the timestamp naming convention.
6. Determine whether the endpoint is publicly accessible.
7. Inspect whether authentication, cookies, or signed URLs are required.
8. Check relevant caching headers and response expiration.
9. Determine whether requests use direct image URLs, tile services, or Blob URLs.

If a displayed image uses `blob:`:

- Trace the original network request.
- Determine the original response type.
- Identify the JavaScript transformation that creates the Blob.
- Extract the reproducible upstream endpoint.

If data is loaded through Web Workers, service workers, or dynamic JavaScript modules, inspect the relevant source and trace the underlying request.

Do not report a Blob URL or canvas data URL as the original endpoint.

## PHASE 6 — FRONTEND SOURCE INVESTIGATION

Inspect loaded JavaScript resources for relevant implementation details.

Search for:

- radar
- satellite
- himawari
- visible
- enhanced
- product
- catalog
- tile
- frames
- timestamp
- raster
- image
- bounds
- layer

Identify:

- API base URL
- Endpoint path construction
- Product identifiers
- Station identifiers
- Timestamp formatting
- Tile URL construction
- Data transformation logic
- Layer rendering implementation
- Refresh intervals

Use browser-observed traffic to validate anything inferred from source code.

Do not invent endpoints based only on variable names.

## PHASE 7 — DIRECT ENDPOINT VERIFICATION

For each of the three target datasets:

1. Capture a successful request originating from the browser.
2. Reconstruct the request using curl or Python.
3. Check the HTTP status and Content-Type.
4. Confirm that the downloaded response contains actual usable data.
5. Save a small sample or image if permitted.
6. Determine whether the request can be repeated without browser session state.
7. Document any required non-secret headers.

Only label an endpoint VERIFIED when a real request succeeds and its contents are confirmed.

Never fabricate responses.

Do not bypass authentication, access controls, or rate limits.

Do not publish or store private cookies, session tokens, or credentials.

## PHASE 8 — OUTPUT FILES

Create the following files in the current working directory:

### 1. bmkg-endpoints.md

Document the three datasets individually, including:

- Exact dataset name
- Verified endpoint URLs
- HTTP methods
- Parameters
- Data format
- Product or station identifiers
- Timestamp behavior
- Coordinate reference system
- Geographic coverage
- Example requests
- Example response structure
- Verification status
- Important limitations

### 2. bmkg-network-requests.json

Store relevant captured HTTP request metadata in structured JSON.

Include:

- Dataset
- Purpose
- Request URL
- HTTP method
- Query parameters
- Safe headers
- Response status
- Content-Type
- Example timestamp
- Verification status

Do not store authentication secrets.

### 3. bmkg-test.py

Create a Python test utility that can:

- Retrieve the latest available radar Balikpapan data.
- Retrieve Himawari-9 Visible imagery.
- Retrieve Himawari-9 EH imagery.
- Save retrieved files using correct extensions.
- Print response status, content type, size, and timestamp.
- Report clear errors if an endpoint is unavailable.

Do not embed guessed endpoints. Only implement endpoints verified during investigation.

### 4. bmkg-discovery-summary.md

Provide a concise comparison table:

| Dataset | Catalog API | Data endpoint | Format | Direct access | Status |
|---|---|---|---|---|---|
| Radar Balikpapan | | | | | |
| Himawari-9 Visible | | | | | |
| Himawari-9 EH | | | | | |

Use VERIFIED, PARTIAL, or NOT FOUND appropriately.

---

## IMPORTANT EXECUTION RULES

- Use Chrome DevTools MCP actively, not just HTTP requests or generic web search.
- Perform actual interactions with the target viewer.
- Capture network requests when a dataset is selected.
- Compare network activity before and after adding each layer.
- Inspect real response content.
- Do not guess endpoint paths.
- Do not stop after discovering a catalog endpoint.
- Continue until the actual image, tile, or raster endpoint is identified.
- Distinguish the metadata API from the data delivery endpoint.
- Avoid aggressive scanning or unnecessary repeated requests.
- Respect the server's access controls and usage limits.
- If an endpoint cannot be found, explain the evidence and exact blocker.
- Keep working through all three datasets even if one fails.

## FINAL SUCCESS CRITERIA

The task is successful when we have independently verified endpoints that can retrieve:

1. Latest Balikpapan radar imagery.
2. Latest Himawari-9 Visible imagery.
3. Latest Himawari-9 EH imagery.

Ideally, all three must be retrievable with Python or curl without manually opening the BMKG web viewer.

Provide exact tested commands and sample file paths.

Start by opening the target website using Chrome DevTools MCP, then investigate each dataset systematically.