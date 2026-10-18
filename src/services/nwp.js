import {
  ECMWF_DEFAULT_VAR,
  ECMWF_LATEST,
  ECMWF_LEGENDS,
  ECMWF_PARAMS,
  ECMWF_POLL_MS,
  fetchLatest as fetchEcmwfLatest,
  legendCss as ecmwfLegendCss,
  pickStep as pickEcmwfStep,
  sourceKey as ecmwfSourceKey,
  tileUrl as ecmwfTileUrl,
} from './ecmwf.js';

export { ECMWF_POLL_MS };

export const GLOBAL_MODELS = ['ecmwf', 'gfs', 'icon'];

export const GFS_PARAMS = [
  { id: 'temperature', label: 'Temperature', short: 'Temp', units: '°C' },
  { id: 'wind', label: 'Wind Speed', short: 'Wind', units: 'm/s' },
  { id: 'rh', label: 'Relative Humidity', short: 'RH', units: '%' },
  { id: 'rain', label: 'Rain accumulation', short: 'Rain', units: 'mm' },
  { id: 'pressure', label: 'Pressure', short: 'P', units: 'hPa' },
  { id: 'dew_point', label: 'Dew Point', short: 'Td', units: '°C' },
  { id: 'cape', label: 'CAPE', short: 'CAPE', units: 'J/kg' },
  { id: 'clouds', label: 'Clouds', short: 'Cloud', units: '%' },
];

export const ICON_PARAMS = [
  { id: 't_2m', label: 'Temperature', short: 'Temp', units: '°C' },
  { id: 'wind_10m', label: 'Wind Speed', short: 'Wind', units: 'm/s' },
  { id: 'relhum_2m', label: 'Relative Humidity', short: 'RH', units: '%' },
  { id: 'tot_prec', label: 'Rain accumulation', short: 'Rain', units: 'mm' },
  { id: 'pmsl', label: 'Pressure', short: 'P', units: 'hPa' },
  { id: 'td_2m', label: 'Dew Point', short: 'Td', units: '°C' },
  { id: 'cape_ml', label: 'CAPE', short: 'CAPE', units: 'J/kg' },
  { id: 'clct', label: 'Clouds', short: 'Cloud', units: '%' },
];

