import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchFloodMetadata, fetchFloodPoint, floodTileUrl, pointContent, REQUIRED_FLOOD_DISCLAIMER } from './flood.js';

test('floodTileUrl constructs correct indicator query and encoded path', () => {
  const meta = { publication_id: 'pub_20261018_00', run_id: 'ecmwf_20261018' };
  const url1 = floodTileUrl(meta, 24, 'rainfall');
  assert.equal(url1, '/api/flood/forecast/tile/pub_20261018_00/24/{z}/{x}/{y}.webp?indicator=rainfall');

  const url2 = floodTileUrl(meta, '36', 'hazard');
  assert.equal(url2, '/api/flood/forecast/tile/pub_20261018_00/36/{z}/{x}/{y}.webp?indicator=hazard');

  const url3 = floodTileUrl(meta, 24, 'invalid_name');
  assert.equal(url3, '/api/flood/forecast/tile/pub_20261018_00/24/{z}/{x}/{y}.webp?indicator=rainfall');
});

test('pointContent uses textContent safely and includes exact disclaimer', () => {
  const previous = globalThis.document;
  globalThis.document = { createElement: () => ({ style: {}, children: [], textContent: '' }) };
  try {
  const sample = {
    status: 'ready',
    window_start: '2026-10-17T00:00:00Z',
    window_end: '2026-10-18T00:00:00Z',
    rainfall_p24_mm: 45.2,
    antecedent_7d_mm: 120.4,
    ar7_weighted_mm: null,
    hazard_index: 0.752,
    vulnerability_index: 0.618,
    bayuadji_model: { status: 'NOT_CONFIGURED', probability: null }
  };
  const el = pointContent(sample);
  assert.equal(el.children.length, 0);
  assert.ok(el.textContent.includes(REQUIRED_FLOOD_DISCLAIMER));
  assert.ok(el.textContent.includes('NOT_CONFIGURED'));
  assert.ok(el.textContent.includes('null (nonaktif)'));
  } finally { globalThis.document = previous; }
});

test('fetch helpers pin publication and forward cancellation signal', async () => {
  const previous = globalThis.fetch;
  const request = new AbortController();
  let requested;
  globalThis.fetch = async (url, options) => {
    requested = url;
    assert.equal(options.signal, request.signal);
    assert.equal(options.cache, 'no-store');
    return { ok: true, json: async () => ({}) };
  };
  try {
    await fetchFloodPoint({ publication_id: '20261018T00-aaaaaaaaaaaaaaaa' }, 24, -6, 107, request.signal);
    assert.match(requested, /run=20261018T00-aaaaaaaaaaaaaaaa/);
    assert.match(requested, /step=24/);
    await assert.rejects(fetchFloodMetadata(request.signal), /Metadata banjir tidak valid/);
  } finally { globalThis.fetch = previous; }
});
