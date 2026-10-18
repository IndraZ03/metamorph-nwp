import {
  commitFeature,
  committedCollection,
  drawing,
  findFeature,
  moveFeature,
  redo,
  selectFeature,
  setActiveTool,
  undo,
  updateFeature,
} from './store.svelte.js';
import {
  applyVertexMove,
  buildCommitted,
  draftCollection,
  renderCollection,
  simplifyLine,
} from './geometry.js';
import { haversineM } from './geo.js';
import { POINT_CLICK_TOOLS, TOOL_BY_ID, nextNumber } from './tools.js';
import { activeLayer } from './store.svelte.js';
import { ensureDrawImages } from './icons.js';

const SRC = 'draw-src';
const DRAFT = 'draw-draft';
const LAYERS = [
  'draw-fill',
  'draw-line',
  'draw-line-dash',
  'draw-circle',
  'draw-head',
  'draw-icon',
  'draw-hl',
  'draw-text',
  'draw-label',
  'draw-sel',
  'draw-sel-pt',
  'draw-vertex',
];
const DRAFT_LAYERS = ['draw-draft-fill', 'draw-draft-line', 'draw-draft-circle', 'draw-draft-close'];
const HIT = [
  'draw-fill',
  'draw-line',
  'draw-line-dash',
  'draw-circle',
  'draw-icon',
  'draw-hl',
  'draw-text',
  'draw-head',
];
const VERTEX_HIT = ['draw-vertex'];
const MULTI_CLICK = ['polyline', 'polygon', 'area'];

const EMPTY = { type: 'FeatureCollection', features: [] };

function numGet(key, fallback) {
  return ['to-number', ['get', key], fallback];
}

const STROKE_W = numGet('strokeWidth', 2);
const FILL_OP = numGet('fillOpacity', 0.22);
const LINE_OP = numGet('lineOpacity', 0.95);
const FONT_SZ = numGet('fontSize', 13);
const ICON_SZ = ['*', STROKE_W, 0.28];
const CIRCLE_R = ['+', 3, ['*', STROKE_W, 1.25]];
const TEXT_SZ = ['+', 6, ['*', STROKE_W, 3.5]];
const DASHED = ['==', ['to-number', ['get', 'dashed']], 1];
const SOLID = ['!=', ['to-number', ['get', 'dashed']], 1];

function coord(e) {
  return [e.lngLat.lon ?? e.lngLat.lng, e.lngLat.lat];
}

export class DrawingController {
  constructor(map) {
    this.map = map;
    this.pts = [];
    this.hover = null;
    this.raf = 0;
    this.drawing = false;
    this.freehand = false;
    this.drag = null;
    this.bound = false;
    this.lastPt = null;
    this.lastClickAt = 0;
    this.justDragged = false;
    this.onClick = this.onClick.bind(this);
    this.onDblClick = this.onDblClick.bind(this);
    this.onContextMenu = this.onContextMenu.bind(this);
    this.onMove = this.onMove.bind(this);
    this.onDown = this.onDown.bind(this);
    this.onUp = this.onUp.bind(this);
    this.onKey = this.onKey.bind(this);
    this.ensureSources();
    this.bind();
    this.sync();
  }

  blocksInspect() {
    if (drawing.sidebarOpen) return true;
    if (this.pts.length) return true;
    if (this.drag) return true;
    return false;
  }

  ensureSources() {
    const map = this.map;
    if (!map.getSource(SRC)) {
      map.addSource(SRC, { type: 'geojson', data: EMPTY, promoteId: 'id' });
    }
    if (!map.getSource(DRAFT)) {
      map.addSource(DRAFT, { type: 'geojson', data: EMPTY });
    }
    this.ensureLayers();
    ensureDrawImages(map);
  }