/** Stops must match engine/gfs/config.py */
export const GFS_LEGENDS = {
  temperature: {
    min: -5,
    max: 40,
    units: '°C',
    label: 'Temperature',
    stops: [
      [0.0, 'rgb(8,48,107)'],
      [0.11, 'rgb(33,113,181)'],
      [0.33, 'rgb(107,174,214)'],
      [0.44, 'rgb(199,233,192)'],
      [0.56, 'rgb(255,255,204)'],
      [0.67, 'rgb(255,237,160)'],
      [0.73, 'rgb(254,217,118)'],
      [0.78, 'rgb(254,178,76)'],
      [0.84, 'rgb(253,141,60)'],
      [0.91, 'rgb(252,78,42)'],
      [1.0, 'rgb(177,0,38)'],
    ],
  },
  dew_point: {
    min: -5,
    max: 30,
    units: '°C',
    label: 'Dew Point',
    stops: [
      [0.0, 'rgb(8,48,107)'],
      [0.14, 'rgb(33,113,181)'],
      [0.43, 'rgb(107,174,214)'],
      [0.57, 'rgb(161,217,155)'],
      [0.71, 'rgb(255,255,204)'],
      [0.86, 'rgb(254,178,76)'],
      [1.0, 'rgb(177,0,38)'],
    ],
  },
  rh: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Relative Humidity',
    stops: [
      [0.0, 'rgb(255,255,255)'],
      [0.2, 'rgb(229,245,224)'],
      [0.4, 'rgb(161,217,155)'],
      [0.6, 'rgb(65,171,93)'],
      [0.8, 'rgb(35,139,69)'],
      [0.9, 'rgb(0,90,50)'],
      [1.0, 'rgb(0,38,7)'],
    ],
  },
  pressure: {
    min: 990,
    max: 1020,
    units: 'hPa',
    label: 'Pressure',
    stops: [
      [0.0, 'rgb(49,54,149)'],
      [0.17, 'rgb(69,117,180)'],
      [0.33, 'rgb(116,173,209)'],
      [0.5, 'rgb(171,217,233)'],
      [0.67, 'rgb(255,255,191)'],
      [0.77, 'rgb(254,224,144)'],
      [0.83, 'rgb(253,174,97)'],
      [0.93, 'rgb(244,109,67)'],
      [1.0, 'rgb(215,48,39)'],
    ],
  },
  rain: {
    min: 0.1,
    max: 50,
    units: 'mm',
    label: 'Rain accumulation',
    ticks: ['0.1', '1', '5', '20', '50'],
    stops: [
      [0.0, 'rgb(207,232,255)'],
      [0.02, 'rgb(127,191,255)'],
      [0.05, 'rgb(63,143,255)'],
      [0.1, 'rgb(0,87,217)'],
      [0.2, 'rgb(0,200,83)'],
      [0.4, 'rgb(255,235,0)'],
      [0.6, 'rgb(255,123,0)'],
      [1.0, 'rgb(177,0,38)'],
    ],
  },
  cape: {
    min: 0,
    max: 4000,
    units: 'J/kg',
    label: 'CAPE',
    stops: [
      [0.0, 'rgb(255,255,255)'],
      [0.06, 'rgb(255,255,204)'],
      [0.13, 'rgb(255,237,160)'],
      [0.25, 'rgb(254,217,118)'],
      [0.38, 'rgb(254,178,76)'],
      [0.5, 'rgb(253,141,60)'],
      [0.63, 'rgb(252,78,42)'],
      [0.75, 'rgb(227,26,28)'],
      [1.0, 'rgb(128,0,38)'],
    ],
  },
  clouds: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Cloud cover',
    stops: [
      [0.0, 'rgb(255,255,255)'],
      [1.0, 'rgb(217,217,217)'],
    ],
  },
  wind: {
    min: 0,
    max: 30,
    units: 'm/s',
    label: 'Wind Speed',
    stops: [
      [0.0, 'rgb(230,245,255)'],
      [0.1, 'rgb(170,222,250)'],
      [0.2, 'rgb(100,200,210)'],
      [0.33, 'rgb(80,210,120)'],
      [0.5, 'rgb(250,225,60)'],
      [0.67, 'rgb(250,140,40)'],
      [0.83, 'rgb(230,40,40)'],
      [1.0, 'rgb(160,20,150)'],
    ],
  },
};

