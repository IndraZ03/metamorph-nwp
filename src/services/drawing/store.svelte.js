/**
 * Drawing state. One source of truth. Map layers stay on even when sidebar closes.
 */
import { defaultStyle, nextName, nextNumber } from './tools.js';
import { ICON_BY_ID, WX_BY_ID } from './icons.js';
import { loadDrawings, saveDrawings, sanitizeText } from './persist.js';
import { bboxOf } from '../userLayers.js';

const HISTORY_MAX = 40;
const EMPTY_FC = { type: 'FeatureCollection', features: [] };

export const drawing = $state({
  sidebarOpen: false,
  ready: false,
  activeTool: 'select',
  units: 'km',
  selectedId: null,
  layers: [],
  activeLayerId: null,
  history: [],
  future: [],
  saveStatus: 'idle',
  error: null,
  draftHint: '',
  draftReady: false,
  iconId: 'pin',
  wxId: 'cb',
});

let seq = 0;
let saveTimer = null;
let persistGen = 0;

function uid(prefix = 'd') {
  seq += 1;
  return `${prefix}${Date.now().toString(36)}${seq.toString(36)}`;
}

export function emptyFc() {
  return { type: 'FeatureCollection', features: [] };
}

export function activeLayer() {
  return drawing.layers.find((l) => l.id === drawing.activeLayerId) || drawing.layers[0] || null;
}

export function allFeatures() {
  return drawing.layers.flatMap((l) => l.features.map((f) => ({ layer: l, feature: f })));
}

export function findFeature(id) {
  for (const layer of drawing.layers) {
    const feature = layer.features.find((f) => f.id === id);
    if (feature) return { layer, feature };
  }
  return null;
}

function toPlain(value) {
  return JSON.parse(JSON.stringify(value));
}

function snapshot() {
  return JSON.stringify(toPlain(drawing.layers));
}

function restoreSnapshot(raw) {
  const layers = JSON.parse(raw);
  drawing.layers = layers;
  if (!layers.some((l) => l.id === drawing.activeLayerId)) {
    drawing.activeLayerId = layers[0]?.id || null;
  }
  if (drawing.selectedId && !findFeature(drawing.selectedId)) drawing.selectedId = null;
}

export function pushHistory() {
  const next = [...drawing.history, snapshot()];
  if (next.length > HISTORY_MAX) next.shift();
  drawing.history = next;
  drawing.future = [];
  scheduleSave();
}

export function undo() {
  if (!drawing.history.length) return false;
  const hist = drawing.history.slice();
  const raw = hist.pop();
  drawing.future = [...drawing.future, snapshot()];
  drawing.history = hist;
  restoreSnapshot(raw);
  scheduleSave();
  return true;
}

export function redo() {
  if (!drawing.future.length) return false;
  const fut = drawing.future.slice();
  const raw = fut.pop();
  drawing.history = [...drawing.history, snapshot()];
  drawing.future = fut;
  restoreSnapshot(raw);
  scheduleSave();
  return true;
}

export function canUndo() {
  return drawing.history.length > 0;
}

export function canRedo() {
  return drawing.future.length > 0;
}

function ensureLayer() {
  if (drawing.layers.length) return activeLayer();
  const layer = makeLayer('Analisis');
  drawing.layers = [layer];
  drawing.activeLayerId = layer.id;
  return layer;
}

export function makeLayer(name = 'Analisis') {
  return {
    id: uid('L'),
    name: sanitizeText(name, 80) || 'Analisis',
    visible: true,
    locked: false,
    features: [],
  };
}

export function addLayer(name) {
  pushHistory();
  const layer = makeLayer(name || `Grup ${drawing.layers.length + 1}`);
  drawing.layers = [...drawing.layers, layer];
  drawing.activeLayerId = layer.id;
  return layer;
}

export function renameLayer(id, name) {
  const layer = drawing.layers.find((l) => l.id === id);
  if (!layer) return;
  const next = sanitizeText(name, 80);
  if (!next || next === layer.name) return;
  pushHistory();
  layer.name = next;
  drawing.layers = [...drawing.layers];
}

export function setLayerVisible(id, visible) {
  const layer = drawing.layers.find((l) => l.id === id);
  if (!layer) return;
  layer.visible = visible;
  drawing.layers = [...drawing.layers];
  scheduleSave();
}

export function setLayerLocked(id, locked) {
  const layer = drawing.layers.find((l) => l.id === id);
  if (!layer) return;
  layer.locked = locked;
  if (locked && drawing.selectedId) {
    const hit = findFeature(drawing.selectedId);
    if (hit?.layer.id === id) drawing.selectedId = null;
  }
  drawing.layers = [...drawing.layers];
  scheduleSave();
}

