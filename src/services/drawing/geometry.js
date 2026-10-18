import {
  bearingDeg,
  defaultRingRadiiM,
  destination,
  formatArea,
  formatBearing,
  formatDist,
  NM_M,
  formatDMS,
  formatLatLon,
  geodesicCircle,
  geodesicSector,
  haversineM,
  lineLengthM,
  midpoint,
  polygonAreaM2,
  ringPerimeterM,
  sameCoord,
} from './geo.js';

function closeRing(ring) {
  if (!ring.length) return ring;
  const a = ring[0];
  const b = ring[ring.length - 1];
  if (a[0] === b[0] && a[1] === b[1]) return ring;
  return [...ring, a];
}

export function rectangleRing(a, b) {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  return closeRing([
    [lon1, lat1],
    [lon2, lat1],
    [lon2, lat2],
    [lon1, lat2],
  ]);
}

export function simplifyLine(coords, minPx, map) {
  if (!map || coords.length < 3) return coords;
  const out = [coords[0]];
  let last = map.project(coords[0]);
  for (let i = 1; i < coords.length - 1; i++) {
    const p = map.project(coords[i]);
    const dx = p.x - last.x;
    const dy = p.y - last.y;
    if (dx * dx + dy * dy >= minPx * minPx) {
      out.push(coords[i]);
      last = p;
    }
  }
  out.push(coords[coords.length - 1]);
  return out;
}

export function geodesicStar(lon, lat, radiusM, rotation = 0, innerRatio = 0.382) {
  if (!(radiusM > 0)) return null;
  const coords = [];
  for (let i = 0; i < 10; i++) {
    const az = rotation - 90 + i * 36;
    const r = i % 2 === 0 ? radiusM : radiusM * innerRatio;
    coords.push(destination(lon, lat, az, r));
  }
  return closeRing(coords);
}

export function arrowHeadPolygon(coords) {
  if (!coords || coords.length < 2) return null;
  const a = coords[coords.length - 2];
  const b = coords[coords.length - 1];
  const len = haversineM(a[0], a[1], b[0], b[1]);
  if (len < 2) return null;
  const size = Math.min(Math.max(len * 0.14, 250), 18000);
  const brg = bearingDeg(a[0], a[1], b[0], b[1]);
  const left = destination(b[0], b[1], brg + 155, size);
  const right = destination(b[0], b[1], brg - 155, size);
  return closeRing([b, left, right]);
}

export function measureLabel(tool, coords, units, extra = {}) {
  if (tool === 'distance' && coords.length >= 2) {
    const a = coords[0];
    const b = coords[coords.length - 1];
    const d = haversineM(a[0], a[1], b[0], b[1]);
    const brg = bearingDeg(a[0], a[1], b[0], b[1]);
    return `${formatDist(d, units)}  ${formatBearing(brg)} T`;
  }
  if ((tool === 'polyline' || tool === 'freehand' || tool === 'arrow' || tool === 'line') && coords.length >= 2) {
    return formatDist(lineLengthM(coords), units);
  }
  if (tool === 'radius' || tool === 'circle') {
    return extra.radiusM != null ? `r ${formatDist(extra.radiusM, units)}` : '';
  }
  if (tool === 'rings') {
    const radii = extra.radiiM || [];
    return radii.length ? radii.map((m) => formatDist(m, units)).join(' · ') : '';
  }
  if (tool === 'sector') {
    const r = extra.radiusM != null ? formatDist(extra.radiusM, units) : '';
    const az =
      extra.startAz != null && extra.endAz != null
        ? `${formatBearing(extra.startAz)}–${formatBearing(extra.endAz)} T`
        : '';
    return [r, az].filter(Boolean).join('  ');
  }
  if ((tool === 'polygon' || tool === 'area' || tool === 'rectangle') && coords?.[0]?.length >= 4) {
    const area = polygonAreaM2(coords);
    const peri = ringPerimeterM(coords[0]);
    return `${formatArea(area, units)}  ${formatDist(peri, units)}`;
  }
  return extra.label || '';
}