/** Stops must match backend/engine/colormaps.py */
export const ICON_LEGENDS = {
  t_2m: {
    min: -10,
    max: 45,
    units: '°C',
    label: 'Temperature',
    stops: [
      [0.0, 'rgb(40,20,140)'],
      [0.18, 'rgb(0,150,230)'],
      [0.45, 'rgb(50,200,80)'],
      [0.62, 'rgb(240,220,20)'],
      [0.73, 'rgb(255,120,0)'],
      [0.85, 'rgb(220,30,30)'],
      [1.0, 'rgb(180,0,140)'],
    ],
  },
  relhum_2m: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Relative Humidity',
    stops: [
      [0.0, 'rgb(180,140,80)'],
      [0.35, 'rgb(160,200,100)'],
      [0.5, 'rgb(130,210,120)'],
      [0.7, 'rgb(40,180,210)'],
      [0.85, 'rgb(30,110,220)'],
      [1.0, 'rgb(15,30,180)'],
    ],
  },
  tot_prec: {
    min: 0,
    max: 250,
    units: 'mm',
    label: 'Rain accumulation',
    ticks: ['0', '10', '50', '100', '250'],
    stops: [
      [0.0, 'rgb(0,0,0)'],
      [0.008, 'rgb(170,230,255)'],
      [0.04, 'rgb(40,180,230)'],
      [0.1, 'rgb(30,200,60)'],
      [0.2, 'rgb(255,230,0)'],
      [0.4, 'rgb(255,100,0)'],
      [0.7, 'rgb(220,20,20)'],
      [1.0, 'rgb(200,0,200)'],
    ],
  },
  pmsl: {
    min: 996,
    max: 1020,
    units: 'hPa',
    label: 'Pressure',
    stops: [
      [0.0, 'rgb(100,20,160)'],
      [0.25, 'rgb(20,130,220)'],
      [0.5, 'rgb(110,190,140)'],
      [0.75, 'rgb(240,190,70)'],
      [1.0, 'rgb(210,50,40)'],
    ],
  },
  td_2m: {
    min: 10,
    max: 32,
    units: '°C',
    label: 'Dew Point',
    stops: [
      [0.0, 'rgb(200,180,130)'],
      [0.27, 'rgb(90,190,130)'],
      [0.5, 'rgb(40,170,220)'],
      [0.73, 'rgb(20,80,210)'],
      [1.0, 'rgb(150,20,180)'],
    ],
  },
  cape_ml: {
    min: 0,
    max: 4000,
    units: 'J/kg',
    label: 'CAPE',
    stops: [
      [0.0, 'rgb(160,220,120)'],
      [0.125, 'rgb(160,220,120)'],
      [0.25, 'rgb(255,230,50)'],
      [0.5, 'rgb(255,130,0)'],
      [0.75, 'rgb(230,30,30)'],
      [1.0, 'rgb(255,0,220)'],
    ],
  },
  clct: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Cloud cover',
    stops: [
      [0.0, 'rgb(255,255,255)'],
      [0.3, 'rgb(255,255,255)'],
      [0.6, 'rgb(255,255,255)'],
      [1.0, 'rgb(255,255,255)'],
    ],
  },
  wind_10m: {
    min: 0,
    max: 35,
    units: 'm/s',
    label: 'Wind Speed',
    stops: [
      [0.0, 'rgb(230,245,255)'],
      [0.1, 'rgb(170,220,250)'],
      [0.2, 'rgb(100,200,210)'],
      [0.35, 'rgb(80,210,120)'],
      [0.5, 'rgb(250,225,60)'],
      [0.65, 'rgb(250,140,40)'],
      [0.8, 'rgb(230,40,40)'],
      [1.0, 'rgb(160,20,150)'],
    ],
  },
};

export const MODELS = {
  ecmwf: {
    id: 'ecmwf',
    title: 'ECMWF IFS',
    badge: '0.25°',
    attribution: '© ECMWF IFS 0.25° (CC-BY-4.0)',
    defaultVar: ECMWF_DEFAULT_VAR,
    params: ECMWF_PARAMS,
    legends: ECMWF_LEGENDS,
    latestUrl: ECMWF_LATEST,
    minzoom: 3,
    maxzoom: 6,
    bbox: [94.0, -11.5, 141.5, 6.5],
  },
  gfs: {
    id: 'gfs',
    title: 'GFS',
    badge: '0.25°',
    attribution: '© NOAA GFS 0.25°',
    defaultVar: 'temperature',
    params: GFS_PARAMS,
    legends: GFS_LEGENDS,
    latestUrl: '/api/gfs/latest',
    minzoom: 0,
    maxzoom: 6,
    bbox: [95.0, -11.0, 141.0, 6.0],
  },
  icon: {
    id: 'icon',
    title: 'ICON',
    badge: '~13 km',
    attribution: '© DWD ICON',
    defaultVar: 't_2m',
    params: ICON_PARAMS,
    legends: ICON_LEGENDS,
    latestUrl: '/api/icon/manifest',
    minzoom: 4,
    maxzoom: 7,
    bbox: [88.0, -15.0, 148.0, 12.0],
  },
};

function isoToDir(iso) {
  return String(iso || '')
    .replace(/[-:TZ]/g, '')
    .slice(0, 10);
}

