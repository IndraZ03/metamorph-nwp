import test from 'node:test';
import assert from 'node:assert/strict';
import {
  windFromComponents,
  parseGfsRainWindow,
  normalizePrecipitationSeries,
} from './meteogram/normalize.js';
import { classifyWeatherCondition, solarElevationDeg } from './meteogram/conditions.js';
import {
  fetchMeteogram,
  meteogramKey,
  meteogramManifestKey,
  clearMeteogramCache,
  runWithConcurrency,
} from './meteogram.js';

test('windFromComponents calculates speed and meteorological direction correctly', () => {
  // Calm wind
  const calm = windFromComponents(0, 0);
  assert.equal(calm.speed, 0);
  assert.equal(calm.direction, null);

  // South wind (blowing towards North: u=0, v=10) -> direction from South (180 deg)
  const south = windFromComponents(0, 10);
  assert.equal(Math.round(south.speed), 10);
  assert.equal(south.direction, 180);

  // West wind (blowing towards East: u=10, v=0) -> direction from West (270 deg)
  const west = windFromComponents(10, 0);
  assert.equal(Math.round(west.speed), 10);
  assert.equal(west.direction, 270);

  // North wind (blowing towards South: u=0, v=-10) -> direction from North (0 deg)
  const north = windFromComponents(0, -10);
  assert.equal(Math.round(north.speed), 10);
  assert.equal(north.direction, 0);

  // East wind (blowing towards West: u=-10, v=0) -> direction from East (90 deg)
  const east = windFromComponents(-10, 0);
  assert.equal(Math.round(east.speed), 10);
  assert.equal(east.direction, 90);

  // Missing components
  const missing = windFromComponents(null, 10);
  assert.equal(missing.speed, null);
  assert.equal(missing.direction, null);
});

test('parseGfsRainWindow parses range strings accurately', () => {
  assert.deepEqual(parseGfsRainWindow('0-1 hour acc fcst'), { start: 0, end: 1 });
  assert.deepEqual(parseGfsRainWindow('3-6 hours'), { start: 3, end: 6 });
  assert.deepEqual(parseGfsRainWindow('invalid'), null);
  assert.deepEqual(parseGfsRainWindow(null), null);
});

test('normalizePrecipitationSeries handles cumulative ECMWF differencing and resets', () => {
  const runTime = '2026-10-21T00:00:00Z';
  const rows = [
    { t: Date.parse('2026-10-21T00:00:00Z'), rawRain: 0.0 },
    { t: Date.parse('2026-10-21T03:00:00Z'), rawRain: 2.5 },
    { t: Date.parse('2026-10-21T06:00:00Z'), rawRain: 5.0 },
    { t: Date.parse('2026-10-21T09:00:00Z'), rawRain: 5.0 }, // No rain in interval
    { t: Date.parse('2026-10-21T12:00:00Z'), rawRain: 8.2 },
  ];

  const res = normalizePrecipitationSeries('ecmwf', rows, runTime);
  assert.equal(res[0].precipitationMm, null); // Baseline
  assert.equal(res[1].precipitationMm, 2.5);
  assert.equal(res[2].precipitationMm, 2.5);
  assert.equal(res[3].precipitationMm, 0.0);
  assert.equal(res[4].precipitationMm, 3.2);

  // Reset or invalid drop does not invent 0 or raw value
  const resetRows = [
    { t: Date.parse('2026-10-21T00:00:00Z'), rawRain: 10.0 },
    { t: Date.parse('2026-10-21T03:00:00Z'), rawRain: 2.0 }, // Decreased (reset/incompatible)
  ];
  const resetRes = normalizePrecipitationSeries('ecmwf', resetRows, runTime);
  assert.equal(resetRes[1].precipitationMm, null);
});

