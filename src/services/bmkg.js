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
export async function findLatestValidBaserun(product) {
  const template = product.url || product.tile_url;
  const candidates = generateBaseruns(12, product.step_minutes || 10, 10);

  if (!template) {
    return {
      current: candidates[1] || candidates[0],
      list: candidates.slice(1),
    };
  }

  // Test sample tile at Indonesia (z=4, x=13, y=7)
  for (const br of candidates) {
    const samplePath = `/api/proxy-satellite-tile/4/13/7.png?tiletype=himawari9&modelname=${product.modelname || (product.param === 'VS' ? 'himawari9hires' : 'himawari9')}&param=${product.param}&baserun=${encodeURIComponent(br)}`;
    try {
      const res = await fetch(samplePath, { method: 'HEAD' });
      if (res.ok) {
        const validIndex = candidates.indexOf(br);
        return {
          current: br,
          list: candidates.slice(validIndex),
        };
      }
    } catch {
      // Continue to next timestamp
    }
  }

  // Fallback if test fails
  return {
    current: candidates[1] || candidates[0],
    list: candidates.slice(1),
  };
}