export function labelPointFor(tool, geometry, extra = {}) {
  const g = geometry;
  if (!g) return null;
  if (g.type === 'Point') return g.coordinates;
  if (g.type === 'LineString' && g.coordinates.length >= 2) {
    const c = g.coordinates;
    if (tool === 'callout') return c[c.length - 1];
    if (tool === 'distance') return midpoint(c[0][0], c[0][1], c[c.length - 1][0], c[c.length - 1][1]);
    const mid = c[Math.floor(c.length / 2)];
    return mid;
  }
  if (g.type === 'Polygon') {
    if ((tool === 'radius' || tool === 'circle') && extra.center && extra.radiusM > 0) {
      const az = extra.labelAz != null ? extra.labelAz : 90;
      return destination(extra.center[0], extra.center[1], az, extra.radiusM);
    }
    if (tool === 'sector' && extra.center && extra.radiusM > 0) {
      let a0 = extra.startAz;
      let a1 = extra.endAz;
      if (a0 == null || a1 == null) return extra.center;
      let span = (a1 - a0 + 360) % 360;
      if (span === 0) span = 360;
      return destination(extra.center[0], extra.center[1], a0 + span / 2, extra.radiusM);
    }
    if (extra.center && tool !== 'radius' && tool !== 'circle') return extra.center;
    const ring = g.coordinates[0];
    if (!ring?.length) return null;
    let lon = 0;
    let lat = 0;
    const n = ring.length - 1;
    for (let i = 0; i < n; i++) {
      lon += ring[i][0];
      lat += ring[i][1];
    }
    return [lon / n, lat / n];
  }
  if (g.type === 'MultiLineString') {
    if (tool === 'rings') return null;
    if (extra.center) return extra.center;
    const first = g.coordinates[0];
    return first?.[0] || null;
  }
  return extra.center || null;
}

