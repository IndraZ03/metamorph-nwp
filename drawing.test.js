import test from 'node:test';
import assert from 'node:assert/strict';
import {
  NM_M,
  backBearingDeg,
  bearingDeg,
  destination,
  formatDist,
  geodesicCircle,
  haversineM,
  lineLengthM,
  polygonAreaM2,
} from './src/services/drawing/geo.js';
import {
  applyVertexMove,
  buildCommitted,
  draftCollection,
  labelPointFor,
  measureLabel,
  parseBearingsInput,
  parseRadiiInput,
  renderCollection,
  ringLabelFeatures,
  vertexHandles,
} from './src/services/drawing/geometry.js';
import { nextNumber } from './src/services/drawing/tools.js';

test('1 NM is 1852 m', () => {
  assert.equal(NM_M, 1852);
});

test('equator 1 degree longitude is ~111.2 km', () => {
  const m = haversineM(0, 0, 1, 0);
  assert.ok(Math.abs(m - 111195) < 50);
});

test('true bearing north is 0 and east is 90', () => {
  assert.equal(Math.round(bearingDeg(0, 0, 0, 1)), 0);
  assert.equal(Math.round(bearingDeg(0, 0, 1, 0)), 90);
});

test('back bearing is geodesic reverse, not always +180 on the same call', () => {
  const fwd = bearingDeg(106.8, -6.2, 107.0, -6.1);
  const back = backBearingDeg(106.8, -6.2, 107.0, -6.1);
  const fromB = bearingDeg(107.0, -6.1, 106.8, -6.2);
  assert.equal(Math.round(back), Math.round(fromB));
  const naive = (fwd + 180) % 360;
  const d = Math.abs(back - naive) % 360;
  const diff = d > 180 ? 360 - d : d;
  assert.ok(diff < 5);
});

test('destination then haversine recovers distance', () => {
  const [lon, lat] = destination(106.8, -6.2, 45, 50 * NM_M);
  const m = haversineM(106.8, -6.2, lon, lat);
  assert.ok(Math.abs(m - 50 * NM_M) < 2);
});

test('geodesic circle is closed and roughly constant radius', () => {
  const ring = geodesicCircle(110, -5, 10000, 32);
  assert.equal(ring.length, 33);
  assert.equal(ring[0][0], ring[32][0]);
  const r = haversineM(110, -5, ring[8][0], ring[8][1]);
  assert.ok(Math.abs(r - 10000) < 3);
});

test('zero-length line is rejected', () => {
  assert.equal(buildCommitted('line', [[110, -5], [110, -5]], 'km'), null);
});

test('distance tool stores metres and true bearing', () => {
  const built = buildCommitted('distance', [
    [106.8, -6.2],
    [106.8, -5.2],
  ], 'km');
  assert.equal(built.geometry.type, 'LineString');
  assert.ok(built.properties.distanceM > 100000);
  assert.equal(Math.round(built.properties.bearing), 0);
  assert.match(built.properties.label, /km/);
  assert.match(built.properties.label, /0° T/);
});

test('radius tool keeps original centre and radiusM', () => {
  const built = buildCommitted('radius', [
    [110, -5],
    destination(110, -5, 90, 25 * NM_M),
  ], 'nm');
  assert.equal(built.properties.tool, 'radius');
  assert.deepEqual(built.properties.center, [110, -5]);
  assert.ok(Math.abs(built.properties.radiusM - 25 * NM_M) < 3);
  assert.match(built.properties.label, /NM/);
});

test('radius label sits on the arc, not the centre', () => {
  const tip = destination(110, -5, 90, 25 * NM_M);
  const built = buildCommitted('radius', [[110, -5], tip], 'nm');
  const lp = labelPointFor('radius', built.geometry, built.properties);
  const d = haversineM(110, -5, lp[0], lp[1]);
  assert.ok(Math.abs(d - 25 * NM_M) < 5);
  const fc = renderCollection({
    type: 'FeatureCollection',
    features: [{ id: 'rad1', type: 'Feature', geometry: built.geometry, properties: built.properties }],
  });
  const lbl = fc.features.find((f) => f.properties.marker === 'label');
  assert.ok(lbl);
  assert.ok(haversineM(110, -5, lbl.geometry.coordinates[0], lbl.geometry.coordinates[1]) > 1000);
});

