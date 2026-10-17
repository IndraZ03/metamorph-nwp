/**
 * User overlays: GeoJSON & GPX handling for the map.
 *
 * Pure logic (no MapLibre dependency) so it can be unit-tested:
 * - parseGeoJSON(text)  -> normalized FeatureCollection
 * - parseGPX(text)      -> FeatureCollection (tracks, routes, waypoints)
 * - bboxOf(featureCollection) -> [minLon, minLat, maxLon, maxLat]
 * - layerDefs(id, color) -> MapLibre layer definitions (fill / line / circle)
 */

export const USER_LAYER_COLORS = [
  '#38bdf8', // sky
  '#f472b6', // pink
  '#facc15', // yellow
  '#4ade80', // green
  '#fb923c', // orange
  '#a78bfa', // violet
  '#2dd4bf', // teal
  '#f87171', // red
];

export function colorFor(index) {
  return USER_LAYER_COLORS[index % USER_LAYER_COLORS.length];
}

/* ------------------------------------------------------------------ */
/* GeoJSON                                                             */
/* ------------------------------------------------------------------ */

function isFiniteNumber(v) {
  return typeof v === 'number' && Number.isFinite(v);
}

/** Recursively validate a coordinates array: every leaf must be [lon, lat(, ...)] numbers. */
function validCoords(coords) {
  if (!Array.isArray(coords) || coords.length === 0) return false;
  if (isFiniteNumber(coords[0])) {
    return isFiniteNumber(coords[0]) && isFiniteNumber(coords[1]);
  }
  return coords.every(validCoords);
}

function validGeometry(geom) {
  if (!geom || typeof geom.type !== 'string') return false;
  if (geom.type === 'GeometryCollection') {
    return (
      Array.isArray(geom.geometries) &&
      geom.geometries.length > 0 &&
      geom.geometries.every(validGeometry)
    );
  }
  return validCoords(geom.coordinates);
}

/** Flatten a GeometryCollection into one feature per geometry. */
function flattenGeometry(geom, properties) {
  if (geom.type === 'GeometryCollection') {
    return geom.geometries.flatMap((g) => flattenGeometry(g, properties));
  }
  return [{ type: 'Feature', properties: { ...properties }, geometry: geom }];
}

export function parseGeoJSON(text) {
  let obj;
  try {
    obj = JSON.parse(text);
  } catch {
    throw new Error('Teks bukan JSON yang valid.');
  }

  let features = [];
  if (obj?.type === 'FeatureCollection' && Array.isArray(obj.features)) {
    features = obj.features;
  } else if (obj?.type === 'Feature') {
    features = [obj];
  } else if (obj && typeof obj.type === 'string') {
    // Bare geometry (Point / LineString / Polygon / Multi* / GeometryCollection)
    features = flattenGeometry(obj, {});
  } else {
    throw new Error('GeoJSON harus berupa FeatureCollection, Feature, atau Geometry.');
  }

  const out = [];
  for (const f of features) {
    if (!f || f.type !== 'Feature' || !validGeometry(f.geometry)) continue;
    out.push({
      type: 'Feature',
      properties: f.properties && typeof f.properties === 'object' ? f.properties : {},
      geometry: f.geometry,
    });
  }
  if (out.length === 0) {
    throw new Error('Tidak ada fitur dengan geometri valid di GeoJSON ini.');
  }
  return { type: 'FeatureCollection', features: out };
}

/* ------------------------------------------------------------------ */
/* GPX                                                                 */
/* ------------------------------------------------------------------ */

function directChildText(parent, tag) {
  for (const child of parent.childNodes) {
    if (child.nodeType === 1 && child.localName === tag) return child.textContent.trim();
  }
  return '';
}

function pointCoords(pt) {
  const lat = parseFloat(pt.getAttribute('lat'));
  const lon = parseFloat(pt.getAttribute('lon'));
  if (!isFiniteNumber(lat) || !isFiniteNumber(lon)) return null;
  return [lon, lat];
}

