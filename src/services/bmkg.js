/**
 * API utilities for BMKG NWP Viewer
 */

export const RADAR_CATALOG_URL = 'https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/radar.json';
export const SATELLITE_CATALOG_URL = 'https://cuaca.bmkg.go.id/data/public/nwp-viewer/meta/satellite.json';

export function proxyCuaca(targetUrl) {
  return `/api/proxy-cuaca?url=${encodeURIComponent(targetUrl)}`;
}

/**
 * Returns a standard MapLibre tile URL pointing to local Vite middleware
 * /api/proxy-satellite-tile/{z}/{x}/{-y}.png?tiletype=...&modelname=...&param=...&baserun=...
 */
export function proxySatelliteTile(template, baserun) {
  if (!template) return '';
  // Template format: https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?tiletype=...&modelname=...&param=...&baserun={baserun}
  // Convert upstream prefix to local proxy path:
  const localUrl = template
    .replace('https://satellite.bmkg.go.id/api22/tile', '/api/proxy-satellite-tile')
    .replace('{baserun}', encodeURIComponent(baserun));

  return localUrl;
}

export async function fetchRadarCatalog() {
  const res = await fetch(proxyCuaca(RADAR_CATALOG_URL));
  if (!res.ok) throw new Error(`Radar catalog failed: ${res.status}`);
  return await res.json();
}

export async function fetchRadarManifest(stationCode, product = 'CMAX', baseDir = null) {
  const base = (baseDir || 'https://cuaca.bmkg.go.id/data/public/nwp-viewer/data/wxr').replace(/\/+$/, '');
  const url = `${base}/${stationCode}/${product}/${stationCode}_${product}_latest.json`;
  const res = await fetch(proxyCuaca(url));
  if (!res.ok) throw new Error(`Manifest failed for ${stationCode}: ${res.status}`);
  return await res.json();
}

export async function fetchSatelliteCatalog() {
  const res = await fetch(proxyCuaca(SATELLITE_CATALOG_URL));
  if (!res.ok) throw new Error(`Satellite catalog failed: ${res.status}`);
  return await res.json();
}

/**
 * Generate candidate ISO UTC baseruns (10-minute cadence)
 */
export function generateBaseruns(count = 12, stepMinutes = 10, lagMinutes = 20) {
  const stepMs = stepMinutes * 60 * 1000;
  const lagMs = lagMinutes * 60 * 1000;
  const nowMs = Date.now();
  const latestMs = Math.floor((nowMs - lagMs) / stepMs) * stepMs;

  const list = [];
  for (let i = 0; i < count; i++) {
    const ms = latestMs - (i * stepMs);
    const iso = new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z');
    list.push(iso);
  }
  return list; // latest first
}

/**
 * Test candidate baseruns against the BMKG tile service to find the latest valid 200 OK timestamp
 */
export function satelliteFrames(tokens = []) {
  return [...new Set(tokens)].filter(token => typeof token === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(token) && Number.isFinite(Date.parse(token)))
    .map(token => ({ token, t: Date.parse(token) })).sort((a, b) => a.t - b.t);
}
export async function verifySatellite(product, token, signal) {
  signal?.throwIfAborted();
  const template = product.url || product.tile_url;
  if (!template || !satelliteFrames([token]).length) return false;
  const url = proxySatelliteTile(template, token).replace('{z}', '4').replace('{x}', '13').replace('{-y}', '7').replace('{y}', '7');
  const response = await fetch(url, { method: 'HEAD', signal });
  signal?.throwIfAborted();
  return response.ok;
}
export async function findLatestValidBaserun(product, signal) {
  const candidates = generateBaseruns(12, product.step_minutes || 10, 10);
  const list = [];
  for (const token of candidates) {
    try {
      if (await verifySatellite(product, token, signal)) list.push(token);
    } catch (error) {
      if (signal?.aborted || error.name === 'AbortError') throw error;
    }
  }
  if (!list.length) throw new Error('Data satelit tidak tersedia.');
  return { current: list[0], list };
}