test('polygon draft rubber-bands closed to the first vertex', () => {
  const draft = draftCollection(
    'polygon',
    [
      [110, -5],
      [110.2, -5],
      [110.1, -5.2],
    ],
    [110.05, -5.1],
    'km'
  );
  const poly = draft.features.find((f) => f.geometry.type === 'Polygon');
  assert.ok(poly);
  const ring = poly.geometry.coordinates[0];
  assert.equal(ring[0][0], ring[ring.length - 1][0]);
  assert.equal(ring[0][1], ring[ring.length - 1][1]);
  const close = draft.features.find((f) => f.properties.closeTarget === 1);
  assert.ok(close);
  assert.deepEqual(close.geometry.coordinates, [110, -5]);
});

test('rings default to 5/10/25/50/100 NM when only centre given via scale from outer', () => {
  const outer = destination(110, -5, 0, 100 * NM_M);
  const built = buildCommitted('rings', [[110, -5], outer], 'nm');
  assert.equal(built.geometry.type, 'MultiLineString');
  assert.equal(built.properties.radiiM.length, 5);
  assert.ok(Math.abs(built.properties.radiiM[0] - 5 * NM_M) < 3);
});

test('ring labels sit on each bearing, not the centre', () => {
  const built = buildCommitted('rings', [[110, -5], destination(110, -5, 0, 100 * NM_M)], 'nm');
  built.properties.labelBearings = [0, 90];
  const labels = ringLabelFeatures({ id: 'r1', properties: built.properties });
  assert.equal(labels.length, 10);
  for (const f of labels) {
    const d = haversineM(110, -5, f.geometry.coordinates[0], f.geometry.coordinates[1]);
    assert.ok(d > 1000);
  }
  const fc = renderCollection({
    type: 'FeatureCollection',
    features: [{ id: 'r1', type: 'Feature', geometry: built.geometry, properties: built.properties }],
  });
  const pts = fc.features.filter((f) => f.properties.marker === 'label');
  assert.equal(pts.length, 10);
  const centreLbl = pts.find((f) => haversineM(110, -5, f.geometry.coordinates[0], f.geometry.coordinates[1]) < 50);
  assert.equal(centreLbl, undefined);
});

test('ring radii and bearings parse from inspector text', () => {
  const radii = parseRadiiInput('5, 10, 25', 'nm');
  assert.equal(radii.length, 3);
  assert.ok(Math.abs(radii[0] - 5 * NM_M) < 1);
  const az = parseBearingsInput('0 90 180 270');
  assert.deepEqual(az.map((d) => Math.round(d)), [0, 90, 180, 270]);
});

test('polygon area and perimeter are positive', () => {
  const pts = [
    [110, -5],
    [110.2, -5],
    [110.2, -5.2],
    [110, -5.2],
  ];
  const built = buildCommitted('area', pts, 'km');
  assert.ok(built.properties.areaM2 > 1e8);
  assert.ok(built.properties.perimeterM > 80000);
  assert.equal(polygonAreaM2(built.geometry.coordinates), built.properties.areaM2);
});

test('formatDist switches km and NM', () => {
  assert.equal(formatDist(1852, 'nm'), '1.00 NM');
  assert.match(formatDist(1852, 'km'), /1\.9 km/);
});

test('polyline and polygon finish without dropping the last vertex', () => {
  const line = [
    [110, -5],
    [110.1, -5],
    [110.2, -5.1],
  ];
  const poly = [
    [110, -5],
    [110.2, -5],
    [110.2, -5.2],
  ];
  const builtLine = buildCommitted('polyline', line, 'km');
  const builtPoly = buildCommitted('polygon', poly, 'km');
  assert.equal(builtLine.geometry.coordinates.length, 3);
  assert.equal(builtPoly.geometry.coordinates[0].length, 4);
  assert.equal(buildCommitted('polygon', line.slice(0, 2), 'km'), null);
});