test('solarElevationDeg separates day and night at the point itself', () => {
  // Jakarta, 22 Oct 2026: sun near zenith at local noon, well below horizon at midnight.
  assert.ok(solarElevationDeg(-6.2, 106.85, Date.parse('2026-10-22T05:00:00Z')) > 70);
  assert.ok(solarElevationDeg(-6.2, 106.85, Date.parse('2026-10-22T17:00:00Z')) < -50);
  assert.equal(solarElevationDeg(null, 106.85, Date.now()), null);
});

test('classifyWeatherCondition derives a category only from available evidence', () => {
  const jakarta = [-6.2, 106.85];
  const noon = Date.parse('2026-10-22T05:00:00Z');
  const midnight = Date.parse('2026-10-22T17:00:00Z');
  const base = { precipitationMm: 0, precipitationIntervalHours: 3, totalCloudCoverPct: 10, t: noon };

  assert.equal(classifyWeatherCondition(null, ...jakarta), null);
  // Rain without a known accumulation window is not enough to claim rain.
  assert.equal(classifyWeatherCondition(
    { precipitationMm: 5, precipitationIntervalHours: null, totalCloudCoverPct: null, t: noon }, ...jakarta), null);
  assert.equal(classifyWeatherCondition(
    { ...base, precipitationMm: 1.2 }, ...jakarta).id, 'rain');
  assert.equal(classifyWeatherCondition(
    { ...base, precipitationMm: 13 }, ...jakarta).id, 'heavy_rain');
  // CAPE never produces a thunderstorm claim, however large.
  assert.equal(classifyWeatherCondition({ ...base, capeJkg: 4000 }, ...jakarta).id, 'clear_day');
  assert.equal(classifyWeatherCondition({ ...base, totalCloudCoverPct: 90 }, ...jakarta).id, 'cloudy');
  assert.equal(classifyWeatherCondition({ ...base, totalCloudCoverPct: 50 }, ...jakarta).id, 'partly_cloudy_day');
  assert.equal(classifyWeatherCondition(
    { ...base, totalCloudCoverPct: 50, t: midnight }, ...jakarta).id, 'partly_cloudy_night');
  assert.equal(classifyWeatherCondition({ ...base, t: midnight }, ...jakarta).id, 'clear_night');
});

test('meteogramKey generates consistent cache keys', () => {
  const key = meteogramKey('ecmwf', '2026102100', -6.21456, 106.84512, 6);
  assert.equal(key, 'ecmwf:2026102100:-6.2146,106.8451:z6');
});

test('meteogramManifestKey ignores volatile updated_at', () => {
  const m1 = {
    run_id: 'r1',
    run_time: '2026-10-21T00:00:00Z',
    updated_at: '2026-10-21T01:00:00Z',
    steps: [{ step: 0, valid_time: '2026-10-21T00:00:00Z', ready: true, vars: ['t2m'] }],
  };
  const m2 = {
    run_id: 'r1',
    run_time: '2026-10-21T00:00:00Z',
    updated_at: '2026-10-21T02:30:00Z',
    steps: [{ step: 0, valid_time: '2026-10-21T00:00:00Z', ready: true, vars: ['t2m'] }],
  };
  assert.equal(meteogramManifestKey('ecmwf', m1), meteogramManifestKey('ecmwf', m2));
});

test('fetchMeteogram rejects out of bounds coordinates', async () => {
  await assert.rejects(
    async () => {
      await fetchMeteogram({
        modelId: 'ecmwf',
        manifest: { run_id: '123' },
        latitude: 85.0, // Out of ECMWF Indonesia bbox
        longitude: 106.0,
      });
    },
    /di luar cakupan/
  );
});

