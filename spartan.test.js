import test from 'node:test';
import assert from 'node:assert/strict';
import { SPARTAN_PRODUCTS, buildSpartanFrames, parseSpartanDate, spartanTileTemplate, verifySpartan, findLatestValidSpartanStart } from './src/services/spartan.js';

test('eight forecast dates keep one run across year with midnight WIB timestamps', () => {
  const frames = buildSpartanFrames(parseSpartanDate('202612290000'));
  assert.equal(frames.length, 8);
  assert.equal(frames[0].endDate, '202612290000');
  assert.equal(frames[7].endDate, '202701050000');
  assert.equal(new Date(frames[0].t).toISOString(), '2026-12-28T17:00:00.000Z');
  assert.equal(new Date(frames[7].t).toISOString(), '2027-01-04T17:00:00.000Z');
  assert.equal(new Set(frames.map((frame) => frame.token)).size, 8);
  frames.forEach((frame, i) => {
    assert.equal(frame.startDate, '202612290000');
    assert.equal(frame.token, frame.endDate);
    assert.equal(frame.leadDay, i);
    assert.ok(!frame.label.includes('–'));
    if (i) assert.equal(frame.t - frames[i - 1].t, 86400000);
  });
});
test('valid dates cross leap day and month without changing run', () => {
  const frames = buildSpartanFrames(parseSpartanDate('202402280000'));
  assert.equal(frames[1].endDate, '202402290000');
  assert.equal(frames[2].endDate, '202403010000');
  assert.ok(frames.every((frame) => frame.startDate === '202402280000'));
});

test('user URL regression: run 21 October serves valid 26 and 28 October', () => {
  const frames = buildSpartanFrames(parseSpartanDate('202610210000'));
  for (const [index, valid] of [[5, '202610260000'], [7, '202610280000']]) {
    const frame = frames[index];
    assert.equal(frame.startDate, '202610210000');
    assert.equal(frame.endDate, valid);
    const url = spartanTileTemplate({ product: 'fwi', start: frame.startDate, end: frame.endDate })
      .replace('{z}', '7').replace('{x}', '104').replace('{y}', '64');
    assert.equal(url, `/api/proxy-spartan-tile/7/104/64.png?product=fwi&start=202610210000&end=${valid}`);
  }
});

for (const { id: product } of SPARTAN_PRODUCTS) {
  test(`${product} navigation verifies every valid date against the same run`, async (t) => {
    const fetch = t.mock.method(globalThis, 'fetch', async (url) => {
      const params = new URL(url, 'https://example.test').searchParams;
      return response(params.get('product') === product && params.get('start') === '202610210000' ? 200 : 404);
    });
    const frames = buildSpartanFrames(parseSpartanDate('202610210000'));
    for (const frame of frames) {
      assert.equal(await verifySpartan({ product, start: frame.startDate, end: frame.endDate }), true);
    }
    assert.deepEqual(fetch.mock.calls.map(({ arguments: [url] }) =>
      new URL(url, 'https://example.test').searchParams.get('end')),
    ['202610210000', '202610220000', '202610230000', '202610240000',
      '202610250000', '202610260000', '202610270000', '202610280000']);
  });
}
const selection = { product: 'fwi', start: '202601010000', end: '202601020000' };
const response = (status) => ({ status, ok: status >= 200 && status < 300 });
const freezeWIB = (t, now = '2026-12-31T18:00:00Z') => {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: Date.parse(now) });
};

test('discovery starts today WIB, not UTC yesterday, and bypasses cache', async (t) => {
  freezeWIB(t);
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(200));
  const start = await findLatestValidSpartanStart('isi');
  assert.equal(start.getFullYear(), 2027);
  assert.equal(start.getMonth(), 0);
  assert.equal(start.getDate(), 1);
  assert.equal(fetch.mock.callCount(), 1);
  const [url, options] = fetch.mock.calls[0].arguments;
  assert.match(url, /product=isi&start=202701010000&end=202701010000$/);
  assert.equal(options.cache, 'no-store');
});

test('discovery uses previous WIB date before Jakarta midnight', async (t) => {
  freezeWIB(t, '2026-12-31T16:59:59Z');
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(200));
  await findLatestValidSpartanStart();
  assert.match(fetch.mock.calls[0].arguments[0], /start=202612310000&end=202612310000$/);
});

