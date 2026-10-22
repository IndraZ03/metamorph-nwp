const ink = '#a1adbd';
const gridColor = '#343d47';
export const METEOGRAM_COLORS = ['#D56354', '#278DC0', '#8AA0B4'];

export function nearestPoint(points, time) {
  if (!Number.isFinite(time) || !points.length) return null;
  return points.reduce((best, p) => Math.abs(p.t - time) < Math.abs(best.t - time) ? p : best);
}

function tick(value) {
  const date = new Date(Number(value) + 7 * 3600000);
  return `${String(date.getUTCHours()).padStart(2, '0')}:00\n${date.getUTCDate()}/${date.getUTCMonth() + 1}`;
}

const rainSeries = (points) => ({
  name: 'Hujan (mm interval)', type: 'custom', yAxisIndex: 1,
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
    }, style: { fill: '#278DC0', opacity: 0.75 } } : null;
  },
  itemStyle: { color: '#278DC0' },
});

/** One plot: temperature (left), interval rain (right), pressure (far right, dashed). */
export function buildMeteogramOptions(points) {
  const line = (name, field, color, yAxisIndex, dashed = false) => ({
    name, type: 'line', yAxisIndex,
    data: points.map(p => [p.t, Number.isFinite(p[field]) ? p[field] : null]),
    connectNulls: false, smooth: false, showSymbol: true, symbolSize: 7,
    itemStyle: { color, borderWidth: 2, borderColor: '#13171c' },
    lineStyle: { color, width: 2, type: dashed ? 'dashed' : 'solid' },
    ...(field === 'temperatureC' ? { areaStyle: { color, opacity: 0.08 } } : {}),
  });
  const series = [
    rainSeries(points),
    line('Suhu 2m (°C)', 'temperatureC', '#D56354', 0),
    line('Tekanan (hPa)', 'pressureHpa', '#8AA0B4', 2, true),
  ];
  const times = points.flatMap(p => [p.t, Date.parse(p.precipitationStartTime)]).filter(Number.isFinite);
  const min = Math.min(...times), max = Math.max(...times);
  // Single sample gets display padding only, never invented forecast values.
  const pad = min === max ? 1800000 : 0;
  const axis = (name, position, extra) => ({ type: 'value', name, position, scale: true,
    nameTextStyle: { color: ink, fontSize: 10 }, axisLabel: { color: ink, fontSize: 10 },
    splitLine: { show: position === 'left', lineStyle: { color: gridColor, opacity: 0.5 } },
    ...extra });
  return {
    animation: false, backgroundColor: 'transparent',
    legend: { top: 2, left: 16, textStyle: { color: ink, fontSize: 11 }, selectedMode: false },
    grid: { left: 52, right: 108, top: 52, bottom: 44 },
    xAxis: { type: 'time', min: min - pad, max: max + pad,
      axisLabel: { color: ink, fontSize: 10, formatter: tick, hideOverlap: true },
      axisLine: { lineStyle: { color: gridColor } }, splitLine: { show: false } },
    yAxis: [
      axis('°C', 'left', {}),
      axis('mm', 'right', { scale: false, min: 0, offset: 0 }),
      axis('hPa', 'right', { offset: 52 }),
    ],
    series,
  };
}