export function removeLayer(id) {
  if (drawing.layers.length <= 1) {
    clearLayer(id);
    return;
  }
  pushHistory();
  drawing.layers = drawing.layers.filter((l) => l.id !== id);
  if (drawing.activeLayerId === id) drawing.activeLayerId = drawing.layers[0].id;
  if (drawing.selectedId && !findFeature(drawing.selectedId)) drawing.selectedId = null;
}

export function clearLayer(id) {
  const layer = drawing.layers.find((l) => l.id === id);
  if (!layer || !layer.features.length) return;
  pushHistory();
  layer.features = [];
  drawing.layers = [...drawing.layers];
  if (drawing.selectedId && !findFeature(drawing.selectedId)) drawing.selectedId = null;
}

export function setActiveLayer(id) {
  if (drawing.layers.some((l) => l.id === id)) drawing.activeLayerId = id;
}

export function moveLayer(id, dir) {
  const i = drawing.layers.findIndex((l) => l.id === id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= drawing.layers.length) return;
  pushHistory();
  const next = drawing.layers.slice();
  const [row] = next.splice(i, 1);
  next.splice(j, 0, row);
  drawing.layers = next;
}

export function clearAll() {
  if (!drawing.layers.some((l) => l.features.length)) return;
  pushHistory();
  drawing.layers = drawing.layers.map((l) => ({ ...l, features: [] }));
  drawing.selectedId = null;
}

export function setSidebarOpen(open) {
  drawing.sidebarOpen = !!open;
  if (!open) {
    drawing.draftHint = '';
    drawing.draftReady = false;
  }
}

export function toggleSidebar() {
  setSidebarOpen(!drawing.sidebarOpen);
}

export function setActiveTool(id) {
  drawing.activeTool = id || 'select';
  if (id !== 'select') drawing.selectedId = null;
}

export function setUnits(units) {
  drawing.units = units === 'nm' ? 'nm' : 'km';
  scheduleSave();
}

export function setIconId(id) {
  drawing.iconId = ICON_BY_ID[id] ? id : 'pin';
}

export function setWxId(id) {
  drawing.wxId = WX_BY_ID[id] ? id : 'cb';
}

export function selectFeature(id) {
  drawing.selectedId = id;
  if (id) {
    const hit = findFeature(id);
    if (hit) drawing.activeLayerId = hit.layer.id;
  }
}

export function commitFeature(partial) {
  const layer = ensureLayer();
  if (layer.locked) {
    drawing.error = 'Layer terkunci';
    return null;
  }
  const tool = partial.properties?.tool || drawing.activeTool;
  const now = new Date().toISOString();
  const feature = {
    type: 'Feature',
    id: partial.id || uid('f'),
    geometry: partial.geometry,
    properties: {
      units: drawing.units,
      timeMode: 'always',
      validTime: null,
      ...partial.properties,
      name: sanitizeText(partial.properties?.name || nextName(layer.features, tool), 80),
      tool,
      label: sanitizeText(partial.properties?.label || '', 120),
      notes: sanitizeText(partial.properties?.notes || '', 400),
      style: { ...defaultStyle(tool), ...(partial.properties?.style || {}) },
      visible: true,
      locked: false,
      createdAt: now,
      updatedAt: now,
    },
  };
  const p = feature.properties;
  if (p.iconId && !ICON_BY_ID[p.iconId]) p.iconId = 'pin';
  if (p.wxId && !WX_BY_ID[p.wxId]) p.wxId = 'cb';
  if (tool === 'numbered') {
    const n = Number(p.number);
    p.number = Number.isFinite(n) && n > 0 ? n : nextNumber(layer.features);
    if (!p.label) p.label = String(p.number);
  }
  pushHistory();
  layer.features = [...layer.features, feature];
  drawing.layers = [...drawing.layers];
  drawing.selectedId = feature.id;
  drawing.error = null;
  return feature;
}

export function updateFeature(id, patch, { history = true } = {}) {
  const hit = findFeature(id);
  if (!hit || hit.layer.locked || hit.feature.properties.locked) return false;
  if (history) pushHistory();
  if (patch.geometry) hit.feature.geometry = patch.geometry;
  if (patch.properties) {
    const next = { ...hit.feature.properties, ...patch.properties, updatedAt: new Date().toISOString() };
    if (next.name != null) next.name = sanitizeText(next.name, 80);
    if (next.label != null) next.label = sanitizeText(next.label, 120);
    if (next.notes != null) next.notes = sanitizeText(next.notes, 400);
    hit.feature.properties = next;
  }
  drawing.layers = [...drawing.layers];
  if (!history) scheduleSave();
  return true;
}

