/** P0 tool registry. Only implemented tools are listed — no fake buttons. */

export const TOOL_GROUPS = [
  { id: 'draw', label: 'Draw' },
  { id: 'measure', label: 'Measure' },
  { id: 'weather', label: 'Weather' },
  { id: 'edit', label: 'Edit' },
];

export const TOOLS = [
  { id: 'select', group: 'edit', label: 'Select', tip: 'Pilih dan geser objek', shortcut: 'V' },
  { id: 'point', group: 'draw', label: 'Point', tip: 'Penanda titik', shortcut: 'P' },
  { id: 'star', group: 'draw', label: 'Star', tip: 'Simbol bintang. Klik peta', shortcut: 'S' },
  { id: 'icon', group: 'draw', label: 'Icon', tip: 'Simbol atlas lokal' },
  { id: 'numbered', group: 'draw', label: 'No.', tip: 'Pin bernomor berurutan' },
  { id: 'coord', group: 'draw', label: 'Coord', tip: 'Pin koordinat lat/lon' },
  { id: 'text', group: 'draw', label: 'Text', tip: 'Anotasi teks', shortcut: 'T' },
  { id: 'callout', group: 'draw', label: 'Call', tip: 'Label dengan garis penunjuk. Klik target, lalu teks' },
  { id: 'freehand', group: 'draw', label: 'Pen', tip: 'Coretan bebas', shortcut: 'F' },
  { id: 'line', group: 'draw', label: 'Line', tip: 'Garis dua titik', shortcut: 'L' },
  { id: 'polyline', group: 'draw', label: 'Polyline', tip: 'Garis multi-titik. Klik ganda untuk selesai' },
  { id: 'arrow', group: 'draw', label: 'Arrow', tip: 'Garis berpanah' },
  { id: 'polygon', group: 'draw', label: 'Polygon', tip: 'Poligon. Klik titik pertama untuk nutup' },
  { id: 'rectangle', group: 'draw', label: 'Rect', tip: 'Persegi panjang' },
  { id: 'circle', group: 'draw', label: 'Circle', tip: 'Lingkaran geodesik' },
  { id: 'distance', group: 'measure', label: 'Dist', tip: 'Jarak dan true bearing' },
  { id: 'radius', group: 'measure', label: 'Radius', tip: 'Cincin radius' },
  { id: 'rings', group: 'measure', label: 'Rings', tip: 'Cincin konsentris 5/10/25/50/100 NM' },
  { id: 'sector', group: 'measure', label: 'Sector', tip: 'Juring bearing' },
  { id: 'area', group: 'measure', label: 'Area', tip: 'Luas dan keliling poligon' },
  { id: 'high', group: 'weather', label: 'High', tip: 'Simbol tekanan H. Analisis manual' },
  { id: 'low', group: 'weather', label: 'Low', tip: 'Simbol tekanan L. Analisis manual' },
  { id: 'wx', group: 'weather', label: 'Wx', tip: 'CB/TS, hujan, angin, waspada. Bukan observasi' },
];

export const POINT_CLICK_TOOLS = ['point', 'text', 'icon', 'numbered', 'coord', 'high', 'low', 'wx', 'star'];

export const TOOL_BY_ID = Object.fromEntries(TOOLS.map((t) => [t.id, t]));

export const STYLE_PRESETS = {
  normal: { stroke: '#38bdf8', fill: '#38bdf8', strokeWidth: 2, fillOpacity: 0.22 },
  focus: { stroke: '#f8fafc', fill: '#e2e8f0', strokeWidth: 2, fillOpacity: 0.18 },
  warning: { stroke: '#f59e0b', fill: '#f59e0b', strokeWidth: 2.5, fillOpacity: 0.2 },
  cb: { stroke: '#a78bfa', fill: '#a78bfa', strokeWidth: 2, fillOpacity: 0.22 },
  rain: { stroke: '#4ade80', fill: '#4ade80', strokeWidth: 2, fillOpacity: 0.22 },
  wind: { stroke: '#fb923c', fill: '#fb923c', strokeWidth: 2, fillOpacity: 0.18 },
  reference: { stroke: '#f472b6', fill: '#f472b6', strokeWidth: 2, fillOpacity: 0.16 },
};

export function defaultStyle(tool) {
  const base = { ...STYLE_PRESETS.normal, lineOpacity: 0.95, fontSize: 12, dashed: 0 };
  if (tool === 'distance' || tool === 'radius' || tool === 'rings' || tool === 'sector') {
    base.dashed = 1;
    base.fillOpacity = tool === 'sector' ? 0.16 : 0.08;
  }
  if (tool === 'star') {
    base.stroke = '#facc15';
    base.fill = '#facc15';
    base.fontSize = 16;
  }
  if (tool === 'text' || tool === 'callout') {
    base.stroke = '#f8fafc';
    base.fontSize = 13;
    base.halo = 1;
    base.align = 'center';
  }
  if (tool === 'high') {
    base.stroke = '#93c5fd';
    base.fill = '#93c5fd';
    base.fontSize = 20;
  }
  if (tool === 'low') {
    base.stroke = '#f87171';
    base.fill = '#f87171';
    base.fontSize = 20;
  }
  if (tool === 'wx') {
    base.stroke = '#a78bfa';
    base.fill = '#a78bfa';
  }
  if (tool === 'icon') {
    base.stroke = '#f8fafc';
    base.fill = '#f8fafc';
  }
  return base;
}

export function toolKind(tool) {
  if (POINT_CLICK_TOOLS.includes(tool)) return 'point';
  if (tool === 'polygon' || tool === 'rectangle' || tool === 'circle' || tool === 'area' || tool === 'sector') {
    return 'polygon';
  }
  return 'line';
}

export function nextNumber(features = []) {
  let max = 0;
  for (const f of features) {
    if (f.properties?.tool !== 'numbered') continue;
    const n = Number(f.properties.number);
    if (Number.isFinite(n) && n > max) max = n;
  }
  return max + 1;
}

export function nextName(features, tool) {
  const prefix = TOOL_BY_ID[tool]?.label || 'Objek';
  const n = features.filter((f) => f.properties.tool === tool).length + 1;
  return `${prefix} ${n}`;
}