export function buildCommitted(tool, pts, units, extras = {}) {
  if (!pts.length) return null;

  if (tool === 'point' || tool === 'text' || tool === 'icon' || tool === 'numbered' || tool === 'coord' || tool === 'high' || tool === 'low' || tool === 'wx' || tool === 'star') {
    const [lon, lat] = pts[0];
    const marker =
      tool === 'icon'
        ? extras.iconId || 'pin'
        : tool === 'wx'
          ? extras.wxId || 'cb'
          : tool;
    let label = extras.label || extras.name || '';
    if (tool === 'text' && !label) label = 'Teks';
    if (tool === 'numbered') {
      const n = extras.number > 0 ? extras.number : 1;
      label = extras.label || String(n);
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker, number: n },
      };
    }
    if (tool === 'coord') {
      label = extras.label || formatLatLon(lon, lat);
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker, dms: formatDMS(lon, lat) },
      };
    }
    if (tool === 'high' || tool === 'low') {
      label = extras.label || (tool === 'high' ? 'H' : 'L');
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker, analysis: 1 },
      };
    }
    if (tool === 'wx') {
      label = extras.label || '';
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker, wxId: extras.wxId || 'cb', analysis: 1 },
      };
    }
    if (tool === 'icon') {
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker, iconId: extras.iconId || 'pin' },
      };
    }
    if (tool === 'star') {
      return {
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { tool, label, marker: 'star' },
      };
    }
    return {
      geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: { tool, label, marker },
    };
  }

  if (tool === 'callout') {
    if (pts.length < 2) return null;
    const a = pts[0];
    const b = pts[pts.length - 1];
    if (haversineM(a[0], a[1], b[0], b[1]) < 1) return null;
    return {
      geometry: { type: 'LineString', coordinates: [a, b] },
      properties: {
        tool,
        marker: 'callout',
        label: extras.label || 'Label',
        leader: 1,
      },
    };
  }

  if (tool === 'line' || tool === 'arrow' || tool === 'distance') {
    if (pts.length < 2) return null;
    const coords = [pts[0], pts[pts.length - 1]];
    if (haversineM(coords[0][0], coords[0][1], coords[1][0], coords[1][1]) < 1) return null;
    const label = measureLabel(tool === 'distance' ? 'distance' : tool, coords, units);
    const props = { tool, label };
    if (tool === 'arrow') props.arrow = 'end';
    if (tool === 'distance') {
      props.distanceM = haversineM(coords[0][0], coords[0][1], coords[1][0], coords[1][1]);
      props.bearing = bearingDeg(coords[0][0], coords[0][1], coords[1][0], coords[1][1]);
    }
    return { geometry: { type: 'LineString', coordinates: coords }, properties: props };
  }

  if (tool === 'polyline' || tool === 'freehand') {
    if (pts.length < 2) return null;
    const coords = pts;
    return {
      geometry: { type: 'LineString', coordinates: coords },
      properties: { tool, label: measureLabel(tool, coords, units) },
    };
  }

  if (tool === 'polygon' || tool === 'area') {
    if (pts.length < 3) return null;
    const ring = closeRing(pts);
    const coords = [ring];
    return {
      geometry: { type: 'Polygon', coordinates: coords },
      properties: {
        tool,
        label: measureLabel(tool, coords, units),
        areaM2: polygonAreaM2(coords),
        perimeterM: ringPerimeterM(ring),
      },
    };
  }

  if (tool === 'rectangle') {
    if (pts.length < 2) return null;
    const a = pts[0];
    const b = pts[pts.length - 1];
    if (a[0] === b[0] || a[1] === b[1]) return null;
    const ring = rectangleRing(a, b);
    const coords = [ring];
    return {
      geometry: { type: 'Polygon', coordinates: coords },
      properties: { tool, label: measureLabel('rectangle', coords, units) },
    };
  }

  if (tool === 'circle' || tool === 'radius') {
    if (pts.length < 2) return null;
    const c = pts[0];
    const e = pts[pts.length - 1];
    const radiusM = haversineM(c[0], c[1], e[0], e[1]);
    if (radiusM < 1) return null;
    const labelAz = bearingDeg(c[0], c[1], e[0], e[1]);
    const ring = geodesicCircle(c[0], c[1], radiusM);
    return {
      geometry: { type: 'Polygon', coordinates: [ring] },
      properties: {
        tool,
        center: c,
        radiusM,
        labelAz,
        label: measureLabel(tool, null, units, { radiusM }),
      },
    };
  }

  if (tool === 'rings') {
    if (!pts.length) return null;
    const c = pts[0];
    const radiiM = extras.radiiM?.length
      ? normalizeRadiiM(extras.radiiM)
      : pts.length >= 2
        ? scaleRings(haversineM(c[0], c[1], pts[pts.length - 1][0], pts[pts.length - 1][1]))
        : defaultRingRadiiM();
    return rebuildRings(
      { properties: { tool, center: c, radiiM, labelBearings: extras.labelBearings } },
      {},
      units
    );
  }

  if (tool === 'sector') {
    if (pts.length < 3) return null;
    const c = pts[0];
    const a = pts[1];
    const b = pts[2];
    const radiusM = haversineM(c[0], c[1], a[0], a[1]);
    if (radiusM < 1) return null;
    const startAz = bearingDeg(c[0], c[1], a[0], a[1]);
    const endAz = bearingDeg(c[0], c[1], b[0], b[1]);
    const ring = geodesicSector(c[0], c[1], radiusM, startAz, endAz);
    return {
      geometry: { type: 'Polygon', coordinates: [ring] },
      properties: {
        tool,
        center: c,
        radiusM,
        startAz,
        endAz,
        label: measureLabel('sector', null, units, { radiusM, startAz, endAz }),
      },
    };
  }

  return null;
}