export function patchStyle(id, stylePatch, { history = true } = {}) {
  const hit = findFeature(id);
  if (!hit || hit.layer.locked || hit.feature.properties.locked) return false;
  if (history) pushHistory();
  hit.feature.properties.style = { ...hit.feature.properties.style, ...stylePatch };
  hit.feature.properties.updatedAt = new Date().toISOString();
  drawing.layers = [...drawing.layers];
  if (!history) scheduleSave();
  return true;
}

export function duplicateFeature(id) {
  const hit = findFeature(id);
  if (!hit || hit.layer.locked) return null;
  const copy = toPlain(hit.feature);
  copy.id = uid('f');
  copy.properties.name = sanitizeText(`${hit.feature.properties.name} copy`, 80);
  copy.properties.createdAt = new Date().toISOString();
  copy.properties.updatedAt = copy.properties.createdAt;
  pushHistory();
  hit.layer.features = [...hit.layer.features, copy];
  drawing.layers = [...drawing.layers];
  drawing.selectedId = copy.id;
  return copy;
}

export function removeFeature(id) {
  const hit = findFeature(id);
  if (!hit || hit.layer.locked) return false;
  pushHistory();
  hit.layer.features = hit.layer.features.filter((f) => f.id !== id);
  drawing.layers = [...drawing.layers];
  if (drawing.selectedId === id) drawing.selectedId = null;
  return true;
}

export function setFeatureVisible(id, visible) {
  const hit = findFeature(id);
  if (!hit) return;
  hit.feature.properties.visible = visible;
  drawing.layers = [...drawing.layers];
  scheduleSave();
}

export function setFeatureLocked(id, locked) {
  const hit = findFeature(id);
  if (!hit) return;
  hit.feature.properties.locked = locked;
  if (locked && drawing.selectedId === id) drawing.selectedId = null;
  drawing.layers = [...drawing.layers];
  scheduleSave();
}

export function moveFeature(id, dLon, dLat) {
  const hit = findFeature(id);
  if (!hit || hit.layer.locked || hit.feature.properties.locked) return false;
  const geom = toPlain(hit.feature.geometry);
  const walk = (coords) => {
    if (!Array.isArray(coords)) return coords;
    if (typeof coords[0] === 'number') {
      let lon = coords[0] + dLon;
      lon = ((((lon + 180) % 360) + 360) % 360) - 180;
      return [lon, coords[1] + dLat];
    }
    return coords.map(walk);
  };
  geom.coordinates = walk(geom.coordinates);
  const props = { ...hit.feature.properties };
  if (props.center) {
    props.center = walk(props.center);
  }
  pushHistory();
  hit.feature.geometry = geom;
  hit.feature.properties = { ...props, updatedAt: new Date().toISOString() };
  drawing.layers = [...drawing.layers];
  return true;
}

