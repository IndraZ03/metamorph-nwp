import test from 'node:test';
import assert from 'node:assert/strict';
import { reconcileTimeline, timelineTime } from './forecastTimeline.js';

test('timelineTime extracts valid_time or computes from run_time + step', () => {
  assert.equal(timelineTime({ valid_time: '2026-10-18T12:00:00Z' }, '2026-10-18T00:00:00Z'), '2026-10-18T12:00:00Z');
  assert.equal(timelineTime({ step: 6 }, '2026-10-18T00:00:00Z'), '2026-10-18T06:00:00.000Z');
});

test('reconcileTimeline preserves valid time across different runs and sets notice', () => {
  const rows = [
    { step: 12, valid_time: '2026-10-18T12:00:00Z', ready: true },
    { step: 24, valid_time: '2026-10-19T00:00:00Z', ready: true },
  ];
  const anchor = { runTime: '2026-10-17T12:00:00Z', validTime: '2026-10-18T12:00:00Z' };
  const res = reconcileTimeline(rows, '2026-10-18T00:00:00Z', anchor);
  assert.equal(res.step, 12);
  assert.match(res.notice, /Run produk berbeda/);
});

test('reconcileTimeline falls back to available step when target missing and reports notice', () => {
  const rows = [
    { step: 24, valid_time: '2026-10-19T00:00:00Z', ready: true },
  ];
  const anchor = { runTime: '2026-10-18T00:00:00Z', validTime: '2026-10-18T06:00:00Z' };
  const res = reconcileTimeline(rows, '2026-10-18T00:00:00Z', anchor);
  assert.equal(res.step, 24);
  assert.match(res.notice, /Waktu sebelumnya tidak tersedia/);
});