export function vertexHandles(feature) {
  if (!feature?.geometry) return [];
  const tool = feature.properties?.tool;
  if (tool === 'label' || tool === 'arrow-head' || tool === 'vertex') return [];
  if (tool === 'point' || tool === 'text' || tool === 'icon' || tool === 'numbered' || tool === 'coord' || tool === 'high' || tool === 'low' || tool === 'wx' || tool === 'star') return [];

  if (tool === 'circle' || tool === 'radius') {
    const c =
      feature.properties?.center ||
      (feature.geometry?.type === 'Point' ? feature.geometry.coordinates : null);
    const r = feature.properties?.radiusM > 0 ? feature.properties.radiusM : 0;
    if (!c || !(r > 0)) return [];
    return [
      { i: 0, role: 'center', coord: c },
      { i: 1, role: 'radius', coord: destination(c[0], c[1], 90, r) },
    ];
  }

  if (tool === 'rings') {
    const c = feature.properties?.center;
    const radii = feature.properties?.radiiM || [];
    const bearings = normalizeLabelBearings(feature.properties?.labelBearings);
    if (!c || !radii.length) return [];
    const out = [{ i: 0, role: 'center', coord: c }];
    const az = bearings[0] ?? 90;
    for (let i = 0; i < radii.length; i++) {
      if (!(radii[i] > 0)) continue;
      out.push({ i: i + 1, role: 'radius', coord: destination(c[0], c[1], az, radii[i]) });
    }
    return out;
  }

  if (tool === 'sector') {
    const c = feature.properties?.center;
    const r = feature.properties?.radiusM;
    const a0 = feature.properties?.startAz;
    const a1 = feature.properties?.endAz;
    if (!c || !(r > 0) || a0 == null || a1 == null) return [];
    return [
      { i: 0, role: 'center', coord: c },
      { i: 1, role: 'start', coord: destination(c[0], c[1], a0, r) },
      { i: 2, role: 'end', coord: destination(c[0], c[1], a1, r) },
    ];
  }

  const g = feature.geometry;
  if (g.type === 'LineString') {
    return (g.coordinates || []).map((coord, i) => ({ i, role: 'vertex', coord }));
  }
  if (g.type === 'Polygon') {
    const ring = g.coordinates?.[0] || [];
    const n = ring.length > 1 && sameCoord(ring[0], ring[ring.length - 1]) ? ring.length - 1 : ring.length;
    const out = [];
    for (let i = 0; i < n; i++) out.push({ i, role: 'vertex', coord: ring[i] });
    return out;
  }
  return [];
}

export function applyVertexMove(feature, index, coord, units) {
  if (!feature?.geometry || !coord) return null;
  const tool = feature.properties?.tool;
  const props = { ...feature.properties };
  const u = units || props.units || 'km';

  if (tool === 'circle' || tool === 'radius') {
    let center = props.center
      ? props.center.slice()
      : feature.geometry?.type === 'Point'
        ? feature.geometry.coordinates.slice()
        : null;
    let radiusM = props.radiusM > 0 ? props.radiusM : 0;
    if (!center) return null;
    if (index === 0) center = coord;
    else {
      radiusM = haversineM(center[0], center[1], coord[0], coord[1]);
      if (radiusM < 1) return null;
    }
    props.center = center;
    props.radiusM = radiusM;
    if (index !== 0) props.labelAz = bearingDeg(center[0], center[1], coord[0], coord[1]);
    props.label = measureLabel(tool, null, u, { radiusM });
    const ring = geodesicCircle(center[0], center[1], radiusM);
    if (!ring) return null;
    return {
      geometry: { type: 'Polygon', coordinates: [ring] },
      properties: props,
    };
  }

  if (tool === 'rings') {
    let center = props.center ? props.center.slice() : null;
    let radiiM = Array.isArray(props.radiiM) ? props.radiiM.slice() : [];
    if (!center || !radiiM.length) return null;
    if (index === 0) center = coord;
    else {
      const ri = index - 1;
      if (ri < 0 || ri >= radiiM.length) return null;
      const nextR = haversineM(center[0], center[1], coord[0], coord[1]);
      if (!(nextR > 0)) return null;
      radiiM[ri] = nextR;
    }
    return rebuildRings({ ...feature, properties: props }, { center, radiiM, keepOrder: true }, u);
  }

  if (tool === 'sector') {
    let center = props.center ? props.center.slice() : null;
    let radiusM = props.radiusM;
    let startAz = props.startAz;
    let endAz = props.endAz;
    if (!center || !(radiusM > 0)) return null;
    if (index === 0) center = coord;
    else if (index === 1) {
      radiusM = haversineM(center[0], center[1], coord[0], coord[1]);
      if (radiusM < 1) return null;
      startAz = bearingDeg(center[0], center[1], coord[0], coord[1]);
    } else {
      endAz = bearingDeg(center[0], center[1], coord[0], coord[1]);
    }
    props.center = center;
    props.radiusM = radiusM;
    props.startAz = startAz;
    props.endAz = endAz;
    props.label = measureLabel('sector', null, u, { radiusM, startAz, endAz });
    return {
      geometry: { type: 'Polygon', coordinates: [geodesicSector(center[0], center[1], radiusM, startAz, endAz)] },
      properties: props,
    };
  }

  const g = feature.geometry;
  if (g.type === 'Point') {
    return { geometry: { type: 'Point', coordinates: coord }, properties: props };
  }

  if (g.type === 'LineString') {
    const coords = g.coordinates.slice();
    if (index < 0 || index >= coords.length) return null;
    coords[index] = coord;
    if (tool === 'distance' && coords.length >= 2) {
      props.distanceM = haversineM(coords[0][0], coords[0][1], coords[coords.length - 1][0], coords[coords.length - 1][1]);
      props.bearing = bearingDeg(coords[0][0], coords[0][1], coords[coords.length - 1][0], coords[coords.length - 1][1]);
    }
    props.label = measureLabel(tool === 'distance' ? 'distance' : tool, coords, u);
    return { geometry: { type: 'LineString', coordinates: coords }, properties: props };
  }

  if (g.type === 'Polygon') {
    const ring = g.coordinates[0].slice();
    const closed = ring.length > 1 && sameCoord(ring[0], ring[ring.length - 1]);
    const n = closed ? ring.length - 1 : ring.length;
    if (index < 0 || index >= n) return null;
    ring[index] = coord;
    if (closed && index === 0) ring[ring.length - 1] = coord;
    const coords = [ring];
    const labelTool = tool === 'rectangle' ? 'rectangle' : tool;
    props.label = measureLabel(labelTool, coords, u);
    if (tool === 'polygon' || tool === 'area') {
      props.areaM2 = polygonAreaM2(coords);
      props.perimeterM = ringPerimeterM(ring);
    }
    return { geometry: { type: 'Polygon', coordinates: coords }, properties: props };
  }

  return null;
}

