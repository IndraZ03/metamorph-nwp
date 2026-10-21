import {
  lonLatToTile,
  numericTileUrl,
  pickInspectZoom,
  readNumericPixel,
  reverseGeocode,
} from './numericTiles.js';
import { listSteps, modelRunId, modelRunTime, MODELS } from './nwp.js';
import { normalizePrecipitationSeries, windFromComponents } from './meteogram/normalize.js';
import { classifyWeatherCondition } from './meteogram/conditions.js';

const MODEL_VARS = {
  ecmwf: {
    temp: 't2m',
    dew: 'd2m',
    rh: 'rh',
    pressure: 'msl',
    cloud: 'tcc',
    rain: 'tp',
    wind: 'wind10m',
    u: 'u10',
    v: 'v10',
    cape: 'cape',
  },
  gfs: {
    temp: 'temperature',
    dew: 'dew_point',
    rh: 'rh',
    pressure: 'pressure',
    cloud: 'clouds',
    rain: 'rain',
    wind: 'wind',
    u: 'u10',
    v: 'v10',
    cape: 'cape',
  },
  icon: {
    temp: 't_2m',
    dew: 'td_2m',
    rh: 'relhum_2m',
    pressure: 'pmsl',
    cloud: 'clct',
    rain: 'tot_prec',
    wind: 'wind_10m',
    u: 'u_10m',
    v: 'v_10m',
    cape: 'cape_ml',
  },
};

const _seriesCache = new Map();
const CACHE_MAX = 32;

export function meteogramKey(modelId, runId, lat, lon, zoom) {
  const latitude = Number(lat);
  const longitude = Number(lon);
  const latStr = Number.isFinite(latitude) ? latitude.toFixed(4) : String(lat);
  const lonStr = Number.isFinite(longitude) ? longitude.toFixed(4) : String(lon);
  return `${modelId}:${runId}:${latStr},${lonStr}:z${zoom}`;
}

export function clearMeteogramCache() {
  _seriesCache.clear();
}

/**
 * Manifest readiness signature: ignores volatile timestamps like updated_at
 * so identical forecast data does not trigger unnecessary refetches.
 */
export function meteogramManifestKey(modelId, manifest) {
  if (!manifest) return '';
  const runId = modelRunId(modelId, manifest);
  const runTime = modelRunTime(modelId, manifest);
  const records = manifest.steps || manifest.timesteps || [];
  const readiness = records.map(row => ({
    step: row.step ?? row.forecast_hour, valid: row.valid_time ?? row.valid,
    ready: row.ready, error: row.error,
    vars: row.vars ? [...row.vars].sort() : undefined,
    params: row.params ? [...row.params].sort() : undefined,
    tiles: row.tiles ? Object.entries(row.tiles).sort(([a], [b]) => a.localeCompare(b)) : undefined,
    rain: row.rain_step_range,
  }));
  return JSON.stringify([modelId, runId, runTime, readiness,
    manifest.numeric_tile_url_template, manifest.numeric_url_template,
    manifest.minzoom, manifest.maxzoom, manifest.zoom_min, manifest.zoom_max, manifest.domain]);
}

/**
 * Bounded worker pool to run promise tasks with strict max concurrency.
 */