  ensureLayers() {
    const map = this.map;
    if (map.getLayer('draw-fill') && map.getLayer('draw-sel-pt') && map.getLayer('draw-line-dash')) {
      this.stripLegacyStarLayers();
      this.ensureVertexLayer();
      this.ensureDraftCloseLayer();
      this.ensureMarkerLayers();
      this.bindStylePaint();
      this.bindDraftFilters();
      return;
    }

    const stroke = ['coalesce', ['get', 'stroke'], '#38bdf8'];
    const fill = ['coalesce', ['get', 'fill'], '#38bdf8'];

    map.addLayer({
      id: 'draw-fill',
      type: 'fill',
      source: SRC,
      filter: [
        'all',
        ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
        ['!=', ['get', 'tool'], 'arrow-head'],
      ],
      paint: {
        'fill-color': fill,
        'fill-opacity': FILL_OP,
      },
    });
    map.addLayer({
      id: 'draw-line',
      type: 'line',
      source: SRC,
      filter: [
        'all',
        ['in', ['geometry-type'], ['literal', ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']]],
        SOLID,
      ],
      paint: {
        'line-color': stroke,
        'line-width': STROKE_W,
        'line-opacity': LINE_OP,
      },
    });
    map.addLayer({
      id: 'draw-line-dash',
      type: 'line',
      source: SRC,
      filter: [
        'all',
        ['in', ['geometry-type'], ['literal', ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']]],
        DASHED,
      ],
      paint: {
        'line-color': stroke,
        'line-width': STROKE_W,
        'line-opacity': LINE_OP,
        'line-dasharray': [2, 2],
      },
    });
    map.addLayer({
      id: 'draw-circle',
      type: 'circle',
      source: SRC,
      filter: [
        'all',
        ['==', ['geometry-type'], 'Point'],
        [
          '!',
          [
            'in',
            ['get', 'marker'],
            ['literal', ['text', 'label', 'vertex', 'icon', 'numbered', 'coord', 'high', 'low', 'wx', 'star', 'pin', 'flag', 'xmark', 'plus', 'triangle', 'square', 'diamond', 'target', 'cb', 'rain', 'wind', 'warn']],
          ],
        ],
      ],
      paint: {
        'circle-color': fill,
        'circle-radius': CIRCLE_R,
        'circle-stroke-color': '#f8fafc',
        'circle-stroke-width': ['max', 1, ['*', STROKE_W, 0.55]],
        'circle-opacity': 0.95,
      },
    });
    map.addLayer({
      id: 'draw-head',
      type: 'fill',
      source: SRC,
      filter: ['==', ['get', 'tool'], 'arrow-head'],
      paint: { 'fill-color': stroke, 'fill-opacity': 0.95 },
    });
    this.ensureMarkerLayers();
    map.addLayer({
      id: 'draw-text',
      type: 'symbol',
      source: SRC,
      filter: ['==', ['get', 'marker'], 'text'],
      layout: {
        'text-field': ['coalesce', ['get', 'label'], ['get', 'name'], 'Teks'],
        'text-size': TEXT_SZ,
        'text-allow-overlap': true,
        'text-ignore-placement': true,
        'text-anchor': 'center',
      },
      paint: {
        'text-color': stroke,
        'text-halo-color': '#0b1220',
        'text-halo-width': 1.2,
      },
    });
    map.addLayer({
      id: 'draw-label',
      type: 'symbol',
      source: SRC,
      filter: ['==', ['get', 'tool'], 'label'],
      layout: {
        'text-field': ['coalesce', ['get', 'label'], ''],
        'text-size': ['max', 10, FONT_SZ],
        'text-allow-overlap': true,
        'text-ignore-placement': true,
        'text-anchor': 'center',
      },
      paint: {
        'text-color': '#e2e8f0',
        'text-halo-color': '#0b1220',
        'text-halo-width': 1.1,
      },
    });
    map.addLayer({
      id: 'draw-sel',
      type: 'line',
      source: SRC,
      filter: ['==', ['get', 'selected'], 1],
      paint: {
        'line-color': '#f8fafc',
        'line-width': 1.25,
        'line-opacity': 0.85,
        'line-dasharray': [2, 1],
      },
    });
    map.addLayer({
      id: 'draw-sel-pt',
      type: 'circle',
      source: SRC,
      filter: [
        'all',
        ['==', ['geometry-type'], 'Point'],
        ['==', ['get', 'selected'], 1],
        ['!', ['in', ['get', 'marker'], ['literal', ['label', 'vertex']]]],
      ],
      paint: {
        'circle-radius': 9,
        'circle-color': 'transparent',
        'circle-stroke-color': '#f8fafc',
        'circle-stroke-width': 1.5,
        'circle-opacity': 0.9,
      },
    });
    this.ensureVertexLayer();
    this.bindStylePaint();

    map.addLayer({
      id: 'draw-draft-fill',
      type: 'fill',
      source: DRAFT,
      filter: ['==', ['geometry-type'], 'Polygon'],
      paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.14 },
    });
    map.addLayer({
      id: 'draw-draft-line',
      type: 'line',
      source: DRAFT,
      paint: {
        'line-color': '#7dd3fc',
        'line-width': 2,
        'line-dasharray': [2, 1],
      },
    });
    map.addLayer({
      id: 'draw-draft-circle',
      type: 'circle',
      source: DRAFT,
      filter: [
        'all',
        ['==', ['geometry-type'], 'Point'],
        ['!=', ['to-number', ['get', 'closeTarget']], 1],
      ],
      paint: {
        'circle-color': '#7dd3fc',
        'circle-radius': 4,
        'circle-stroke-color': '#f8fafc',
        'circle-stroke-width': 1,
      },
    });
    this.ensureDraftCloseLayer();
  }

  stripLegacyStarLayers() {
    const map = this.map;
    if (!map) return;
    for (const id of ['draw-star', 'draw-star-lbl']) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
  }

  ensureDraftCloseLayer() {
    const map = this.map;
    if (!map) return;
    const filter = ['==', ['to-number', ['get', 'closeTarget']], 1];
    if (map.getLayer('draw-draft-close')) {
      try {
        map.setFilter('draw-draft-close', filter);
        map.setPaintProperty('draw-draft-close', 'circle-radius', 10);
      } catch {
        /* ignore */
      }
      return;
    }
    map.addLayer({
      id: 'draw-draft-close',
      type: 'circle',
      source: DRAFT,
      filter,
      paint: {
        'circle-color': '#f8fafc',
        'circle-radius': 10,
        'circle-stroke-color': '#38bdf8',
        'circle-stroke-width': 2.4,
      },
    });
  }

  bindStylePaint() {
    const map = this.map;
    if (!map) return;
    const setP = (id, name, value) => {
      if (!map.getLayer(id)) return;
      try {
        map.setPaintProperty(id, name, value);
      } catch {
        /* layer type mismatch */
      }
    };
    const setL = (id, name, value) => {
      if (!map.getLayer(id)) return;
      try {
        map.setLayoutProperty(id, name, value);
      } catch {
        /* layer type mismatch */
      }
    };
    setP('draw-fill', 'fill-opacity', FILL_OP);
    setP('draw-line', 'line-width', STROKE_W);
    setP('draw-line', 'line-opacity', LINE_OP);
    setP('draw-line-dash', 'line-width', STROKE_W);
    setP('draw-line-dash', 'line-opacity', LINE_OP);
    setP('draw-circle', 'circle-radius', CIRCLE_R);
    setP('draw-circle', 'circle-stroke-width', ['max', 1, ['*', STROKE_W, 0.55]]);
    setL('draw-icon', 'icon-size', ICON_SZ);
    setL('draw-text', 'text-size', TEXT_SZ);
    setL('draw-hl', 'text-size', TEXT_SZ);
    setL('draw-label', 'text-size', ['max', 10, FONT_SZ]);
    this.bindDraftFilters();
  }

  bindDraftFilters() {
    const map = this.map;
    if (!map) return;
    try {
      if (map.getLayer('draw-draft-circle')) {
        map.setFilter('draw-draft-circle', [
          'all',
          ['==', ['geometry-type'], 'Point'],
          ['!=', ['to-number', ['get', 'closeTarget']], 1],
        ]);
      }
    } catch {
      /* ignore */
    }
  }

  ensureVertexLayer() {
    const map = this.map;
    if (!map || map.getLayer('draw-vertex')) return;
    map.addLayer({
      id: 'draw-vertex',
      type: 'circle',
      source: SRC,
      filter: ['==', ['get', 'marker'], 'vertex'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#f8fafc',
        'circle-stroke-color': '#0ea5e9',
        'circle-stroke-width': 2,
        'circle-opacity': 0.98,
      },
    });
  }

  ensureMarkerLayers() {
    const map = this.map;
    if (!map) return;
    ensureDrawImages(map);
    const stroke = ['coalesce', ['get', 'stroke'], '#38bdf8'];
    if (!map.getLayer('draw-icon')) {
      map.addLayer({
        id: 'draw-icon',
        type: 'symbol',
        source: SRC,
        filter: [
          'any',
          ['==', ['get', 'tool'], 'icon'],
          ['==', ['get', 'tool'], 'star'],
          ['==', ['get', 'tool'], 'numbered'],
          ['==', ['get', 'tool'], 'coord'],
          ['==', ['get', 'tool'], 'wx'],
          ['==', ['get', 'marker'], 'star'],
        ],
        layout: {
          'icon-image': [
            'case',
            ['==', ['get', 'tool'], 'star'],
            'draw-icon-star',
            ['==', ['get', 'marker'], 'star'],
            'draw-icon-star',
            ['==', ['get', 'tool'], 'wx'],
            ['concat', 'draw-wx-', ['coalesce', ['get', 'wxId'], 'cb']],
            ['concat', 'draw-icon-', ['coalesce', ['get', 'iconId'], 'pin']],
          ],
          'icon-size': ICON_SZ,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-anchor': [
            'case',
            ['any', ['==', ['get', 'tool'], 'numbered'], ['==', ['get', 'tool'], 'coord']],
            'bottom',
            [
              'match',
              ['coalesce', ['get', 'iconId'], ['get', 'marker'], ''],
              'pin',
              'bottom',
              'flag',
              'bottom',
              'center',
            ],
          ],
          'text-field': [
            'case',
            ['==', ['get', 'tool'], 'numbered'],
            ['to-string', ['coalesce', ['get', 'number'], ['get', 'label'], '']],
            ['==', ['get', 'tool'], 'coord'],
            ['coalesce', ['get', 'label'], ''],
            '',
          ],
          'text-size': ['case', ['==', ['get', 'tool'], 'numbered'], 11, 10],
          'text-offset': [
            'case',
            ['==', ['get', 'tool'], 'numbered'],
            ['literal', [0, -1.35]],
            ['literal', [0, 1.15]],
          ],
          'text-anchor': [
            'case',
            ['==', ['get', 'tool'], 'numbered'],
            'center',
            'top',
          ],
          'text-allow-overlap': true,
          'text-ignore-placement': true,
        },
        paint: {
          'icon-color': stroke,
          'text-color': '#e2e8f0',
          'text-halo-color': '#0b1220',
          'text-halo-width': 1.1,
        },
      });
    }
    if (!map.getLayer('draw-hl')) {
      map.addLayer({
        id: 'draw-hl',
        type: 'symbol',
        source: SRC,
        filter: [
          'any',
          ['==', ['get', 'tool'], 'high'],
          ['==', ['get', 'tool'], 'low'],
        ],
        layout: {
          'text-field': ['coalesce', ['get', 'label'], ['case', ['==', ['get', 'tool'], 'low'], 'L', 'H']],
          'text-size': TEXT_SZ,
          'text-allow-overlap': true,
          'text-ignore-placement': true,
          'text-anchor': 'center',
        },
        paint: {
          'text-color': stroke,
          'text-halo-color': '#0b1220',
          'text-halo-width': 1.6,
        },
      });
    }
  }

  bind() {
    if (this.bound) return;
    const map = this.map;
    map.on('click', this.onClick);
    map.on('dblclick', this.onDblClick);
    map.on('contextmenu', this.onContextMenu);
    map.on('mousemove', this.onMove);
    map.on('mousedown', this.onDown);
    map.on('mouseup', this.onUp);
    window.addEventListener('mouseup', this.onUp);
    window.addEventListener('keydown', this.onKey);
    this.bound = true;
    this.applyMode();
  }

  unbind() {
    if (!this.bound) return;
    const map = this.map;
    map.off('click', this.onClick);
    map.off('dblclick', this.onDblClick);
    map.off('contextmenu', this.onContextMenu);
    map.off('mousemove', this.onMove);
    map.off('mousedown', this.onDown);
    map.off('mouseup', this.onUp);
    window.removeEventListener('mouseup', this.onUp);
    window.removeEventListener('keydown', this.onKey);
    this.bound = false;
    this.setCursor('');
    try {
      map.dragPan.enable();
      map.doubleClickZoom.enable();
    } catch {
      /* map gone */
    }
  }

  destroy() {
    this.cancelDraft();
    this.unbind();
    const map = this.map;
    if (!map) return;
    for (const id of [...LAYERS, ...DRAFT_LAYERS, 'draw-star', 'draw-star-lbl']) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource(SRC)) map.removeSource(SRC);
    if (map.getSource(DRAFT)) map.removeSource(DRAFT);
  }

  restore() {
    this.ensureSources();
    this.sync();
    this.applyMode();
  }

  applyMode() {
    const map = this.map;
    if (!map) return;
    const tool = drawing.activeTool;
    const draw = drawing.sidebarOpen && tool !== 'select';
    try {
      if (draw) map.dragPan.disable();
      else map.dragPan.enable();
      if (draw && MULTI_CLICK.includes(tool)) {
        map.doubleClickZoom.disable();
      } else {
        map.doubleClickZoom.enable();
      }
    } catch {
      /* ignore */
    }
    this.setCursor(draw ? 'crosshair' : '');
  }

  setCursor(v) {
    const c = this.map?.getCanvas();
    if (c) c.style.cursor = v;
  }

  sync() {
    const src = this.map.getSource(SRC);
    if (src) src.setData(renderCollection(committedCollection()));
    this.applyMode();
  }

  cancelDraft() {
    this.pts = [];
    this.hover = null;
    this.freehand = false;
    this.drawing = false;
    drawing.draftHint = '';
    drawing.draftReady = false;
    const src = this.map.getSource(DRAFT);
    if (src) src.setData(EMPTY);
  }

  canFinish(tool = drawing.activeTool, pts = this.pts) {
    if (tool === 'polyline' || tool === 'freehand') return pts.length >= 2;
    if (tool === 'polygon' || tool === 'area') return pts.length >= 3;
    return false;
  }

  nearFirst(pt, px = 28) {
    if (!this.pts.length || !pt) return false;
    try {
      const a = this.map.project({ lng: this.pts[0][0], lat: this.pts[0][1] });
      const b = this.map.project({ lng: pt[0], lat: pt[1] });
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      return dx * dx + dy * dy <= px * px;
    } catch {
      return haversineM(this.pts[0][0], this.pts[0][1], pt[0], pt[1]) < 250;
    }
  }

  hitCloseTarget(e) {
    if (!this.map.getLayer('draw-draft-close')) return false;
    const p = e.point;
    const pad = 16;
    const box = [
      [p.x - pad, p.y - pad],
      [p.x + pad, p.y + pad],
    ];
    const feats = this.map.queryRenderedFeatures(box, { layers: ['draw-draft-close'] });
    return feats.some((f) => Number(f.properties?.closeTarget) === 1);
  }

  finishIfPossible() {
    if (!this.canFinish()) return false;
    this.finish();
    return true;
  }

  adoptTool(id) {
    if (id === drawing.activeTool) return;
    this.finishIfPossible();
    this.cancelDraft();
    setActiveTool(id);
    this.applyMode();
  }

  queueDraft() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      const src = this.map.getSource(DRAFT);
      if (!src) return;
      const tool = drawing.activeTool;
      let hover = this.hover;
      if ((tool === 'polygon' || tool === 'area') && this.pts.length >= 3 && hover && this.nearFirst(hover)) {
        hover = this.pts[0];
      }
      src.setData(draftCollection(tool, this.pts, hover, drawing.units));
    });
  }

  hint() {
    const t = TOOL_BY_ID[drawing.activeTool];
    const n = this.pts.length;
    drawing.draftReady = this.canFinish();
    if (!t || t.id === 'select') {
      drawing.draftHint = '';
      drawing.draftReady = false;
      return;
    }
    if (t.id === 'sector') {
      drawing.draftHint = n === 0 ? 'Klik pusat' : n === 1 ? 'Klik azimuth awal' : 'Klik azimuth akhir';
      return;
    }
    if (POINT_CLICK_TOOLS.includes(t.id)) {
      drawing.draftHint = t.id === 'callout' ? 'Klik target, lalu teks' : 'Klik peta';
      drawing.draftReady = false;
      return;
    }
    if (t.id === 'callout') {
      drawing.draftHint = n === 0 ? 'Klik lokasi target' : 'Klik posisi label';
      return;
    }
    if (MULTI_CLICK.includes(t.id)) {
      if (t.id === 'polyline') {
        drawing.draftHint =
          n < 2
            ? 'Klik titik. Selesai / Enter / klik kanan / klik ganda'
            : 'Lanjut klik, atau Selesai / Enter / klik kanan / klik ganda';
      } else {
        drawing.draftHint =
          n < 3
            ? 'Klik titik (≥3). Nutup ke titik pertama / Selesai / Enter'
            : 'Klik titik pertama untuk nutup, atau Selesai / Enter';
      }
      return;
    }
    if (t.id === 'freehand') {
      drawing.draftHint = 'Tahan dan seret. Lepas untuk selesai';
      return;
    }
    drawing.draftHint = n === 0 ? 'Klik peta' : 'Klik titik kedua';
  }

  hitId(e) {
    const feats = this.map.queryRenderedFeatures(e.point, { layers: HIT.filter((id) => this.map.getLayer(id)) });
    for (const f of feats) {
      const id = f.properties?.parentId || f.properties?.id || f.id;
      if (id && findFeature(String(id))) return String(id);
    }
    return null;
  }

  hitVertex(e) {
    const layers = VERTEX_HIT.filter((id) => this.map.getLayer(id));
    if (!layers.length) return null;
    const feats = this.map.queryRenderedFeatures(e.point, { layers });
    for (const f of feats) {
      if (f.properties?.marker !== 'vertex') continue;
      const parentId = String(f.properties.parentId || '');
      const vi = Number(f.properties.vi);
      if (!parentId || !Number.isFinite(vi)) continue;
      if (!findFeature(parentId)) continue;
      return { parentId, vi };
    }
    return null;
  }

  onClick(e) {
    if (e.originalEvent?.button && e.originalEvent.button !== 0) return;
    if (!drawing.sidebarOpen) return;
    if (this.justDragged) {
      this.justDragged = false;
      return;
    }
    const tool = drawing.activeTool;
    if (e.originalEvent?.detail > 1) return;
    this.lastClickAt = performance.now();
    if (tool === 'select') {
      const id = this.hitId(e);
      selectFeature(id);
      this.sync();
      if (id) {
        e.preventDefault();
        e.originalEvent?.stopPropagation();
        e.originalEvent?.stopImmediatePropagation?.();
      }
      return;
    }
    e.preventDefault();
    e.originalEvent?.stopPropagation();
    e.originalEvent?.stopImmediatePropagation?.();
    if (this.freehand) return;
    const pt = coord(e);

    if (POINT_CLICK_TOOLS.includes(tool)) {
      const extras = this.clickExtras(tool);
      const built = buildCommitted(tool, [pt], drawing.units, extras);
      if (built) commitFeature(built);
      this.cancelDraft();
      this.sync();
      return;
    }

    if (tool === 'freehand') return;

    if (
      (tool === 'polygon' || tool === 'area') &&
      this.pts.length >= 3 &&
      (this.nearFirst(pt) || this.hitCloseTarget(e))
    ) {
      this.finish();
      return;
    }

    this.pts.push(pt);
    this.hover = null;
    this.hint();

    const twoClick = ['line', 'arrow', 'distance', 'rectangle', 'circle', 'radius', 'rings', 'callout'];
    if (twoClick.includes(tool) && this.pts.length >= 2) {
      this.finish();
      return;
    }
    if (tool === 'sector' && this.pts.length >= 3) {
      this.finish();
      return;
    }
    this.queueDraft();
  }

  onDblClick(e) {
    if (!drawing.sidebarOpen) return;
    const tool = drawing.activeTool;
    if (!MULTI_CLICK.includes(tool)) return;
    e.preventDefault();
    e.originalEvent?.stopPropagation();
    e.originalEvent?.stopImmediatePropagation?.();
    this.finishIfPossible();
  }

  onContextMenu(e) {
    if (!drawing.sidebarOpen) return;
    if (!MULTI_CLICK.includes(drawing.activeTool)) return;
    e.preventDefault();
    e.originalEvent?.preventDefault();
    e.originalEvent?.stopPropagation();
    this.finishIfPossible();
  }

  onDown(e) {
    if (!drawing.sidebarOpen) return;
    if (e.originalEvent?.button && e.originalEvent.button !== 0) return;
    const tool = drawing.activeTool;
    if (tool === 'freehand') {
      e.preventDefault();
      this.freehand = true;
      this.pts = [coord(e)];
      this.hint();
      this.queueDraft();
      return;
    }
    if (tool === 'select') {
      const vtx = this.hitVertex(e);
      if (vtx) {
        const hit = findFeature(vtx.parentId);
        if (!hit || hit.layer.locked || hit.feature.properties.locked) return;
        selectFeature(vtx.parentId);
        this.sync();
        this.drag = {
          kind: 'vertex',
          id: vtx.parentId,
          vi: vtx.vi,
          start: coord(e),
          origFeature: JSON.parse(JSON.stringify(hit.feature)),
        };
        this.map.dragPan.disable();
        this.setCursor('grabbing');
        e.preventDefault();
        return;
      }
      const id = this.hitId(e);
      if (!id) return;
      const hit = findFeature(id);
      if (!hit || hit.layer.locked || hit.feature.properties.locked) return;
      this.drag = {
        kind: 'feature',
        id,
        start: coord(e),
        orig: JSON.parse(JSON.stringify(hit.feature.geometry)),
        origCenter: hit.feature.properties.center
          ? hit.feature.properties.center.slice()
          : null,
      };
      this.map.dragPan.disable();
      this.setCursor('grabbing');
    }
  }

  onMove(e) {
    this.lastPt = coord(e);
    if (this.drag) {
      const src = this.map.getSource(SRC);
      if (!src) return;
      if (this.drag.kind === 'vertex') {
        const next = applyVertexMove(this.drag.origFeature, this.drag.vi, coord(e), drawing.units);
        if (!next) return;
        const fc = committedCollection();
        const feat = fc.features.find((f) => f.id === this.drag.id);
        if (feat) {
          feat.geometry = next.geometry;
          Object.assign(feat.properties, next.properties);
        }
        src.setData(renderCollection(fc));
        return;
      }
      const [lon, lat] = coord(e);
      const dLon = lon - this.drag.start[0];
      const dLat = lat - this.drag.start[1];
      const fc = committedCollection();
      const feat = fc.features.find((f) => f.id === this.drag.id);
      if (feat) {
        feat.geometry = offsetGeom(this.drag.orig, dLon, dLat);
        if (this.drag.origCenter) {
          feat.properties.center = [
            this.drag.origCenter[0] + dLon,
            this.drag.origCenter[1] + dLat,
          ];
        }
      }
      src.setData(renderCollection(fc));
      return;
    }
    if (drawing.sidebarOpen && drawing.activeTool === 'select') {
      this.setCursor(this.hitVertex(e) ? 'grab' : '');
      return;
    }
    if (!drawing.sidebarOpen || drawing.activeTool === 'select') return;
    if (
      (drawing.activeTool === 'polygon' || drawing.activeTool === 'area') &&
      this.pts.length >= 3 &&
      this.nearFirst(coord(e))
    ) {
      this.setCursor('pointer');
    } else if (drawing.activeTool !== 'select') {
      this.setCursor('crosshair');
    }
    if (this.freehand) {
      const pt = coord(e);
      const last = this.pts[this.pts.length - 1];
      const p0 = this.map.project(last);
      const p1 = this.map.project(pt);
      const dx = p1.x - p0.x;
      const dy = p1.y - p0.y;
      if (dx * dx + dy * dy >= 9) {
        this.pts.push(pt);
        this.queueDraft();
      }
      return;
    }
    if (!this.pts.length) return;
    this.hover = coord(e);
    this.queueDraft();
  }

  onUp(e) {
    const pt = e?.lngLat ? coord(e) : this.lastPt;
    if (this.freehand) {
      this.freehand = false;
      if (this.pts.length >= 2) {
        this.pts = simplifyLine(this.pts, 3, this.map);
        this.finish();
      } else {
        this.cancelDraft();
      }
      return;
    }
    if (this.drag) {
      const drag = this.drag;
      this.drag = null;
      this.justDragged = true;
      this.applyMode();
      if (!pt) {
        this.sync();
        return;
      }
      if (drag.kind === 'vertex') {
        const next = applyVertexMove(drag.origFeature, drag.vi, pt, drawing.units);
        if (next) updateFeature(drag.id, { geometry: next.geometry, properties: next.properties });
        this.sync();
        return;
      }
      const [lon, lat] = pt;
      const dLon = lon - drag.start[0];
      const dLat = lat - drag.start[1];
      if (Math.abs(dLon) > 1e-8 || Math.abs(dLat) > 1e-8) moveFeature(drag.id, dLon, dLat);
      this.sync();
    }
  }

  onKey(e) {
    const tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable) return;
    if (e.key === 'Escape') {
      if (this.pts.length || this.freehand) {
        e.preventDefault();
        this.cancelDraft();
        return;
      }
      if (drawing.selectedId) {
        selectFeature(null);
        this.sync();
      }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
      e.preventDefault();
      this.cancelDraft();
      if (e.shiftKey) redo();
      else undo();
      this.sync();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || e.key === 'Y')) {
      e.preventDefault();
      this.cancelDraft();
      redo();
      this.sync();
      return;
    }
    if ((e.key === 'Enter' || e.key === ' ') && drawing.sidebarOpen) {
      if (MULTI_CLICK.includes(drawing.activeTool) && this.pts.length) {
        e.preventDefault();
        this.finishIfPossible();
      }
    }
    if (!drawing.sidebarOpen) return;
    if (e.ctrlKey || e.metaKey) return;
    const mapKey = { v: 'select', p: 'point', s: 'star', t: 'text', f: 'freehand', l: 'line' };
    const next = mapKey[e.key?.toLowerCase()];
    if (next) {
      e.preventDefault();
      this.adoptTool(next);
    }
  }

  clickExtras(tool) {
    if (tool === 'text') return { label: 'Teks' };
    if (tool === 'callout') return { label: 'Label' };
    if (tool === 'numbered') {
      const feats = activeLayer()?.features || [];
      return { number: nextNumber(feats) };
    }
    if (tool === 'icon') return { iconId: drawing.iconId || 'pin' };
    if (tool === 'wx') return { wxId: drawing.wxId || 'cb' };
    if (tool === 'high') return { label: 'H' };
    if (tool === 'low') return { label: 'L' };
    return {};
  }

  finish() {
    const tool = drawing.activeTool;
    let pts = this.pts;
    if (MULTI_CLICK.includes(tool) && pts.length >= 2) {
      const a = pts[pts.length - 2];
      const b = pts[pts.length - 1];
      if (haversineM(a[0], a[1], b[0], b[1]) < 1) pts = pts.slice(0, -1);
    }
    const built = buildCommitted(tool, pts, drawing.units, this.clickExtras(tool));
    this.cancelDraft();
    if (built) {
      commitFeature(built);
      if (MULTI_CLICK.includes(tool)) setActiveTool('select');
      this.sync();
    }
  }
}

function offsetGeom(geom, dLon, dLat) {
  const walk = (coords) => {
    if (!Array.isArray(coords)) return coords;
    if (typeof coords[0] === 'number') {
      let lon = coords[0] + dLon;
      lon = ((((lon + 180) % 360) + 360) % 360) - 180;
      return [lon, coords[1] + dLat];
    }
    return coords.map(walk);
  };
  return { type: geom.type, coordinates: walk(geom.coordinates) };
}
