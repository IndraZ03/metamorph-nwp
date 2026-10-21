import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSpartanFrames, parseSpartanDate, verifySpartan, findLatestValidSpartanStart } from './src/services/spartan.js';

test('seven daily intervals cross year with explicit midnight WIB', () => {
  const frames = buildSpartanFrames(parseSpartanDate('202612290000'));
  assert.equal(frames.length, 7);
  assert.equal(frames[0].startDate, '202612290000');
  assert.equal(frames[6].endDate, '202701050000');
  assert.equal(new Date(frames[0].t).toISOString(), '2026-12-28T17:00:00.000Z');
  frames.forEach((frame, i) => {
    assert.match(frame.startDate, /^\d{8}0000$/);
    if (i) assert.equal(frame.t - frames[i - 1].t, 86400000);
    assert.equal(frame.endDate, buildSpartanFrames(parseSpartanDate(frame.startDate))[1].startDate);
  });
});
test('daily frames cross leap day and month', () => {
  const frames = buildSpartanFrames(parseSpartanDate('202402280000'));
  assert.equal(frames[1].startDate, '202402290000');
  assert.equal(frames[2].startDate, '202403010000');
});
test('discovery verifies selected product and daily interval; no fallback success', async () => {
  const original = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => { urls.push(url); return { ok: false }; };
  try {
    assert.equal(await findLatestValidSpartanStart('isi', 2), null);
    assert.equal(urls.length, 2);
    assert.ok(urls.every((url) => url.includes('product=isi')));
  } finally { globalThis.fetch = original; }
});
test('verification forwards cancellation signal and rejects aborted request', async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  controller.abort();
  globalThis.fetch = async (_url, options) => { assert.equal(options.signal, controller.signal); throw new Error('aborted'); };
  try { assert.equal(await verifySpartan({ product: 'fwi', start: '202601010000', end: '202601020000', signal: controller.signal }), false); }
  finally { globalThis.fetch = original; }
});