export async function runWithConcurrency(tasks, limit = 6, signal) {
  const results = [];
  let index = 0;

  async function worker() {
    while (index < tasks.length) {
      signal?.throwIfAborted();
      const currentIdx = index++;
      try {
        results[currentIdx] = await tasks[currentIdx]();
      } catch (err) {
        if (signal?.aborted) throw err;
        results[currentIdx] = { error: err?.message || 'Gagal membaca pixel' };
      }
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => worker());
  await Promise.all(workers);
  return results;
}

/**
 * Fetch meteogram time series at (latitude, longitude).
 */
export async function fetchMeteogram({
  modelId,
  manifest,
  latitude,
  longitude,
  signal,
  sampler = readNumericPixel,
  geocoder = reverseGeocode,
}) {
  signal?.throwIfAborted();

  const spec = MODELS[modelId];
  if (!spec) throw new Error(`Model '${modelId}' tidak didukung`);

  const lat = latitude;
  const lon = longitude;
  const [w, s, e, n] = spec.bbox || [-180, -90, 180, 90];

  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lon < w || lon > e || lat < s || lat > n) {
    const latStr = Number.isFinite(lat) ? lat.toFixed(2) : String(latitude);
    const lonStr = Number.isFinite(lon) ? lon.toFixed(2) : String(longitude);
    throw new Error(`Koordinat (${latStr}, ${lonStr}) di luar cakupan model ${spec.title}`);
  }

  const runId = modelRunId(modelId, manifest);
  const runTime = modelRunTime(modelId, manifest);
  const varMap = MODEL_VARS[modelId] || {};

  const minZ = manifest.minzoom ?? manifest.zoom_min ?? manifest.domain?.zoom_min ?? spec.minzoom ?? 0;
  const maxZ = manifest.maxzoom ?? manifest.zoom_max ?? manifest.domain?.zoom_max ?? spec.maxzoom ?? 6;
  const sampleZoom = pickInspectZoom(minZ, maxZ, maxZ);
  const tile = lonLatToTile(lon, lat, sampleZoom);

  const manifestSig = meteogramManifestKey(modelId, manifest);
  const cacheKey = `${meteogramKey(modelId, runId, lat, lon, sampleZoom)}:${lat}:${lon}:${tile.x}:${tile.y}:${tile.px}:${tile.py}:${manifestSig}`;

  if (_seriesCache.has(cacheKey)) {
    return _seriesCache.get(cacheKey);
  }

  const rawSteps = listSteps(modelId, manifest);
  // Deduplicate timesteps by validTime/t
  const seenTimes = new Set();
  const steps = [];
  for (const s of rawSteps) {
    const key = s.validTime || s.t;
    if (key && !seenTimes.has(key)) {
      seenTimes.add(key);
      steps.push(s);
    }
  }

  if (!steps.length) {
    return {
      latitude: lat,
      longitude: lon,
      modelId,
      modelTitle: spec.title,
      runId,
      runTime,
      sampling: {
        method: 'numeric_tile_pixel',
        zoom: sampleZoom,
        tileX: tile.x,
        tileY: tile.y,
        px: tile.px,
        py: tile.py,
        precision: 0.1,
      },
      points: [],
      errors: ['Tidak ada timestep yang tersedia dalam manifest'],
      missing: [],
    };
  }

  const locationPromise = geocoder(lat, lon).catch(() => ({
    display_name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
  }));

  const paramsToFetch = ['temp', 'rain', 'dew', 'rh', 'pressure', 'cloud', 'wind', 'u', 'v', 'cape'];
  const tasks = [];
  const taskMap = [];
  const missing = [];
  const errors = [];

  for (let sIdx = 0; sIdx < steps.length; sIdx++) {
    const step = steps[sIdx];
    for (const pKey of paramsToFetch) {
      const varId = varMap[pKey];
      if (!varId) continue;

      let available = true;
      if (modelId === 'ecmwf') {
        const rawStep = (manifest.steps || []).find((s) => s.step === step.step);
        if (rawStep && rawStep.vars && rawStep.vars.length && !rawStep.vars.includes(varId)) {
          available = false;
        }
      } else if (modelId === 'gfs') {
        const rawStep = (manifest.timesteps || []).find(
          (s) => s.forecast_hour === step.step || s.valid === step.validTime
        );
        if (rawStep) {
          if (rawStep.tiles) {
            const count = rawStep.tiles[varId];
            if (count == null || count === 0) available = false;
          } else if (rawStep.params && !rawStep.params.includes(varId)) {
            available = false;
          }
        }
      } else if (modelId === 'icon') {
        const rawStep = (manifest.timesteps || []).find((s) => s.step === step.step);
        if (rawStep && Array.isArray(rawStep.params) && rawStep.params.length && !rawStep.params.includes(varId)) {
          available = false;
        }
      }

      if (!available) {
        missing.push(`${step.validTime}: ${varId}`);
        continue;
      }

      const url = numericTileUrl(modelId, manifest, varId, step, tile.z, tile.x, tile.y);
      if (!url) continue;

      taskMap.push({ sIdx, pKey, varId, stepTime: step.validTime });
      tasks.push(async () => {
        try {
          return await sampler(url, tile.px, tile.py, { signal });
        } catch (err) {
          if (signal?.aborted) throw err;
          return { error: err?.message || 'Tile fetch/decode error' };
        }
      });
    }
  }

  const results = await runWithConcurrency(tasks, 6, signal);
  signal?.throwIfAborted();

  const rawData = steps.map((s) => ({
    validTime: s.validTime,
    t: s.t,
    step: s.step,
  }));

  for (let i = 0; i < taskMap.length; i++) {
    const { sIdx, pKey, varId, stepTime } = taskMap[i];
    const val = results[i];
    if (val && typeof val === 'object' && 'error' in val) {
      errors.push(`${stepTime} ${varId}: ${val.error}`);
    } else if (Number.isFinite(val)) {
      rawData[sIdx][pKey] = val;
    } else {
      missing.push(`${stepTime}: ${varId} (nodata)`);
    }
  }

  const intermediatePoints = rawData.map((row) => {
    const rawStep =
      modelId === 'ecmwf'
        ? (manifest.steps || []).find((s) => s.step === row.step)
        : (manifest.timesteps || []).find((s) => s.step === row.step || s.forecast_hour === row.step);

    const cloudMax = modelId === 'ecmwf' ? 1 : 100;
    const cloudPct = Number.isFinite(row.cloud) && row.cloud >= 0 && row.cloud <= cloudMax
      ? Math.round(row.cloud * (modelId === 'ecmwf' ? 100 : 1)) : null;

    let windSpeed = row.wind != null ? Math.round(row.wind * 10) / 10 : null;
    let windDir = null;
    let maximumWind = null;

    if (row.u != null && row.v != null) {
      const fromComp = windFromComponents(row.u, row.v);
      if (fromComp.speed != null) windSpeed = fromComp.speed;
      if (fromComp.direction != null) windDir = fromComp.direction;
    }

    if (modelId === 'icon') {
      if (row.wind != null) {
        maximumWind = Math.round(row.wind * 10) / 10;
        if (row.u == null || row.v == null) {
          windSpeed = null; // ICON wind_10m is VMAX, not mean wind
        }
      }
    }

    return {
      validTime: row.validTime,
      t: row.t,
      step: row.step,
      rainStepRange: rawStep?.rain_step_range || null,
      rawRain: row.rain,
      temperatureC: row.temp != null ? Math.round(row.temp * 10) / 10 : null,
      dewPointC: row.dew != null ? Math.round(row.dew * 10) / 10 : null,
      relativeHumidityPct: row.rh != null ? Math.min(100, Math.max(0, Math.round(row.rh))) : null,
      pressureHpa: row.pressure != null ? Math.round(row.pressure * 10) / 10 : null,
      totalCloudCoverPct: cloudPct,
      windSpeedMs: windSpeed,
      windDirectionDeg: windDir,
      maximumWindMs: maximumWind,
      capeJkg: row.cape != null ? Math.round(row.cape) : null,
    };
  });

  const normalizedRainPoints = normalizePrecipitationSeries(modelId, intermediatePoints, runTime);

  const points = normalizedRainPoints.map((pt) => ({
    ...pt,
    weatherCondition: classifyWeatherCondition(pt, lat, lon),
  }));

  const location = await locationPromise;
  signal?.throwIfAborted();

  const series = {
    latitude: lat,
    longitude: lon,
    location,
    modelId,
    modelTitle: spec.title,
    runId,
    runTime,
    sampling: {
      method: 'numeric_tile_pixel',
      zoom: sampleZoom,
      tileX: tile.x,
      tileY: tile.y,
      px: tile.px,
      py: tile.py,
      precision: 0.1,
    },
    points,
    errors,
    missing,
  };

  // Only cache if there are actual points and not completely failing
  const hasValidData = points.some((p) => p.temperatureC != null || p.precipitationMm != null || p.windSpeedMs != null);
  if (hasValidData && !errors.length) {
    if (_seriesCache.size >= CACHE_MAX) {
      const oldest = _seriesCache.keys().next().value;
      _seriesCache.delete(oldest);
    }
    _seriesCache.set(cacheKey, series);
  }

  return series;
}