async function getJson(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${url} ${res.status}`);
  return await res.json();
}

export async function fetchLatest(modelId) {
  if (modelId === 'ecmwf') return fetchEcmwfLatest();
  if (modelId === 'gfs') {
    const latest = await getJson(MODELS.gfs.latestUrl);
    const runDir = isoToDir(latest.run);
    const manUrl = latest.manifest || `/api/gfs/runs/${runDir}/manifest.json`;
    try {
      const man = await getJson(manUrl);
      return { ...man, run: man.run || latest.run };
    } catch {
      return {
        ...latest,
        tile_url_template: '/tiles/gfs/{run}/{valid}/{variable}/{z}/{x}/{y}.webp',
        zoom_min: 0,
        zoom_max: 6,
        domain: { lat_min: -11, lat_max: 6, lon_min: 95, lon_max: 141 },
      };
    }
  }
  if (modelId === 'icon') return getJson(MODELS.icon.latestUrl);
  throw new Error(`unknown model ${modelId}`);
}

export function nearestStep(rows, now = Date.now()) {
  if (!rows?.length) return null;
  let best = rows[0];
  let bestAbs = Infinity;
  for (const row of rows) {
    const t = row.t ?? Date.parse(row.validTime);
    if (Number.isNaN(t)) continue;
    const abs = Math.abs(t - now);
    if (abs < bestAbs) {
      best = row;
      bestAbs = abs;
    }
  }
  return best;
}

function withTime(row) {
  const t = Date.parse(row.validTime);
  return Number.isNaN(t) ? null : { ...row, t };
}

export function listSteps(modelId, manifest, varId) {
  let rows = [];
  if (modelId === 'ecmwf') {
    rows = (manifest?.steps || [])
      .filter((s) => s.ready && s.valid_time)
      .map((s) =>
        withTime({
          step: s.step,
          validTime: s.valid_time,
          token: String(s.step),
        })
      );
  } else if (modelId === 'gfs') {
    rows = (manifest?.timesteps || [])
      .filter((s) => !s.error && s.valid)
      .map((s) =>
        withTime({
          step: s.forecast_hour,
          validTime: s.valid,
          token: isoToDir(s.valid),
        })
      );
  } else if (modelId === 'icon') {
    rows = (manifest?.timesteps || [])
      .filter((s) => {
        if (!s.valid_time) return false;
        if (varId && Array.isArray(s.params) && s.params.length) {
          return s.params.includes(varId);
        }
        return true;
      })
      .map((s) =>
        withTime({
          step: s.step,
          validTime: s.valid_time,
          token: s.step_str || String(s.step).padStart(3, '0'),
        })
      );
  }
  return rows.filter(Boolean).sort((a, b) => a.t - b.t);
}

export function pickStep(modelId, manifest, varId, now = Date.now()) {
  return nearestStep(listSteps(modelId, manifest, varId), now);
}

export function tileUrl(modelId, manifest, varId, step) {
  if (modelId === 'ecmwf') return ecmwfTileUrl(manifest, varId, step.step);
  if (modelId === 'gfs') {
    const run = isoToDir(manifest.run);
    const template =
      manifest.tile_url_template || '/tiles/gfs/{run}/{valid}/{variable}/{z}/{x}/{y}.webp';
    return template
      .replaceAll('{run}', run)
      .replaceAll('{valid}', step.token)
      .replaceAll('{variable}', String(varId));
  }
  if (modelId === 'icon') {
    const run = manifest.run_id;
    const template =
      manifest.tile_url_template || '/api/icon/tiles/{run}/{param}/{step}/{z}/{x}/{y}.webp';
    return template
      .replaceAll('{run}', run)
      .replaceAll('{param}', String(varId))
      .replaceAll('{step}', step.token);
  }
  return '';
}

export function sourceKey(modelId, manifest, varId, step) {
  if (modelId === 'ecmwf') return `ecmwf:${ecmwfSourceKey(manifest, varId, step.step)}`;
  if (modelId === 'gfs') return `gfs:${isoToDir(manifest.run)}:${varId}:${step.token}`;
  if (modelId === 'icon') return `icon:${manifest.run_id}:${varId}:${step.token}`;
  return `${modelId}:${varId}:${step?.token}`;
}

export function modelBbox(modelId, manifest) {
  const def = MODELS[modelId];
  if (modelId === 'ecmwf') return manifest?.bbox || def.bbox;
  if (modelId === 'gfs' && manifest?.domain) {
    const d = manifest.domain;
    return [d.lon_min, d.lat_min, d.lon_max, d.lat_max];
  }
  if (modelId === 'icon' && manifest?.domain?.bounds) {
    const [[latMin, lonMin], [latMax, lonMax]] = manifest.domain.bounds;
    return [lonMin, latMin, lonMax, latMax];
  }
  return def.bbox;
}

export function modelZoom(modelId, manifest) {
  const def = MODELS[modelId];
  if (modelId === 'ecmwf') {
    return {
      minzoom: manifest?.minzoom ?? def.minzoom,
      maxzoom: manifest?.maxzoom ?? def.maxzoom,
    };
  }
  if (modelId === 'gfs') {
    return {
      minzoom: manifest?.zoom_min ?? def.minzoom,
      maxzoom: manifest?.zoom_max ?? def.maxzoom,
    };
  }
  if (modelId === 'icon') {
    return {
      minzoom: manifest?.domain?.zoom_min ?? def.minzoom,
      maxzoom: manifest?.domain?.zoom_max ?? def.maxzoom,
    };
  }
  return { minzoom: def.minzoom, maxzoom: def.maxzoom };
}

export function modelRunTime(modelId, manifest) {
  if (modelId === 'ecmwf') return manifest.run_time;
  if (modelId === 'gfs') return manifest.run;
  if (modelId === 'icon') return manifest.run_time;
  return '';
}

export function modelRunId(modelId, manifest) {
  if (modelId === 'ecmwf') return manifest.run_id;
  if (modelId === 'gfs') return isoToDir(manifest.run);
  if (modelId === 'icon') return manifest.run_id;
  return '';
}

export function legendFor(modelId, varId) {
  return MODELS[modelId]?.legends?.[varId] || null;
}

export function legendCss(modelId, varId) {
  if (modelId === 'ecmwf') return ecmwfLegendCss(varId);
  const spec = legendFor(modelId, varId);
  if (!spec?.stops?.length) return 'transparent';
  return `linear-gradient(to right, ${spec.stops.map(([t, c]) => `${c} ${t * 100}%`).join(', ')})`;
}

export const WIND_PARAM = {
  ecmwf: 'wind10m',
  gfs: 'wind',
  icon: 'wind_10m',
};

export const WIND_UV = {
  ecmwf: ['u10', 'v10'],
  gfs: ['u10', 'v10'],
  icon: ['u_10m', 'v_10m'],
};

export function paramsFor(modelId) {
  return MODELS[modelId]?.params || ECMWF_PARAMS;
}

export function windParamId(modelId) {
  return WIND_PARAM[modelId] || null;
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

export function availableVars(modelId, manifest) {
  const ids = new Set();
  if (!manifest) return [];
  if (modelId === 'ecmwf') {
    // Catalog (`variables`) is the full param list, not baked tiles.
    for (const s of asList(manifest.steps)) {
      for (const v of asList(s.vars)) ids.add(v);
    }
  } else if (modelId === 'gfs') {
    for (const s of asList(manifest.timesteps)) {
      for (const k of Object.keys(s.tiles || {})) ids.add(k);
    }
  } else if (modelId === 'icon') {
    for (const s of asList(manifest.timesteps)) {
      for (const p of asList(s.params)) ids.add(p);
    }
  }
  const uv = WIND_UV[modelId];
  const windId = windParamId(modelId);
  if (windId && uv && uv.every((id) => ids.has(id))) ids.add(windId);
  return [...ids];
}

export function paramsAvailable(modelId, manifest) {
  const all = paramsFor(modelId);
  const ids = availableVars(modelId, manifest);
  const windId = windParamId(modelId);
  const uv = WIND_UV[modelId];
  const windReady =
    (windId && ids.includes(windId)) || (uv && uv.every((id) => ids.includes(id)));
  if (!ids.length) {
    return all.filter((p) => p.id === defaultVar(modelId));
  }
  const ready = all.filter((p) => ids.includes(p.id));
  if (windReady && windId && !ready.some((p) => p.id === windId)) {
    const wind = all.find((p) => p.id === windId);
    if (wind) ready.push(wind);
  }
  return ready.length ? ready : all.filter((p) => p.id === defaultVar(modelId));
}

export function defaultVar(modelId) {
  return MODELS[modelId]?.defaultVar || ECMWF_DEFAULT_VAR;
}
