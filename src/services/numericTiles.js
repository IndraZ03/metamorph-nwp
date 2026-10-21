/**
 * Client inspect of Terrain-RGB numeric WebP tiles.
 * val = ((R * 65536 + G * 256 + B) / 10) - 1000
 * Alpha 0 = nodata.
 */

const OFFSET = 1000;
const SCALE = 10;
const TILE = 256;

const BULAN = [
  '',
  'Januari',
  'Februari',
  'Maret',
  'April',
  'Mei',
  'Juni',
  'Juli',
  'Agustus',
  'September',
  'Oktober',
  'November',
  'Desember',
];

const BULAN_SHORT = [
  '',
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'Mei',
  'Jun',
  'Jul',
  'Agu',
  'Sep',
  'Okt',
  'Nov',
  'Des',
];

const _geoCache = new Map();
const _bmpCache = new Map();
const BMP_CACHE_MAX = 64;

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

export function lonLatToTile(lon, lat, z) {
  const n = 2 ** z;
  const latRad = (clamp(lat, -85.05112878, 85.05112878) * Math.PI) / 180;
  const xFloat = ((lon + 180) / 360) * n;
  const yFloat = (1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2 * n;
  const x = Math.floor(xFloat);
  const y = Math.floor(yFloat);
  return {
    z,
    x,
    y,
    px: clamp(Math.floor((xFloat - x) * TILE), 0, TILE - 1),
    py: clamp(Math.floor((yFloat - y) * TILE), 0, TILE - 1),
  };
}

export function pickInspectZoom(minzoom, maxzoom, mapZoom) {
  const z = Math.round(mapZoom ?? maxzoom);
  return clamp(z, minzoom ?? 0, maxzoom ?? 6);
}

export function decodeRgb(r, g, b, a) {
  if (a === 0) return null;
  return Math.round(((r * 65536 + g * 256 + b) / SCALE - OFFSET) * 100) / 100;
}

function fillTemplate(template, map) {
  let url = template;
  for (const [k, v] of Object.entries(map)) {
    url = url.replaceAll(`{${k}}`, String(v));
  }
  return url;
}

export function numericTileUrl(modelId, manifest, varId, step, z, x, y) {
  if (modelId === 'ecmwf') {
    const run = manifest.run_id;
    const template =
      manifest.numeric_tiles ||
      '/ecmwf/numeric/{run_id}/{var}/{step}/{z}/{x}/{y}.webp';
    return (
      fillTemplate(template, {
        run_id: run,
        var: varId,
        step: step.token,
        z,
        x,
        y,
      }) + '?v=2'
    );
  }
  if (modelId === 'gfs') {
    const run = String(manifest.run || '')
      .replace(/[-:TZ]/g, '')
      .slice(0, 10);
    const template =
      manifest.numeric_tile_url_template ||
      '/tiles/gfs-numeric/{run}/{valid}/{variable}/{z}/{x}/{y}.webp';
    return (
      fillTemplate(template, {
        run,
        valid: step.token,
        variable: varId,
        z,
        x,
        y,
      }) + '?v=2'
    );
  }
  if (modelId === 'icon') {
    const template =
      manifest.numeric_tile_url_template ||
      '/api/icon/tiles-numeric/{run}/{param}/{step}/{z}/{x}/{y}.webp';
    return (
      fillTemplate(template, {
        run: manifest.run_id,
        param: varId,
        step: step.token,
        z,
        x,
        y,
      }) + '?v=2'
    );
  }
  return '';
}

async function pixelAt(url, px, py) {
  let bmp = _bmpCache.get(url);
  if (!bmp) {
    const res = await fetch(url, { cache: 'force-cache' });
    if (!res.ok) return null;
    const blob = await res.blob();
    if (!blob.size || blob.size < 40) return null;
    try {
      bmp = await createImageBitmap(blob);
    } catch {
      return null;
    }
    if (bmp.width < 2 || bmp.height < 2) {
      bmp.close?.();
      return null;
    }
    if (_bmpCache.size >= BMP_CACHE_MAX) {
      const first = _bmpCache.keys().next().value;
      const old = _bmpCache.get(first);
      _bmpCache.delete(first);
      old?.close?.();
    }
    _bmpCache.set(url, bmp);
  }
  const canvas = document.createElement('canvas');
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bmp, px, py, 1, 1, 0, 0, 1, 1);
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
  return decodeRgb(r, g, b, a);
}

function parseTime(isoOrT) {
  if (isoOrT == null || isoOrT === '') return NaN;
  if (typeof isoOrT === 'number') return isoOrT;
  const s = String(isoOrT);
  const n = Date.parse(s);
  if (!Number.isNaN(n)) return n;
  const m = s.match(/^(\d{4})(\d{2})(\d{2})(\d{2})$/);
  if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]);
  return NaN;
}

