/** Local analysis-symbol atlas. Canvas only — no per-marker network request. Not WMO/ICAO. */

export const ICON_ATLAS = [
  { id: 'pin', label: 'Pin' },
  { id: 'flag', label: 'Flag' },
  { id: 'xmark', label: 'X' },
  { id: 'plus', label: 'Plus' },
  { id: 'triangle', label: 'Tri' },
  { id: 'square', label: 'Sq' },
  { id: 'diamond', label: 'Dia' },
  { id: 'target', label: 'Tgt' },
];

export const WX_ATLAS = [
  { id: 'cb', label: 'CB/TS' },
  { id: 'rain', label: 'Hujan' },
  { id: 'wind', label: 'Angin' },
  { id: 'warn', label: 'Waspada' },
];

export const ICON_BY_ID = Object.fromEntries(ICON_ATLAS.map((x) => [x.id, x]));
export const WX_BY_ID = Object.fromEntries(WX_ATLAS.map((x) => [x.id, x]));

const SIZE = 64;

function renderShape(drawFn) {
  const canvas = document.createElement('canvas');
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, SIZE, SIZE);
  ctx.translate(SIZE / 2, SIZE / 2);
  ctx.strokeStyle = '#fff';
  ctx.fillStyle = '#fff';
  ctx.lineWidth = 3.2;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  drawFn(ctx);
  return ctx.getImageData(0, 0, SIZE, SIZE);
}

const DRAW = {
  star(ctx) {
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const ang = -Math.PI / 2 + (i * Math.PI) / 5;
      const r = i % 2 === 0 ? 20 : 8;
      const x = Math.cos(ang) * r;
      const y = Math.sin(ang) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
  },
  pin(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, 22);
    ctx.bezierCurveTo(-18, 4, -16, -18, 0, -18);
    ctx.bezierCurveTo(16, -18, 18, 4, 0, 22);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, -8, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#000';
    ctx.fill();
  },
  flag(ctx) {
    ctx.beginPath();
    ctx.moveTo(-14, 22);
    ctx.lineTo(-14, -20);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-14, -20);
    ctx.lineTo(16, -12);
    ctx.lineTo(-14, -4);
    ctx.closePath();
    ctx.fill();
  },
  xmark(ctx) {
    ctx.beginPath();
    ctx.moveTo(-14, -14);
    ctx.lineTo(14, 14);
    ctx.moveTo(14, -14);
    ctx.lineTo(-14, 14);
    ctx.stroke();
  },
  plus(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -16);
    ctx.lineTo(0, 16);
    ctx.moveTo(-16, 0);
    ctx.lineTo(16, 0);
    ctx.stroke();
  },
  triangle(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -18);
    ctx.lineTo(18, 16);
    ctx.lineTo(-18, 16);
    ctx.closePath();
    ctx.fill();
  },
  square(ctx) {
    ctx.fillRect(-13, -13, 26, 26);
  },
  diamond(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -18);
    ctx.lineTo(16, 0);
    ctx.lineTo(0, 18);
    ctx.lineTo(-16, 0);
    ctx.closePath();
    ctx.fill();
  },
  target(ctx) {
    ctx.beginPath();
    ctx.arc(0, 0, 16, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, -20);
    ctx.lineTo(0, 20);
    ctx.moveTo(-20, 0);
    ctx.lineTo(20, 0);
    ctx.stroke();
  },
  cb(ctx) {
    ctx.beginPath();
    ctx.arc(-8, 0, 10, 0, Math.PI * 2);
    ctx.arc(6, -2, 12, 0, Math.PI * 2);
    ctx.arc(14, 4, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(2, 8);
    ctx.lineTo(-4, 18);
    ctx.lineTo(4, 16);
    ctx.lineTo(-2, 24);
    ctx.stroke();
  },
  rain(ctx) {
    ctx.beginPath();
    ctx.arc(-6, -6, 9, 0, Math.PI * 2);
    ctx.arc(8, -8, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-8, 8);
    ctx.lineTo(-12, 20);
    ctx.moveTo(0, 10);
    ctx.lineTo(-4, 22);
    ctx.moveTo(10, 8);
    ctx.lineTo(6, 20);
    ctx.stroke();
  },
  wind(ctx) {
    ctx.beginPath();
    ctx.moveTo(-18, -8);
    ctx.quadraticCurveTo(0, -16, 18, -6);
    ctx.moveTo(-18, 2);
    ctx.quadraticCurveTo(2, -4, 20, 4);
    ctx.moveTo(-16, 12);
    ctx.quadraticCurveTo(4, 6, 16, 14);
    ctx.stroke();
  },
  warn(ctx) {
    ctx.beginPath();
    ctx.moveTo(0, -20);
    ctx.lineTo(18, 16);
    ctx.lineTo(-18, 16);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, -6);
    ctx.lineTo(0, 6);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 12, 1.6, 0, Math.PI * 2);
    ctx.fill();
  },
};

export function iconImageName(id) {
  return `draw-icon-${ICON_BY_ID[id] ? id : 'pin'}`;
}

export function wxImageName(id) {
  return `draw-wx-${WX_BY_ID[id] ? id : 'cb'}`;
}

export function ensureDrawImages(map) {
  if (!map || typeof document === 'undefined') return;
  const add = (name, key) => {
    if (map.hasImage(name)) return;
    const fn = DRAW[key];
    if (!fn) return;
    try {
      map.addImage(name, renderShape(fn), { sdf: true, pixelRatio: 2 });
    } catch {
      /* style not ready */
    }
  };
  add('draw-icon-star', 'star');
  for (const ic of ICON_ATLAS) add(iconImageName(ic.id), ic.id);
  for (const wx of WX_ATLAS) add(wxImageName(wx.id), wx.id);
}