export function committedCollection() {
  const features = [];
  for (const layer of drawing.layers) {
    if (!layer.visible) continue;
    for (const f of layer.features) {
      if (f.properties.visible === false) continue;
      const style = f.properties.style || {};
      features.push({
        type: 'Feature',
        id: f.id,
        geometry: f.geometry,
        properties: {
          ...f.properties,
          id: f.id,
          layerId: layer.id,
          layerName: layer.name,
          selected: f.id === drawing.selectedId ? 1 : 0,
          marker: f.properties.marker || f.properties.tool,
          label: f.properties.label || (f.properties.tool === 'star' ? f.properties.name : '') || '',
          stroke: style.stroke || '#38bdf8',
          fill: style.fill || style.stroke || '#38bdf8',
          strokeWidth: Number(style.strokeWidth) > 0 ? Number(style.strokeWidth) : 2,
          fillOpacity: Number.isFinite(Number(style.fillOpacity)) ? Number(style.fillOpacity) : 0.22,
          lineOpacity: Number.isFinite(Number(style.lineOpacity)) ? Number(style.lineOpacity) : 0.95,
          dashed: style.dashed ? 1 : 0,
          fontSize: Number(style.fontSize) > 0 ? Number(style.fontSize) : 12,
        },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

export function exportGeoJSON() {
  return {
    type: 'FeatureCollection',
    features: drawing.layers.flatMap((layer) =>
      layer.features.map((f) => ({
        type: 'Feature',
        id: f.id,
        geometry: f.geometry,
        properties: { ...f.properties, layerId: layer.id, layerName: layer.name },
      }))
    ),
  };
}

export function importGeoJSON(fc, { replace = false } = {}) {
  if (!fc || fc.type !== 'FeatureCollection' || !Array.isArray(fc.features)) {
    throw new Error('GeoJSON harus FeatureCollection.');
  }
  const incoming = [];
  for (const f of fc.features) {
    if (!f || f.type !== 'Feature' || !f.geometry?.type) continue;
    const tool = f.properties?.tool || guessTool(f);
    incoming.push({
      type: 'Feature',
      id: typeof f.id === 'string' ? f.id : uid('f'),
      geometry: f.geometry,
      properties: {
        name: sanitizeText(f.properties?.name || f.properties?.layerName || nextName(incoming, tool), 80),
        tool,
        label: sanitizeText(f.properties?.label || '', 120),
        notes: sanitizeText(f.properties?.notes || '', 400),
        units: f.properties?.units === 'nm' ? 'nm' : 'km',
        timeMode: f.properties?.timeMode === 'valid' ? 'valid' : 'always',
        validTime: f.properties?.validTime || null,
        style: { ...defaultStyle(tool), ...(f.properties?.style || {}) },
        visible: f.properties?.visible !== false,
        locked: !!f.properties?.locked,
        center: f.properties?.center,
        radiusM: f.properties?.radiusM,
        startAz: f.properties?.startAz,
        endAz: f.properties?.endAz,
        radiiM: f.properties?.radiiM,
        labelAz: Number.isFinite(Number(f.properties?.labelAz)) ? Number(f.properties.labelAz) : undefined,
        labelBearings: Array.isArray(f.properties?.labelBearings) ? f.properties.labelBearings : undefined,
        iconId: ICON_BY_ID[f.properties?.iconId] ? f.properties.iconId : undefined,
        wxId: WX_BY_ID[f.properties?.wxId] ? f.properties.wxId : undefined,
        number: Number.isFinite(Number(f.properties?.number)) ? Number(f.properties.number) : undefined,
        dms: typeof f.properties?.dms === 'string' ? sanitizeText(f.properties.dms, 80) : undefined,
        analysis: f.properties?.analysis ? 1 : undefined,
        marker: typeof f.properties?.marker === 'string' ? f.properties.marker : undefined,
        createdAt: f.properties?.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    });
  }
  if (!incoming.length) throw new Error('Tidak ada fitur valid di file.');
  pushHistory();
  const layer = ensureLayer();
  layer.features = replace ? incoming : [...layer.features, ...incoming];
  drawing.layers = [...drawing.layers];
  return incoming.length;
}

function guessTool(f) {
  const t = f.geometry?.type;
  if (t === 'Point') return 'point';
  if (t === 'Polygon') return 'polygon';
  if (t === 'LineString') return 'polyline';
  return 'polyline';
}

export function drawingBbox() {
  const fc = exportGeoJSON();
  if (!fc.features.length) return null;
  return bboxOf(fc);
}

function scheduleSave() {
  drawing.saveStatus = 'unsaved';
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    persist().catch((err) => {
      drawing.saveStatus = 'error';
      drawing.error = err.message;
    });
  }, 450);
}

export async function persist() {
  const gen = ++persistGen;
  drawing.saveStatus = 'saving';
  try {
    await saveDrawings({
      units: drawing.units,
      activeLayerId: drawing.activeLayerId,
      layers: toPlain(drawing.layers),
    });
  } catch (err) {
    if (gen !== persistGen) return;
    drawing.saveStatus = 'error';
    drawing.error = err?.message || 'Gagal simpan';
    throw err;
  }
  if (gen !== persistGen) return;
  drawing.saveStatus = 'saved';
  drawing.error = null;
}

export async function hydrate() {
  try {
    const data = await loadDrawings();
    if (data?.layers?.length) {
      drawing.layers = toPlain(data.layers);
      drawing.activeLayerId = data.activeLayerId || data.layers[0].id;
      drawing.units = data.units === 'nm' ? 'nm' : 'km';
    } else {
      const layer = makeLayer('Analisis');
      drawing.layers = [layer];
      drawing.activeLayerId = layer.id;
    }
    drawing.saveStatus = 'saved';
  } catch {
    const layer = makeLayer('Analisis');
    drawing.layers = [layer];
    drawing.activeLayerId = layer.id;
    drawing.saveStatus = 'idle';
  }
  drawing.ready = true;
}

export { EMPTY_FC };