export function formatWib(iso) {
  const t = parseTime(iso);
  if (Number.isNaN(t)) return '–';
  const wib = new Date(t + 7 * 3600 * 1000);
  const d = wib.getUTCDate();
  const m = BULAN[wib.getUTCMonth() + 1];
  const y = wib.getUTCFullYear();
  const hh = String(wib.getUTCHours()).padStart(2, '0');
  const mm = String(wib.getUTCMinutes()).padStart(2, '0');
  return `${d} ${m} ${y}, ${hh}:${mm} WIB`;
}

export function formatWibShort(iso) {
  const t = parseTime(iso);
  if (Number.isNaN(t)) return '–';
  const wib = new Date(t + 7 * 3600 * 1000);
  const d = wib.getUTCDate();
  const m = BULAN_SHORT[wib.getUTCMonth() + 1];
  const hh = String(wib.getUTCHours()).padStart(2, '0');
  const mm = String(wib.getUTCMinutes()).padStart(2, '0');
  return `${d} ${m} ${hh}:${mm}`;
}

export function formatValue(varId, value, units) {
  if (value == null || Number.isNaN(value)) return '–';
  let v = value;
  let u = units || '';
  if (varId === 'tcc' && u !== '%') {
    v = value * 100;
    u = '%';
  }
  const abs = Math.abs(v);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  const n = v.toFixed(digits);
  return u ? `${n} ${u}` : n;
}

export async function reverseGeocode(lat, lon) {
  const key = `${lat.toFixed(2)},${lon.toFixed(2)}`;
  if (_geoCache.has(key)) return _geoCache.get(key);
  const fallback = {
    kecamatan: 'Perairan / Luar Wilayah',
    kabupaten_kota: '–',
    provinsi: '–',
    negara: 'Indonesia',
    display_name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
  };
  try {
    const url = `/api/geocode?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}`;
    const res = await fetch(url, { signal: AbortSignal.timeout(2500) });
    if (!res.ok) {
      _geoCache.set(key, fallback);
      return fallback;
    }
    const data = await res.json();
    const addr = data.address || {};
    const loc = {
      kecamatan:
        addr.suburb ||
        addr.district ||
        addr.subdistrict ||
        addr.town ||
        addr.village ||
        addr.hamlet ||
        '–',
      kabupaten_kota:
        addr.city || addr.county || addr.municipality || addr.regency || '–',
      provinsi: addr.state || addr.province || '–',
      negara: addr.country || 'Indonesia',
      display_name: data.display_name || fallback.display_name,
    };
    _geoCache.set(key, loc);
    return loc;
  } catch {
    _geoCache.set(key, fallback);
    return fallback;
  }
}

export async function inspectValues({
  modelId,
  manifest,
  step,
  params,
  lat,
  lon,
  zoom,
  onPartial,
}) {
  const minZ = manifest.minzoom ?? manifest.zoom_min ?? manifest.domain?.zoom_min ?? 0;
  const maxZ = manifest.maxzoom ?? manifest.zoom_max ?? manifest.domain?.zoom_max ?? 6;
  const z = pickInspectZoom(minZ, maxZ, zoom);
  const tile = lonLatToTile(lon, lat, z);
  const list = params || [];
  const nilai = {};
  for (const p of list) {
    nilai[p.id] = {
      id: p.id,
      name: p.label,
      short: p.short || p.label,
      value: null,
      unit: p.units || '',
      display: '–',
    };
  }
  const tanggal = formatWib(step.validTime);
  onPartial?.({ lat, lon, z: tile.z, nilai: { ...nilai }, tanggal });
  await Promise.all(
    list.map(async (p) => {
      const url = numericTileUrl(modelId, manifest, p.id, step, tile.z, tile.x, tile.y);
      let value = null;
      try {
        value = url ? await pixelAt(url, tile.px, tile.py) : null;
      } catch {
        value = null;
      }
      nilai[p.id] = {
        ...nilai[p.id],
        value,
        display: formatValue(p.id, value, p.units),
      };
      onPartial?.({
        lat,
        lon,
        z: tile.z,
        nilai: { ...nilai },
        tanggal,
      });
    })
  );
  return {
    lat,
    lon,
    z: tile.z,
    nilai,
    tanggal,
  };
}

export async function inspectPoint(opts) {
  const [values, lokasi] = await Promise.all([
    inspectValues(opts),
    reverseGeocode(opts.lat, opts.lon),
  ]);
  return { ...values, lokasi };
}
