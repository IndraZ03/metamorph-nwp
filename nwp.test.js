import test from 'node:test';
import assert from 'node:assert/strict';
import { availableVars, listSteps, paramsAvailable } from './src/services/nwp.js';

const gfsManifest = {
  run: '2026-10-17T12:00:00Z',
  timesteps: [{ tiles: { temperature: 65, wind: 65 } }],
  variables: { temperature: { label: 'T' }, wind: { label: 'Wind' } },
};

const ecmwfManifest = {
  run_id: '20261016T18',
  variables: [{ id: 't2m' }, { id: 'rh' }],
  steps: [{ vars: ['t2m', 'rh', 'msl'] }],
};

test('availableVars does not throw when ECMWF reads a GFS-shaped variables object', () => {
  assert.deepEqual(availableVars('ecmwf', gfsManifest), []);
  assert.ok(availableVars('gfs', gfsManifest).includes('temperature'));
});

test('availableVars uses ECMWF step.vars, not the catalog', () => {
  const ids = availableVars('ecmwf', ecmwfManifest);
  assert.ok(ids.includes('t2m'));
  assert.ok(ids.includes('rh'));
  assert.ok(ids.includes('msl'));
  assert.ok(!ids.includes('wind10m'));
});

test('availableVars infers ECMWF wind from u10/v10 tiles', () => {
  const ids = availableVars('ecmwf', {
    steps: [{ vars: ['t2m', 'u10', 'v10'] }],
  });
  assert.ok(ids.includes('wind10m'));
});

test('paramsAvailable falls back to default var on stale or empty manifest', () => {
  const stale = paramsAvailable('ecmwf', gfsManifest).map((p) => p.id);
  assert.ok(stale.includes('t2m'));
  assert.ok(!stale.includes('wind10m'));
  assert.deepEqual(paramsAvailable('ecmwf', null).map((p) => p.id), ['t2m']);
});

test('paramsAvailable keeps ECMWF vars that are actually baked', () => {
  const ready = paramsAvailable('ecmwf', ecmwfManifest).map((p) => p.id);
  assert.ok(ready.includes('t2m'));
  assert.ok(ready.includes('rh'));
  assert.ok(!ready.includes('wind10m'));
});

test('paramsAvailable shows ECMWF wind only after tiles exist on a step', () => {
  const withWind = {
    run_id: '20261016T18',
    variables: [{ id: 't2m' }, { id: 'wind10m' }],
    steps: [{ vars: ['t2m', 'rh', 'wind10m', 'u10', 'v10'] }],
  };
  const ready = paramsAvailable('ecmwf', withWind).map((p) => p.id);
  assert.ok(ready.includes('t2m'));
  assert.ok(ready.includes('wind10m'));
  assert.ok(!ready.includes('u10'));
});

test('paramsAvailable always exposes Wind Speed for ICON like GFS', () => {
  const iconManifest = { timesteps: [{ params: ['t_2m', 'u_10m', 'v_10m'] }] };
  const icon = paramsAvailable('icon', iconManifest).map((p) => p.id);
  assert.ok(icon.includes('t_2m'));
  assert.ok(icon.includes('wind_10m'));
  const gfs = paramsAvailable('gfs', gfsManifest).map((p) => p.id);
  assert.ok(gfs.includes('wind'));
});

test('listSteps filters steps per requested varId across models', () => {
  const ecmwf = {
    steps: [
      { step: 0, valid_time: '2026-10-18T00:00:00Z', ready: true, vars: ['t2m'] },
      { step: 6, valid_time: '2026-10-18T06:00:00Z', ready: true, vars: ['rh'] },
      { step: 12, valid_time: '2026-10-18T12:00:00Z', ready: false, vars: ['t2m'] },
    ],
  };
  const ecmwfT = listSteps('ecmwf', ecmwf, 't2m');
  assert.deepEqual(ecmwfT.map((s) => s.step), [0]);

  const gfs = {
    timesteps: [
      { forecast_hour: 0, valid: '2026-10-18T00:00:00Z', params: ['temperature'] },
      { forecast_hour: 3, valid: '2026-10-18T03:00:00Z', params: ['wind'] },
      { forecast_hour: 6, valid: '2026-10-18T06:00:00Z', params: ['temperature'], error: 'fail' },
    ],
  };
  const gfsT = listSteps('gfs', gfs, 'temperature');
  assert.deepEqual(gfsT.map((s) => s.step), [0]);

  const icon = {
    timesteps: [
      { step: 0, valid_time: '2026-10-18T00:00:00Z', params: ['t_2m'] },
      { step: 1, valid_time: '2026-10-18T01:00:00Z', params: ['tot_prec'] },
    ],
  };
  const iconT = listSteps('icon', icon, 't_2m');
  assert.deepEqual(iconT.map((s) => s.step), [0]);
});
