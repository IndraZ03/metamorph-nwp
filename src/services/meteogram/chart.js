const ink = '#a1adbd';
const gridColor = '#343d47';
export const METEOGRAM_COLORS = ['#D56354', '#278DC0'];

export function nearestPoint(points, time) {
  if (!Number.isFinite(time) || !points.length) return null;
  return points.reduce((best, p) => Math.abs(p.t - time) < Math.abs(best.t - time) ? p : best);
}

function tick(value) {
  const date = new Date(Number(value) + 7 * 3600000);
  return `${String(date.getUTCHours()).padStart(2, '0')}:00\n${date.getUTCDate()}/${date.getUTCMonth() + 1}`;
}

/** Time-axis geometry preserves gaps and actual precipitation accumulation windows. */
export function buildMeteogramOptions(points, tab = 'overview') {
  const line = (name, field, color, index = 0, dashed = false) => ({
    name, type: 'line', xAxisIndex: index, yAxisIndex: index,
    data: points.map(p => [p.t, Number.isFinite(p[field]) ? p[field] : null]),
    connectNulls: false, smooth: false, showSymbol: true, symbolSize: 8,
    itemStyle: { color, borderWidth: 2, borderColor: '#13171c' },
    lineStyle: { color, width: 2, type: dashed ? 'dashed' : 'solid' },
    ...(field === 'temperatureC' ? { areaStyle: { color, opacity: 0.08 } } : {}),
  });
  const rain = {
    name: 'Hujan interval (mm)', type: 'custom', yAxisIndex: tab === 'overview' ? 1 : 0,
    dimensions: ['start', 'end', 'amount'], encode: { x: [0, 1], y: 2 },
    data: points.filter(p => Number.isFinite(p.precipitationMm) && p.precipitationStartTime)
      .map(p => [Date.parse(p.precipitationStartTime), p.t, p.precipitationMm]),
    renderItem(params, api) {
      const start = api.coord([api.value(0), 0]);
      const end = api.coord([api.value(1), api.value(2)]);
      const bounds = params.coordSys;
      const x = Math.max(start[0] + 1, bounds.x);
      const right = Math.min(end[0] - 1, bounds.x + bounds.width);
      const y = Math.max(end[1], bounds.y);
      return right > x ? { type: 'rect', shape: {
        x, y, width: right - x, height: Math.max(0, Math.min(start[1], bounds.y + bounds.height) - y),
      }, style: { fill: '#278DC0', opacity: 0.8 } } : null;
    },
    itemStyle: { color: '#278DC0' },
  };
  let series;
  let units;
  if (tab === 'temperature') {
    series = [line('Suhu 2m (°C)', 'temperatureC', '#D56354'), line('Titik embun (°C)', 'dewPointC', '#278DC0', 0, true)];
    units = ['°C'];
  } else if (tab === 'precipitation') { series = [rain]; units = ['mm interval']; }
  else if (tab === 'wind') { series = [line('Angin (m/s)', 'windSpeedMs', '#278DC0')]; units = ['m/s']; }
  else if (tab === 'atmosphere') {
    // Unlike overview's explicitly requested dual axes, atmosphere uses separate plots.
    const rows = [
      ['Kelembapan (%)', 'relativeHumidityPct', '%'], ['Awan (%)', 'totalCloudCoverPct', '%'],
      ['Tekanan (hPa)', 'pressureHpa', 'hPa'], ['CAPE (J/kg)', 'capeJkg', 'J/kg'],
    ].filter(([, field]) => points.some(p => Number.isFinite(p[field])));
    series = rows.map(([name, field], i) => line(name, field, '#278DC0', i));
    units = rows.map(([, , unit]) => unit);
  } else {
    series = [rain, line('Suhu 2m (°C)', 'temperatureC', '#D56354')];
    units = ['°C', 'mm interval'];
  }
  const split = tab === 'atmosphere';
  const count = split ? Math.max(1, units.length) : 1;
  const times = points.flatMap(p => [p.t, Date.parse(p.precipitationStartTime)]).filter(Number.isFinite);
  const min = Math.min(...times), max = Math.max(...times);
  // Single sample gets display padding only, never invented forecast values.
  const pad = min === max ? 1800000 : 0;
  const grids = Array.from({ length: count }, (_, i) => ({
    left: 56, right: 72, top: 46 + i * 140, height: split ? 88 : undefined,
    ...(split ? {} : { bottom: 48 }),
  }));
  return {
    animation: false, backgroundColor: 'transparent',
    legend: { top: 2, left: 16, textStyle: { color: ink, fontSize: 11 }, selectedMode: false },
    grid: grids,
    xAxis: grids.map((_, i) => ({ type: 'time', gridIndex: i, min: min - pad, max: max + pad,
      axisLabel: { color: ink, fontSize: 10, formatter: tick, hideOverlap: true },
      axisLine: { lineStyle: { color: gridColor } }, splitLine: { show: false },
    })),
    yAxis: units.map((unit, i) => ({ type: 'value', name: unit,
      gridIndex: split ? i : 0, position: !split && i === 1 ? 'right' : 'left',
      scale: !unit.startsWith('mm'), ...(unit.startsWith('mm') ? { min: 0 } : {}),
      nameTextStyle: { color: ink }, axisLabel: { color: ink, fontSize: 10 },
      splitLine: { show: split || i === 0, lineStyle: { color: gridColor, opacity: 0.5 } },
    })),
    series,
  };
}
