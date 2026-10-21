export function windFromComponents(u, v) {
  if (![u, v].every(Number.isFinite)) return { speed: null, direction: null };
  const speed = Math.hypot(u, v);
  return { speed, direction: speed === 0 ? null : (270 - Math.atan2(v, u) * 180 / Math.PI + 360) % 360 };
}

export function parseGfsRainWindow(text) {
  const m = typeof text === 'string' && text.match(/^(\d+)\s*-\s*(\d+)\s*hours?(?:\s|$)/i);
  if (!m || +m[2] <= +m[1]) return null;
  return { start: +m[1], end: +m[2] };
}

/** No baseline, reset, or ambiguous window is ever filled with invented rain. */
export function normalizePrecipitationSeries(modelId, rows, runTime) {
  const run = Date.parse(runTime);
  return rows.map((p, i) => {
    let amount = null, start = null;
    const prev = rows[i - 1];
    const raw = p.rawRain;
    if (Number.isFinite(raw) && raw >= 0) {
      if (modelId === 'gfs') {
        const window = parseGfsRainWindow(p.rainStepRange);
        if (window && Number.isFinite(run) && run + window.end * 3600000 === p.t) {
          amount = raw;
          start = run + window.start * 3600000;
          const previousWindow = parseGfsRainWindow(prev?.rainStepRange);
          // Overlapping same-origin windows become disjoint increments only with a baseline.
          if (prev && start < prev.t) {
            if (previousWindow?.start === window.start && run + previousWindow.end * 3600000 === prev.t
              && Number.isFinite(prev.rawRain) && raw >= prev.rawRain) {
              amount = raw - prev.rawRain;
              start = prev.t;
            } else { amount = null; start = null; }
          }
        }
      } else if (prev && Number.isFinite(prev.rawRain) && prev.rawRain >= 0 && raw >= prev.rawRain && p.t > prev.t) {
        amount = raw - prev.rawRain;
        start = prev.t;
      }
    }
    return { ...p, precipitationMm: amount == null ? null : Math.round(amount * 10) / 10,
      precipitationIntervalHours: start == null ? null : (p.t - start) / 3600000,
      precipitationStartTime: start == null ? null : new Date(start).toISOString() };
  });
}