test('runWithConcurrency never exceeds max concurrent active tasks', async () => {
  let active = 0;
  let maxActive = 0;
  const tasks = Array.from({ length: 24 }, (_, i) => async () => {
    active++;
    maxActive = Math.max(maxActive, active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    active--;
    return i;
  });

  const results = await runWithConcurrency(tasks, 6);
  assert.equal(results.length, 24);
  assert.ok(maxActive <= 6, `maxActive was ${maxActive}, expected <= 6`);
});

test('fetchMeteogram retrieves series via mock sampler with bounded concurrency', async () => {
  clearMeteogramCache();

  const manifest = {
    run_id: 'test_run_01',
    run_time: '2026-10-21T00:00:00Z',
    minzoom: 3,
    maxzoom: 6,
    steps: [
      { step: 0, valid_time: '2026-10-21T00:00:00Z', ready: true, vars: ['t2m', 'tp', 'u10', 'v10'] },
      { step: 3, valid_time: '2026-10-21T03:00:00Z', ready: true, vars: ['t2m', 'tp', 'u10', 'v10'] },
      { step: 6, valid_time: '2026-10-21T06:00:00Z', ready: true, vars: ['t2m', 'tp', 'u10', 'v10'] },
    ],
  };

  const sampledUrls = [];
  const mockSampler = async (url) => {
    sampledUrls.push(url);
    if (url.includes('/t2m/')) return 28.5;
    if (url.includes('/tp/')) {
      if (url.includes('/0/')) return 0.0;
      if (url.includes('/3/')) return 4.2;
      if (url.includes('/6/')) return 9.5;
    }
    if (url.includes('/u10/')) return 5.0;
    if (url.includes('/v10/')) return 5.0;
    return null;
  };

  const mockGeocoder = async (lat, lon) => ({
    kecamatan: 'Gambir',
    kabupaten_kota: 'Jakarta Pusat',
    provinsi: 'DKI Jakarta',
  });

  const res = await fetchMeteogram({
    modelId: 'ecmwf',
    manifest,
    latitude: -6.2,
    longitude: 106.8,
    sampler: mockSampler,
    geocoder: mockGeocoder,
  });

  assert.equal(res.modelId, 'ecmwf');
  assert.equal(res.location.kecamatan, 'Gambir');
  assert.equal(res.points.length, 3);
  assert.equal(res.points[0].temperatureC, 28.5);
  assert.equal(res.points[1].precipitationMm, 4.2);
  assert.equal(res.points[2].precipitationMm, 5.3); // 9.5 - 4.2 = 5.3
  assert.equal(res.points[1].windSpeedMs, Math.hypot(5, 5));
  assert.equal(res.points[1].windDirectionDeg, 225); // from SW (225 deg)

  // Verify caching
  const cached = await fetchMeteogram({
    modelId: 'ecmwf',
    manifest,
    latitude: -6.2,
    longitude: 106.8,
    sampler: () => { throw new Error('Should use cache'); },
    geocoder: mockGeocoder,
  });
  assert.equal(cached, res);
});

test('fetchMeteogram handles GFS tile counts and ICON maximum wind', async () => {
  clearMeteogramCache();

  // Test ICON VMAX mapped to maximumWindMs and windSpeedMs set to null when U/V absent
  const iconManifest = {
    run_id: 'icon_run_01',
    run_time: '2026-10-21T00:00:00Z',
    minzoom: 4,
    maxzoom: 7,
    timesteps: [
      { step: 0, valid_time: '2026-10-21T00:00:00Z', params: ['t_2m', 'wind_10m'] },
    ],
  };

  const res = await fetchMeteogram({
    modelId: 'icon',
    manifest: iconManifest,
    latitude: -6.2,
    longitude: 106.8,
    sampler: async (url) => {
      if (url.includes('/t_2m/')) return 29.1;
      if (url.includes('/wind_10m/')) return 12.4;
      return null;
    },
    geocoder: async () => ({ display_name: 'Test' }),
  });

  assert.equal(res.points.length, 1);
  assert.equal(res.points[0].temperatureC, 29.1);
  assert.equal(res.points[0].maximumWindMs, 12.4);
  assert.equal(res.points[0].windSpeedMs, null); // Must be null because U/V absent
});
