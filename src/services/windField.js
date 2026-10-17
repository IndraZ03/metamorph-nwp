import { decodeRgb, lonLatToTile, numericTileUrl } from './numericTiles.js';

const COMPONENTS = { ecmwf: ['u10', 'v10'], gfs: ['u10', 'v10'], icon: ['u_10m', 'v_10m'] };
const TILE_SIZE = 256;

async function loadNumericTile(url, signal) {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Wind tile HTTP ${response.status}`);
  const bitmap = await createImageBitmap(await response.blob(), { premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
  try {
    if (bitmap.width !== TILE_SIZE || bitmap.height !== TILE_SIZE) throw new Error('Invalid wind tile size');
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = TILE_SIZE;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(bitmap, 0, 0);
    const rgba = ctx.getImageData(0, 0, TILE_SIZE, TILE_SIZE).data;
    const values = new Float32Array(TILE_SIZE * TILE_SIZE);
    for (let i = 0; i < values.length; i++) {
      values[i] = decodeRgb(...rgba.subarray(i * 4, i * 4 + 4)) ?? NaN;
    }
    return values;
  } finally {
    bitmap.close();
  }
}

/** Numeric U/V tiles only. No synthetic fallback or color-to-speed inference. */
export class WindField {
  constructor({ modelId, manifest, step, bbox, zoom }, loadTile = loadNumericTile) {
    this.modelId = modelId;
    this.manifest = manifest;
    this.step = step;
    this.bbox = bbox;
    this.zoom = Math.min(zoom.maxzoom, Math.max(3, zoom.minzoom));
    this.loadTile = loadTile;
    this.tiles = new Map();
  }

  async load(signal) {
    const components = COMPONENTS[this.modelId];
    if (!components) throw new Error('Unsupported wind model');
    const [west, south, east, north] = this.bbox;
    const topLeft = lonLatToTile(west, north, this.zoom);
    const bottomRight = lonLatToTile(east, south, this.zoom);
    const jobs = [];
    for (let x = topLeft.x; x <= bottomRight.x; x++) {
      for (let y = topLeft.y; y <= bottomRight.y; y++) {
        for (const component of components) jobs.push({ x, y, component });
      }
    }
    let cursor = 0;
    await Promise.all(Array.from({ length: Math.min(6, jobs.length) }, async () => {
      while (cursor < jobs.length) {
        if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
        const { x, y, component } = jobs[cursor++];
        try {
          const url = numericTileUrl(this.modelId, this.manifest, component, this.step, this.zoom, x, y);
          const values = await this.loadTile(url, signal);
          this.tiles.set(`${component}:${x}:${y}`, values);
        } catch (error) {
          if (signal.aborted) throw error;
          // Missing tiles remain nodata, including edges and incomplete runs.
        }
      }
    }));
    let hasPair = false;
    for (const key of this.tiles.keys()) {
      if (key.startsWith(`${components[0]}:`) && this.tiles.has(key.replace(`${components[0]}:`, `${components[1]}:`))) hasPair = true;
    }
    if (!hasPair) throw new Error('Data U/V 10 m belum tersedia untuk run ini');
  }

  pixel(component, x, y) {
    const tile = this.tiles.get(`${component}:${Math.floor(x / TILE_SIZE)}:${Math.floor(y / TILE_SIZE)}`);
    if (!tile) return NaN;
    return tile[((y % TILE_SIZE) + TILE_SIZE) % TILE_SIZE * TILE_SIZE + ((x % TILE_SIZE) + TILE_SIZE) % TILE_SIZE];
  }

  sample(lon, lat) {
    const [west, south, east, north] = this.bbox;
    if (lon < west || lon > east || lat < south || lat > north) return null;
    const n = 2 ** this.zoom * TILE_SIZE;
    // Numeric tiles sample pixel centers. Interpolate components, never direction angles.
    const x = (lon + 180) / 360 * n - 0.5;
    const y = (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * n - 0.5;
    const ix = Math.floor(x), iy = Math.floor(y);
    const fx = x - ix, fy = y - iy;
    const values = COMPONENTS[this.modelId].map(component => {
      const a = this.pixel(component, ix, iy), b = this.pixel(component, ix + 1, iy);
      const c = this.pixel(component, ix, iy + 1), d = this.pixel(component, ix + 1, iy + 1);
      return [a, b, c, d].every(Number.isFinite)
        ? a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy
        : NaN;
    });
    return values.every(Number.isFinite) ? { u: values[0], v: values[1] } : null;
  }
}

/** Visual demo only, never model data or a weather forecast. */
export class DemoWindField {
  constructor(bbox = [88, -15, 148, 12]) {
    this.bbox = bbox;
  }

  sample(lon, lat) {
    const [west, south, east, north] = this.bbox;
    if (lon < west || lon > east || lat < south || lat > north) return null;
    const turn = (Math.tanh(lat / 6) + 1) / 2;
    return { u: -9 + 5 * turn, v: 4 - turn };
  }
}

/** Project east/north wind into camera coordinates, preserving bearing and pitch. */
export function screenVelocity(map, lon, lat, wind) {
  const origin = map.project([lon, lat]);
  const cosLat = Math.max(0.01, Math.cos(lat * Math.PI / 180));
  const end = map.project([lon + wind.u * 0.01 / cosLat, lat + wind.v * 0.01]);
  const pixelsPerDegree = 512 * 2 ** map.getZoom() / 360;
  const scale = 6 * cosLat / (0.01 * pixelsPerDegree);
  return { x: (end.x - origin.x) * scale, y: (end.y - origin.y) * scale };
}