test('404 falls back one run with selected product and lead zero', async (t) => {
  freezeWIB(t);
  let calls = 0;
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(++calls === 1 ? 404 : 200));
  const start = await findLatestValidSpartanStart('isi');
  assert.equal(start.getDate(), 31);
  assert.equal(start.getMonth(), 11);
  assert.equal(fetch.mock.callCount(), 2);
  assert.match(fetch.mock.calls[1].arguments[0], /product=isi&start=202612310000&end=202612310000$/);
  assert.ok(fetch.mock.calls.every(({ arguments: [, options] }) => options.cache === 'no-store'));
});

test('all 404 returns null after exactly five default candidates including today', async (t) => {
  freezeWIB(t);
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(404));
  assert.equal(await findLatestValidSpartanStart(), null);
  assert.equal(fetch.mock.callCount(), 5);
  assert.deepEqual(fetch.mock.calls.map(({ arguments: [url] }) => new URL(url, 'https://example.test').searchParams.get('start')),
    ['202701010000', '202612310000', '202612300000', '202612290000', '202612280000']);
});

test('explicit candidate count remains supported', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(404));
  assert.equal(await findLatestValidSpartanStart('isi', 2), null);
  assert.equal(fetch.mock.callCount(), 2);
});

for (const status of [500, 503, 429, 403]) {
  test(`HTTP ${status} rejects discovery without falling back`, async (t) => {
    const fetch = t.mock.method(globalThis, 'fetch', async () => response(status));
    await assert.rejects(findLatestValidSpartanStart(), new RegExp(`HTTP ${status}`));
    assert.equal(fetch.mock.callCount(), 1);
  });
}

test('network failure rejects discovery unchanged without falling back', async (t) => {
  const error = new TypeError('Failed to fetch');
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw error; });
  await assert.rejects(findLatestValidSpartanStart(), (caught) => caught === error);
  assert.equal(fetch.mock.callCount(), 1);
});

test('pre-aborted verification and discovery reject without fetching', async (t) => {
  const controller = new AbortController();
  controller.abort();
  const fetch = t.mock.method(globalThis, 'fetch', async () => response(200));
  await assert.rejects(verifySpartan({ ...selection, signal: controller.signal }), (error) => error === controller.signal.reason);
  await assert.rejects(findLatestValidSpartanStart('fwi', 5, controller.signal), (error) => error === controller.signal.reason);
  assert.equal(fetch.mock.callCount(), 0);
});

test('in-flight abort propagates reason and removes caller listener', async (t) => {
  const controller = new AbortController();
  const remove = t.mock.method(controller.signal, 'removeEventListener');
  const fetch = t.mock.method(globalThis, 'fetch', (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  }));
  const pending = findLatestValidSpartanStart('fwi', 5, controller.signal);
  controller.abort();
  await assert.rejects(pending, (error) => error === controller.signal.reason);
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(remove.mock.callCount(), 1);
});

test('hung request times out after ten seconds without fallback', async (t) => {
  freezeWIB(t);
  const fetch = t.mock.method(globalThis, 'fetch', (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  }));
  const pending = findLatestValidSpartanStart();
  const rejected = assert.rejects(pending, { name: 'TimeoutError' });
  const signal = fetch.mock.calls[0].arguments[1].signal;
  t.mock.timers.tick(9999);
  assert.equal(signal.aborted, false);
  t.mock.timers.tick(1);
  await rejected;
  assert.equal(fetch.mock.callCount(), 1);
});

test('status checks cancel response body and clean timer and abort listener', async (t) => {
  freezeWIB(t);
  const controller = new AbortController();
  const remove = t.mock.method(controller.signal, 'removeEventListener');
  let cancelled = 0;
  const fetch = t.mock.method(globalThis, 'fetch', async () => ({
    ...response(200), body: { cancel: async () => { cancelled++; } },
  }));
  assert.equal(await verifySpartan({ ...selection, signal: controller.signal }), true);
  assert.equal(cancelled, 1);
  assert.equal(remove.mock.callCount(), 1);
  const signal = fetch.mock.calls[0].arguments[1].signal;
  t.mock.timers.tick(10000);
  controller.abort();
  assert.equal(signal.aborted, false);
});

test('body cancellation rejection does not change available status', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => ({
    ...response(200), body: { cancel: async () => { throw new Error('already closed'); } },
  }));
  assert.equal(await verifySpartan(selection), true);
});