function parseGPX(text) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length > 0) {
    throw new Error('File bukan XML/GPX yang valid.');
  }
  const gpx = doc.getElementsByTagNameNS('*', 'gpx')[0];
  if (!gpx) throw new Error('File XML ini bukan GPX (tag <gpx> tidak ditemukan).');

  const features = [];

  // Tracks: each segment -> one LineString feature
  for (const trk of gpx.getElementsByTagNameNS('*', 'trk')) {
    const name = directChildText(trk, 'name') || 'Track';
    let segIndex = 0;
    for (const seg of trk.getElementsByTagNameNS('*', 'trkseg')) {
      const coords = [];
      for (const pt of seg.getElementsByTagNameNS('*', 'trkpt')) {
        const c = pointCoords(pt);
        if (c) coords.push(c);
      }
      if (coords.length >= 2) {
        features.push({
          type: 'Feature',
          properties: { name: segIndex === 0 ? name : `${name} (${segIndex + 1})`, kind: 'track' },
          geometry: { type: 'LineString', coordinates: coords },
        });
      }
      segIndex += 1;
    }
  }

  // Routes
  for (const rte of gpx.getElementsByTagNameNS('*', 'rte')) {
    const name = directChildText(rte, 'name') || 'Route';
    const coords = [];
    for (const pt of rte.getElementsByTagNameNS('*', 'rtept')) {
      const c = pointCoords(pt);
      if (c) coords.push(c);
    }
    if (coords.length >= 2) {
      features.push({
        type: 'Feature',
        properties: { name, kind: 'route' },
        geometry: { type: 'LineString', coordinates: coords },
      });
    }
  }

  // Waypoints
  for (const wpt of gpx.getElementsByTagNameNS('*', 'wpt')) {
    const c = pointCoords(wpt);
    if (!c) continue;
    features.push({
      type: 'Feature',
      properties: {
        name: directChildText(wpt, 'name') || 'Waypoint',
        ele: directChildText(wpt, 'ele') || undefined,
        time: directChildText(wpt, 'time') || undefined,
        kind: 'waypoint',
      },
      geometry: { type: 'Point', coordinates: c },
    });
  }

  if (features.length === 0) {
    throw new Error('Tidak ada track, route, atau waypoint di file GPX ini.');
  }
  return { type: 'FeatureCollection', features };
}

/** Detect format and parse. `fileName` (optional) helps pick GPX vs GeoJSON. */
export function parseUserFile(text, fileName = '') {
  const looksXml = /^\s*<\?xml|^\s*<gpx[\s>]/.test(text);
  if (fileName.toLowerCase().endsWith('.gpx') || looksXml) {
    return { kind: 'gpx', geojson: parseGPX(text) };
  }
  return { kind: 'geojson', geojson: parseGeoJSON(text) };
}

/* ------------------------------------------------------------------ */
/* BBox & MapLibre layers                                              */
/* ------------------------------------------------------------------ */

export function bboxOf(fc) {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  const walk = (coords) => {
    if (!Array.isArray(coords)) return;
    if (isFiniteNumber(coords[0]) && isFiniteNumber(coords[1])) {
      minLon = Math.min(minLon, coords[0]);
      maxLon = Math.max(maxLon, coords[0]);
      minLat = Math.min(minLat, coords[1]);
      maxLat = Math.max(maxLat, coords[1]);
      return;
    }
    coords.forEach(walk);
  };
  for (const f of fc.features) {
    if (f.geometry?.type === 'GeometryCollection') {
      f.geometry.geometries?.forEach((g) => walk(g.coordinates));
    } else {
      walk(f.geometry?.coordinates);
    }
  }
  if (!Number.isFinite(minLon)) return null;
  return [minLon, minLat, maxLon, maxLat];
}

export function countByGeometry(fc) {
  const counts = { Point: 0, LineString: 0, Polygon: 0, Other: 0, total: 0 };
  for (const f of fc.features) {
    const t = f.geometry?.type;
    if (t === 'Point' || t === 'MultiPoint') counts.Point += 1;
    else if (t === 'LineString' || t === 'MultiLineString') counts.LineString += 1;
    else if (t === 'Polygon' || t === 'MultiPolygon') counts.Polygon += 1;
    else if (t) counts.Other += 1;
  }
  counts.total = counts.Point + counts.LineString + counts.Polygon + counts.Other;
  return counts;
}

/** MapLibre layer definitions for one user layer (fill + line + circle). */
export function layerDefs(layerId, color) {
  const source = `user-${layerId}`;
  return [
    {
      id: `${source}-fill`,
      type: 'fill',
      source,
      filter: ['any', ['==', '$type', 'Polygon'], ['==', '$type', 'MultiPolygon']],
      paint: {
        'fill-color': color,
        'fill-opacity': 0.25,
        'fill-outline-color': color,
      },
    },
    {
      id: `${source}-line`,
      type: 'line',
      source,
      filter: [
        'any',
        ['==', '$type', 'LineString'],
        ['==', '$type', 'MultiLineString'],
        ['==', '$type', 'Polygon'],
        ['==', '$type', 'MultiPolygon'],
      ],
      paint: {
        'line-color': color,
        'line-width': 2.5,
        'line-opacity': 0.95,
      },
    },
    {
      id: `${source}-circle`,
      type: 'circle',
      source,
      filter: ['any', ['==', '$type', 'Point'], ['==', '$type', 'MultiPoint']],
      paint: {
        'circle-color': color,
        'circle-radius': 5,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
        'circle-opacity': 0.95,
      },
    },
  ];
}
