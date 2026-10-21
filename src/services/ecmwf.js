export const ECMWF_LATEST = '/ecmwf/latest.json';
export const ECMWF_POLL_MS = 5 * 60 * 1000;
export const ECMWF_DEFAULT_VAR = 't2m';

export const GLOBAL_MODELS = ['ecmwf'];

export const ECMWF_PARAMS = [
  { id: 't2m', label: 'Temperature', short: 'Temp', units: '°C' },
  { id: 'wind10m', label: 'Wind Speed', short: 'Wind', units: 'm/s' },
  { id: 'rh', label: 'Relative Humidity', short: 'RH', units: '%' },
  { id: 'tp', label: 'Rain accumulation', short: 'Rain', units: 'mm' },
  { id: 'msl', label: 'Pressure', short: 'P', units: 'hPa' },
  { id: 'd2m', label: 'Dew Point', short: 'Td', units: '°C' },
  { id: 'cape', label: 'CAPE', short: 'CAPE', units: 'J/kg' },
  { id: 'tcc', label: 'Clouds', short: 'Cloud', units: '' },
];

/** Stops must match engine/colormaps.py (t 0..1, rgb). */
export const ECMWF_LEGENDS = {
  wind10m: {
    min: 0,
    max: 30,
    units: 'm/s',
    label: 'Wind Speed',
    log: false,
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
  t2m: {
    min: -5,
    max: 35,
    units: '°C',
    label: 'Temperature',
    log: false,
    stops: [
      [0.0, 'rgb(49,54,149)'],
      [0.2, 'rgb(69,117,180)'],
      [0.4, 'rgb(171,217,233)'],
      [0.5, 'rgb(255,255,191)'],
      [0.65, 'rgb(253,174,97)'],
      [0.8, 'rgb(215,48,39)'],
      [1.0, 'rgb(165,0,38)'],
    ],
  },
  d2m: {
    min: 0,
    max: 28,
    units: '°C',
    label: 'Dew Point',
    log: false,
    stops: [
      [0.0, 'rgb(49,54,149)'],
      [0.2, 'rgb(69,117,180)'],
      [0.4, 'rgb(171,217,233)'],
      [0.5, 'rgb(255,255,191)'],
      [0.65, 'rgb(253,174,97)'],
      [0.8, 'rgb(215,48,39)'],
      [1.0, 'rgb(165,0,38)'],
    ],
  },
  rh: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Relative Humidity',
    log: false,
    stops: [
      [0.0, 'rgb(255,255,229)'],
      [0.3, 'rgb(194,230,153)'],
      [0.55, 'rgb(120,198,121)'],
      [0.75, 'rgb(49,163,84)'],
      [1.0, 'rgb(0,104,55)'],
    ],
  },
  msl: {
    min: 990,
    max: 1030,
    units: 'hPa',
    label: 'Pressure',
    log: false,
    stops: [
      [0.0, 'rgb(178,24,43)'],
      [0.35, 'rgb(239,138,98)'],
      [0.5, 'rgb(247,247,247)'],
      [0.65, 'rgb(103,169,207)'],
      [1.0, 'rgb(33,102,172)'],
    ],
  },
  tp: {
    min: 0.1,
    max: 300,
    units: 'mm',
    label: 'Rain accumulation',
    log: true,
    ticks: ['0.1', '1', '10', '50', '300'],
    stops: [
      [0.0, 'rgb(199,233,192)'],
      [0.15, 'rgb(161,217,155)'],
      [0.3, 'rgb(65,171,93)'],
      [0.5, 'rgb(8,104,172)'],
      [0.7, 'rgb(8,64,129)'],
      [0.85, 'rgb(136,65,157)'],
      [1.0, 'rgb(197,27,125)'],
    ],
  },
  cape: {
    min: 50,
    max: 4000,
    units: 'J/kg',
    label: 'CAPE',
    log: false,
    stops: [
      [0.0, 'rgb(255,255,204)'],
      [0.2, 'rgb(255,237,160)'],
      [0.4, 'rgb(254,178,76)'],
      [0.6, 'rgb(253,141,60)'],
      [0.8, 'rgb(227,26,28)'],
      [1.0, 'rgb(128,0,38)'],
    ],
  },
  tcc: {
    min: 0,
    max: 100,
    units: '%',
    label: 'Cloud cover',
    log: false,
    stops: [
      [0.0, 'rgb(255,255,255)'],
      [0.15, 'rgb(230,230,230)'],
      [0.4, 'rgb(189,189,189)'],
      [0.7, 'rgb(150,150,150)'],
      [1.0, 'rgb(99,99,99)'],
    ],
  },
};

export function legendCss(varId) {
  const spec = ECMWF_LEGENDS[varId];
  if (!spec) return 'transparent';
  return `linear-gradient(to right, ${spec.stops.map(([t, c]) => `${c} ${t * 100}%`).join(', ')})`;
}

export async function fetchLatest() {
  const res = await fetch(ECMWF_LATEST, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`ECMWF latest.json ${res.status}`);
  }
  return await res.json();
}

export function pickStep(manifest, now = Date.now()) {
  const ready = (manifest?.steps || []).filter((s) => s.ready);
  if (!ready.length) return null;

  let best = ready[0];
  let bestAbs = Infinity;
  for (const step of ready) {
    const t = Date.parse(step.valid_time);
    if (Number.isNaN(t)) continue;
    const abs = Math.abs(t - now);
    if (abs < bestAbs) {
      best = step;
      bestAbs = abs;
    }
  }
  return best;
}

export function tileUrl(manifest, varId, step) {
  const template = manifest.tiles || '/ecmwf/runs/{run_id}/{var}/{step}/{z}/{x}/{y}.webp';
  return template
    .replaceAll('{run_id}', manifest.run_id)
    .replaceAll('{var}', String(varId))
    .replaceAll('{step}', String(step));
}

export function sourceKey(manifest, varId, step) {
  return `${manifest.run_id}:${varId}:${step}`;
}
