import test from 'node:test';
import assert from 'node:assert/strict';
import { WindField, DemoWindField, screenVelocity } from './src/services/windField.js';
import { WindOverlay } from './src/services/windAnimation.js';

const context = {
  modelId: 'icon', manifest: { run_id: '2026101706' }, step: { token: '000' },
  bbox: [100, -10, 120, 10], zoom: { minzoom: 4, maxzoom: 7 },
};

function overlay() {
  const layer = Object.create(WindOverlay.prototype);
  Object.assign(layer, {
    map: {}, ctx: { clearRect() {} }, canvas: { width: 800, height: 600 },
    initParticles() {}, onStatus(status) { this.status = status; },
  });
  return layer;
}

test('demo is explicitly separate from NWP and bounded', () => {
  const field = new DemoWindField();
  assert.ok(field.sample(110, -6).u < 0);
  assert.ok(field.sample(110, -6).v > 0);
  assert.equal(field.sample(0, 0), null);
});

test('numeric field loads paired model components and interpolates signed values', async () => {
  const field = new WindField(context, async url => new Float32Array(256 * 256).fill(url.includes('/u_10m/') ? -3 : 4));
  await field.load(new AbortController().signal);
  assert.deepEqual(field.sample(110, 0), { u: -3, v: 4 });
  assert.equal(field.sample(130, 0), null);
});

test('missing numeric data is not silently synthesized by model field', async () => {
  const field = new WindField(context, async () => { throw new Error('404'); });
  await assert.rejects(field.load(new AbortController().signal), /U\/V/);
});

test('projection sends positive U east and positive V north', () => {
  const map = { getZoom: () => 0, project: ([lon, lat]) => ({ x: lon * 512 / 360, y: -lat * 512 / 360 }) };
  const result = screenVelocity(map, 110, 0, { u: 3, v: 4 });
  assert.ok(Math.abs(result.x - 18) < 1e-8);
  assert.ok(Math.abs(result.y + 24) < 1e-8);
});

test('missing manifest immediately selects labeled demo', async () => {
  const layer = overlay();
  await layer.setContext({ modelId: 'ecmwf' });
  assert.ok(layer.field instanceof DemoWindField);
  assert.equal(layer.status.mode, 'demo');
});

test('failed data load keeps animation field and labels simulation', async () => {
  const original = WindField.prototype.load;
  WindField.prototype.load = async () => { throw new Error('404'); };
  try {
    const layer = overlay();
    await layer.setContext(context);
    assert.ok(layer.field instanceof DemoWindField);
    assert.equal(layer.status.mode, 'demo');
  } finally { WindField.prototype.load = original; }
});

test('failed context can retry; concurrent requests and ready model are reused', async () => {
  const original = WindField.prototype.load;
  let calls = 0;
  let finish;
  WindField.prototype.load = async () => {
    calls++;
    if (calls === 1) throw new Error('404');
    await new Promise(resolve => { finish = resolve; });
  };
  try {
    const layer = overlay();
    await layer.setContext(context);
    const pending = layer.setContext(context);
    await layer.setContext(context);
    assert.equal(calls, 2);
    finish();
    await pending;
    assert.equal(layer.mode, 'model');
    await layer.setContext(context);
    assert.equal(calls, 2);
    assert.equal(layer.loading, false);
  } finally { WindField.prototype.load = original; }
});

test('successful U/V loads switch to model; stale requests cannot overwrite new context', async () => {
  const original = WindField.prototype.load;
  let finish;
  WindField.prototype.load = () => new Promise(resolve => { finish = resolve; });
  try {
    const layer = overlay();
    const pending = layer.setContext(context);
    await layer.setContext({ modelId: 'ecmwf' });
    finish();
    await pending;
    assert.equal(layer.status.mode, 'demo');
    WindField.prototype.load = async () => {};
    await layer.setContext(context);
    assert.ok(layer.field instanceof WindField);
    assert.equal(layer.status.mode, 'model');
  } finally { WindField.prototype.load = original; }
});