function scaleRings(outerM) {
  const preset = defaultRingRadiiM();
  const max = preset[preset.length - 1];
  const k = outerM / max;
  if (!Number.isFinite(k) || k <= 0) return preset;
  return preset.map((r) => r * k);
}

export function normalizeRadiiM(list) {
  const out = [];
  for (const v of list || []) {
    const n = Number(v);
    if (Number.isFinite(n) && n > 0) out.push(n);
  }
  out.sort((a, b) => a - b);
  const uniq = [];
  for (const r of out) {
    if (!uniq.length || Math.abs(r - uniq[uniq.length - 1]) > 1) uniq.push(r);
  }
  return uniq.slice(0, 8);
}

export function normalizeLabelBearings(list) {
  const src = Array.isArray(list) && list.length ? list : [0, 90, 180, 270];
  const out = [];
  const seen = new Set();
  for (const v of src) {
    const n = ((Number(v) % 360) + 360) % 360;
    if (!Number.isFinite(n)) continue;
    const key = Math.round(n);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out.length ? out.slice(0, 8) : [0, 90, 180, 270];
}

export function parseRadiiInput(text, units) {
  const parts = String(text || '')
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const out = [];
  for (const p of parts) {
    const n = Number(p);
    if (!Number.isFinite(n) || n <= 0) continue;
    out.push(units === 'nm' ? n * NM_M : n * 1000);
  }
  return normalizeRadiiM(out);
}

export function parseBearingsInput(text) {
  const parts = String(text || '')
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  return normalizeLabelBearings(parts.map((p) => Number(p)));
}

export function radiiInputValue(radiiM, units) {
  if (!Array.isArray(radiiM) || !radiiM.length) return '';
  return radiiM
    .map((m) => (units === 'nm' ? (m / NM_M).toFixed(m / NM_M >= 10 ? 0 : 1) : (m / 1000).toFixed(m >= 10000 ? 0 : 1)))
    .join(', ');
}

export function bearingsInputValue(list) {
  return normalizeLabelBearings(list)
    .map((d) => String(Math.round(d)))
    .join(', ');
}

export function rebuildRings(feature, patch = {}, units) {
  const props = { ...(feature?.properties || {}), ...patch };
  delete props.keepOrder;
  const center = Array.isArray(props.center) ? props.center.slice() : null;
  const radiiM = patch.keepOrder
    ? (Array.isArray(props.radiiM) ? props.radiiM.map(Number).filter((n) => n > 0).slice(0, 8) : [])
    : normalizeRadiiM(props.radiiM);
  const labelBearings = normalizeLabelBearings(props.labelBearings);
  if (!center || !radiiM.length) return null;
  const u = units || props.units || 'km';
  props.center = center;
  props.radiiM = radiiM;
  props.labelBearings = labelBearings;
  props.tool = 'rings';
  props.units = u;
  props.label = measureLabel('rings', null, u, { radiiM });
  return {
    geometry: { type: 'MultiLineString', coordinates: radiiM.map((r) => geodesicCircle(center[0], center[1], r)) },
    properties: props,
  };
}

export function ringLabelFeatures(feature) {
  const props = feature?.properties || {};
  const c = props.center;
  const radii = normalizeRadiiM(props.radiiM);
  const bearings = normalizeLabelBearings(props.labelBearings);
  if (!c || !radii.length || !bearings.length) return [];
  const units = props.units || 'km';
  const out = [];
  for (let bi = 0; bi < bearings.length; bi++) {
    const az = bearings[bi];
    for (let ri = 0; ri < radii.length; ri++) {
      const r = radii[ri];
      const pt = destination(c[0], c[1], az, r);
      out.push({
        type: 'Feature',
        id: `${feature.id}__rl${bi}_${ri}`,
        properties: {
          tool: 'label',
          marker: 'label',
          parentId: feature.id,
          label: formatDist(r, units),
          stroke: props.stroke,
          fontSize: Math.max(10, (Number(props.fontSize) || 11) - 1),
        },
        geometry: { type: 'Point', coordinates: pt },
      });
    }
  }
  return out;
}

export function draftCollection(tool, pts, hover, units) {
  const all = hover ? [...pts, hover] : pts.slice();
  const features = [];
  if (!all.length) return { type: 'FeatureCollection', features };

  if (tool === 'point' || tool === 'text' || tool === 'icon' || tool === 'numbered' || tool === 'coord' || tool === 'high' || tool === 'low' || tool === 'wx' || tool === 'star') {
    features.push(ptFeature(all[0], tool));
    return { type: 'FeatureCollection', features };
  }

  if (tool === 'line' || tool === 'arrow' || tool === 'distance' || tool === 'callout') {
    if (all.length === 1) features.push(ptFeature(all[0], tool));
    if (all.length >= 2) {
      const built = buildCommitted(tool, all, units);
      if (built) features.push(asDraft(built, tool));
    }
    return { type: 'FeatureCollection', features };
  }

  if (tool === 'polyline' || tool === 'freehand' || tool === 'polygon' || tool === 'area') {
    if (all.length === 1) features.push(ptFeature(all[0], tool));
    else if (all.length >= 2 && (tool === 'polyline' || tool === 'freehand')) {
      features.push(asDraft({ geometry: { type: 'LineString', coordinates: all }, properties: { tool } }, tool));
    } else if (all.length >= 2 && (tool === 'polygon' || tool === 'area')) {
      const closed = [...all, pts[0] || all[0]];
      if (all.length >= 3) {
        const built = buildCommitted(tool, all, units);
        if (built) features.push(asDraft(built, tool));
        else {
          features.push(asDraft({ geometry: { type: 'LineString', coordinates: closed }, properties: { tool } }, tool));
        }
      } else {
        features.push(asDraft({ geometry: { type: 'LineString', coordinates: closed }, properties: { tool } }, tool));
      }
    }
    for (let i = 0; i < pts.length; i++) {
      features.push(ptFeature(pts[i], tool, i === 0 && pts.length >= 3 ? { closeTarget: 1 } : {}));
    }
    return { type: 'FeatureCollection', features };
  }

  if (tool === 'rectangle' && all.length >= 2) {
    const built = buildCommitted('rectangle', all, units);
    if (built) features.push(asDraft(built, tool));
    return { type: 'FeatureCollection', features };
  }

  if ((tool === 'circle' || tool === 'radius' || tool === 'rings') && all.length >= 1) {
    if (all.length === 1) features.push(ptFeature(all[0], tool));
    else {
      const built = buildCommitted(tool, all, units);
      if (built) {
        features.push(asDraft(built, tool));
        if (tool === 'rings') {
          for (const lbl of ringLabelFeatures({ id: 'draft', properties: { ...built.properties, units } })) {
            features.push({ ...lbl, properties: { ...lbl.properties, draft: 1 } });
          }
        }
      }
    }
    return { type: 'FeatureCollection', features };
  }

  if (tool === 'sector') {
    if (all.length === 1) features.push(ptFeature(all[0], tool));
    else if (all.length === 2) {
      const built = buildCommitted('radius', all, units);
      if (built) features.push(asDraft(built, tool));
    } else {
      const built = buildCommitted('sector', all, units);
      if (built) features.push(asDraft(built, tool));
    }
    return { type: 'FeatureCollection', features };
  }

  if (all.length) features.push(ptFeature(all[all.length - 1], tool));
  return { type: 'FeatureCollection', features };
}

function ptFeature(coord, tool, extra = {}) {
  return {
    type: 'Feature',
    properties: { tool, draft: 1, ...extra },
    geometry: { type: 'Point', coordinates: coord },
  };
}

function asDraft(built, tool) {
  return {
    type: 'Feature',
    properties: { ...built.properties, tool, draft: 1 },
    geometry: built.geometry,
  };
}

export function renderCollection(fc) {
  const features = [];
  for (const f of fc.features || []) {
    let geom = f.geometry;
    let props = f.properties || {};
    const tool = props.tool;
    if (tool === 'star' && geom?.type === 'Polygon') {
      const c = props.center || geom.coordinates?.[0]?.[0];
      if (c) {
        geom = { type: 'Point', coordinates: c };
        props = { ...props, marker: 'star' };
      }
    }
    const rendered = { ...f, geometry: geom, properties: props };
    features.push(rendered);
    if (tool === 'arrow' && geom?.type === 'LineString') {
      const head = arrowHeadPolygon(geom.coordinates);
      if (head) {
        features.push({
          type: 'Feature',
          id: `${f.id}__head`,
          properties: { ...props, tool: 'arrow-head', parentId: f.id, marker: 'arrow-head' },
          geometry: { type: 'Polygon', coordinates: [head] },
        });
      }
    }
    if (props.selected && tool !== 'label' && tool !== 'arrow-head') {
      for (const v of vertexHandles(rendered)) {
        features.push({
          type: 'Feature',
          id: `${f.id}__v${v.i}`,
          properties: {
            marker: 'vertex',
            tool: 'vertex',
            parentId: f.id,
            vi: v.i,
            role: v.role,
            selected: 1,
          },
          geometry: { type: 'Point', coordinates: v.coord },
        });
      }
    }
    if (tool === 'rings') {
      features.push(...ringLabelFeatures({ ...rendered, id: f.id }));
      continue;
    }
    if (
      tool === 'text' ||
      tool === 'point' ||
      tool === 'arrow-head' ||
      tool === 'label' ||
      tool === 'icon' ||
      tool === 'numbered' ||
      tool === 'coord' ||
      tool === 'high' ||
      tool === 'low' ||
      tool === 'wx' ||
      tool === 'star'
    ) {
      continue;
    }
    const extra = {
      center: props.center,
      radiusM: props.radiusM,
      radiiM: props.radiiM,
      startAz: props.startAz,
      endAz: props.endAz,
      labelAz: props.labelAz,
    };
    const lp = labelPointFor(tool, geom, extra);
    const text = props.label;
    if (lp && text) {
      features.push({
        type: 'Feature',
        id: `${f.id}__lbl`,
        properties: {
          ...f.properties,
          tool: 'label',
          marker: 'label',
          label: text,
          parentId: f.id,
        },
        geometry: { type: 'Point', coordinates: lp },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

export { closeRing };