test('vertex handles omit polygon closing point and move updates geometry', () => {
  const built = buildCommitted(
    'polygon',
    [
      [110, -5],
      [110.2, -5],
      [110.2, -5.2],
      [110, -5.2],
    ],
    'km'
  );
  const feature = { id: 'f1', geometry: built.geometry, properties: built.properties };
  const handles = vertexHandles(feature);
  assert.equal(handles.length, 4);
  const moved = applyVertexMove(feature, 1, [110.3, -5], 'km');
  assert.equal(moved.geometry.coordinates[0][1][0], 110.3);
  assert.ok(moved.properties.areaM2 > 0);
});

test('polygon ring closes on first vertex', () => {
  const pts = [
    [110, -5],
    [110.2, -5],
    [110.1, -5.2],
  ];
  const built = buildCommitted('polygon', pts, 'km');
  const ring = built.geometry.coordinates[0];
  assert.equal(ring[0][0], ring[ring.length - 1][0]);
  assert.equal(ring[0][1], ring[ring.length - 1][1]);
  assert.equal(ring.length, 4);
});

test('star is a Point symbol, not a polygon', () => {
  const built = buildCommitted('star', [[110, -5]], 'km');
  assert.equal(built.geometry.type, 'Point');
  assert.equal(built.properties.tool, 'star');
  assert.equal(built.properties.marker, 'star');
  assert.deepEqual(built.geometry.coordinates, [110, -5]);
  assert.equal(vertexHandles({ geometry: built.geometry, properties: built.properties }).length, 0);
});

test('numbered / coord / callout / H L / wx commit', () => {
  const n1 = buildCommitted('numbered', [[110, -5]], 'km', { number: 3 });
  assert.equal(n1.properties.marker, 'numbered');
  assert.equal(n1.properties.number, 3);
  assert.equal(n1.properties.label, '3');
  const coord = buildCommitted('coord', [[106.8, -6.2]], 'km');
  assert.equal(coord.geometry.type, 'Point');
  assert.match(coord.properties.label, /6\.2000°S/);
  assert.match(coord.properties.dms, /S/);
  const call = buildCommitted('callout', [[110, -5], [110.1, -5.1]], 'km', { label: 'CB' });
  assert.equal(call.geometry.type, 'LineString');
  assert.equal(call.properties.marker, 'callout');
  assert.equal(call.properties.label, 'CB');
  const hi = buildCommitted('high', [[110, -5]], 'km');
  assert.equal(hi.properties.label, 'H');
  const lo = buildCommitted('low', [[110, -5]], 'km');
  assert.equal(lo.properties.label, 'L');
  const wx = buildCommitted('wx', [[110, -5]], 'km', { wxId: 'rain' });
  assert.equal(wx.properties.wxId, 'rain');
  const ic = buildCommitted('icon', [[110, -5]], 'km', { iconId: 'flag' });
  assert.equal(ic.properties.iconId, 'flag');
  assert.equal(nextNumber([{ properties: { tool: 'numbered', number: 2 } }]), 3);
});

test('polyline vertex move updates that coordinate', () => {
  const built = buildCommitted(
    'polyline',
    [
      [110, -5],
      [110.1, -5],
      [110.2, -5.1],
    ],
    'km'
  );
  const feature = { id: 'f1', geometry: built.geometry, properties: built.properties };
  assert.equal(vertexHandles(feature).length, 3);
  const moved = applyVertexMove(feature, 0, [109.9, -5], 'km');
  assert.deepEqual(moved.geometry.coordinates[0], [109.9, -5]);
});

test('measure label for a two-point line uses geodesic length', () => {
  const coords = [
    [100, 0],
    [101, 0],
  ];
  const m = lineLengthM(coords);
  const label = measureLabel('line', coords, 'km');
  assert.ok(m > 110000);
  assert.match(label, /km/);
});
