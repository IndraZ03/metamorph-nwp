import test from 'node:test';
import assert from 'node:assert/strict';
import { satelliteFrames, verifySatellite, findLatestValidBaserun } from './src/services/bmkg.js';
const product = { url: 'https://satellite.bmkg.go.id/api22/tile/{z}/{x}/{y}.png?param=IR&baserun={baserun}' };
test('UTC tokens retained; frames sorted, invalid and duplicate tokens removed across midnight WIB', () => {
  const tokens = ['2026-12-31T17:00:00Z', 'invalid', '2026-12-31T16:50:00Z', '2026-12-31T17:00:00Z', '2026-12-31T17:00:00+07:00'];
  const frames = satelliteFrames(tokens);
  assert.equal(frames.length, 2);
  assert.equal(frames[0].token, tokens[2]);
  assert.equal(frames[1].t, Date.parse(tokens[0]));
  assert.equal(new Date(frames[1].t + 7 * 3600000).toISOString(), '2027-01-01T00:00:00.000Z');
  assert.deepEqual(satelliteFrames(), []);
});
test('verification uses selected template, exact UTC token and cancellation signal', async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  globalThis.fetch = async (url, options) => {
    assert.match(url, /^\/api\/proxy-satellite-tile\/4\/13\/7.png\?param=IR/);
    assert.ok(url.includes(encodeURIComponent('2026-01-01T00:00:00Z')));
    assert.equal(options.signal, controller.signal);
    return { ok: true };
  };
  try { assert.equal(await verifySatellite(product, '2026-01-01T00:00:00Z', controller.signal), true); }
  finally { globalThis.fetch = original; }
});
test('discovery includes only verified frames; all failures reject without fallback', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => ({ ok: ++calls === 3 });
  try {
    const result = await findLatestValidBaserun(product);
    assert.equal(result.list.length, 1);
    assert.equal(result.current, result.list[0]);
    globalThis.fetch = async () => ({ ok: false });
    await assert.rejects(findLatestValidBaserun(product), /tidak tersedia/);
    await assert.rejects(findLatestValidBaserun({}), /tidak tersedia/);
  } finally { globalThis.fetch = original; }
});
test('aborted verification and discovery reject without fallback', async () => {
  const controller = new AbortController(); controller.abort();
  await assert.rejects(verifySatellite(product, '2026-01-01T00:00:00Z', controller.signal), { name: 'AbortError' });
  await assert.rejects(findLatestValidBaserun(product, controller.signal), { name: 'AbortError' });
});
