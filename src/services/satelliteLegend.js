// Palette resmi: https://satellite.bmkg.go.id/_nuxt/abbc6bd.js (EH / VS).
const palettes = {
  EH: [[-100,233,63,51],[-80,234,84,86],[-75,248,212,184],[-69,246,195,140],[-62,242,159,51],[-56,235,90,51],[-48,205,155,40],[-41,197,187,36],[-34,156,211,19],[-28,133,242,0],[-21,118,231,135],[-13,95,193,146],[-7,67,175,251],[0,73,135,251],[8,52,98,180],[14,14,72,130],[21,0,0,0],[60,0,0,0]],
  VS: [[1,250,250,250],[0.9,221,221,221],[0.8,201,201,201],[0.7,172,172,172],[0.6,149,149,149],[0.5,120,120,120],[0.4,88,88,88],[0.3,65,65,65],[0.2,33,33,33],[0.05,6,6,6]],
};

export function satelliteLegend(product) {
  const param = product?.param || ({ 'himawari9-ir': 'EH', 'himawari9-vs': 'VS' })[product?.id];
  const rows = palettes[param];
  if (!rows) return null;
  return { label: param === 'EH' ? 'Skala EH · BMKG' : 'Skala Visible · BMKG',
    stops: rows.map(([value, r, g, b]) => ({ value, color: `rgb(${r},${g},${b})` })) };
}
