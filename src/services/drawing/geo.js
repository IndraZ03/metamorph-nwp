/** Geodesic helpers. 1 NM = 1852 m. True north bearing 0–360°. */

export const NM_M = 1852;
export const EARTH_M = 6371008.8;

export function toRad(d) {
  return (d * Math.PI) / 180;
}

export function toDeg(r) {
  return (r * 180) / Math.PI;
}

export function wrapLon(lon) {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

export function haversineM(lon1, lat1, lon2, lat2) {
  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const Δφ = toRad(lat2 - lat1);
  const Δλ = toRad(lon2 - lon1);
  const a =
    Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
  return 2 * EARTH_M * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Forward azimuth, true north, degrees 0–360. */
export function bearingDeg(lon1, lat1, lon2, lat2) {
  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const Δλ = toRad(lon2 - lon1);
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

/** Reverse geodesic bearing from B back to A — not always +180 on long tracks. */
export function backBearingDeg(lon1, lat1, lon2, lat2) {
  return bearingDeg(lon2, lat2, lon1, lat1);
}

export function destination(lon, lat, bearing, distM) {
  const δ = distM / EARTH_M;
  const θ = toRad(bearing);
  const φ1 = toRad(lat);
  const λ1 = toRad(lon);
  const sinφ2 = Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(θ);
  const φ2 = Math.asin(Math.min(1, Math.max(-1, sinφ2)));
  const λ2 =
    λ1 +
    Math.atan2(
      Math.sin(θ) * Math.sin(δ) * Math.cos(φ1),
      Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2)
    );
  return [wrapLon(toDeg(λ2)), toDeg(φ2)];
}

export function lineLengthM(coords) {
  let n = 0;
  for (let i = 1; i < coords.length; i++) {
    n += haversineM(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]);
  }
  return n;
}

/** Spherical polygon area (m²). Ring may be open or closed. */
export function ringAreaM2(ring) {
  if (!Array.isArray(ring) || ring.length < 3) return 0;
  const pts =
    ring.length > 1 && sameCoord(ring[0], ring[ring.length - 1]) ? ring.slice(0, -1) : ring;
  if (pts.length < 3) return 0;
  let total = 0;
  for (let i = 0; i < pts.length; i++) {
    const [lon1, lat1] = pts[i];
    const [lon2, lat2] = pts[(i + 1) % pts.length];
    total += toRad(lon2 - lon1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
  }
  return Math.abs((total * EARTH_M * EARTH_M) / 2);
}

export function polygonAreaM2(coords) {
  if (!coords?.length) return 0;
  let a = ringAreaM2(coords[0]);
  for (let i = 1; i < coords.length; i++) a -= ringAreaM2(coords[i]);
  return Math.max(0, a);
}

export function ringPerimeterM(ring) {
  if (!ring?.length) return 0;
  const closed =
    ring.length > 1 && sameCoord(ring[0], ring[ring.length - 1]) ? ring : [...ring, ring[0]];
  return lineLengthM(closed);
}

export function sameCoord(a, b, eps = 1e-12) {
  return Math.abs(a[0] - b[0]) < eps && Math.abs(a[1] - b[1]) < eps;
}

export function geodesicCircle(lon, lat, radiusM, steps = 64) {
  const coords = [];
  for (let i = 0; i <= steps; i++) {
    coords.push(destination(lon, lat, (360 * i) / steps, radiusM));
  }
  return coords;
}

export function geodesicSector(lon, lat, radiusM, startAz, endAz, steps = 48) {
  let span = (endAz - startAz + 360) % 360;
  if (span === 0) span = 360;
  const coords = [[lon, lat]];
  for (let i = 0; i <= steps; i++) {
    coords.push(destination(lon, lat, startAz + (span * i) / steps, radiusM));
  }
  coords.push([lon, lat]);
  return coords;
}

export function midpoint(lon1, lat1, lon2, lat2) {
  return destination(lon1, lat1, bearingDeg(lon1, lat1, lon2, lat2), haversineM(lon1, lat1, lon2, lat2) / 2);
}

export function offsetCoords(coords, dLon, dLat) {
  if (!Array.isArray(coords)) return coords;
  if (typeof coords[0] === 'number') return [wrapLon(coords[0] + dLon), coords[1] + dLat];
  return coords.map((c) => offsetCoords(c, dLon, dLat));
}

export function formatDist(m, units) {
  if (!Number.isFinite(m)) return '—';
  if (units === 'nm') {
    const nm = m / NM_M;
    return nm >= 10 ? `${nm.toFixed(1)} NM` : `${nm.toFixed(2)} NM`;
  }
  if (m >= 1000) return `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km`;
  return `${Math.round(m)} m`;
}

export function formatArea(m2, units) {
  if (!Number.isFinite(m2)) return '—';
  if (units === 'nm') {
    const nmi2 = m2 / (NM_M * NM_M);
    return nmi2 >= 10 ? `${nmi2.toFixed(1)} NM²` : `${nmi2.toFixed(2)} NM²`;
  }
  const km2 = m2 / 1e6;
  if (km2 >= 10) return `${km2.toFixed(1)} km²`;
  if (km2 >= 0.01) return `${km2.toFixed(2)} km²`;
  return `${Math.round(m2)} m²`;
}

export function formatBearing(deg) {
  if (!Number.isFinite(deg)) return '—';
  return `${((deg % 360) + 360) % 360 | 0}°`;
}

export function formatLatLon(lon, lat) {
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(4)}°${ns} ${Math.abs(lon).toFixed(4)}°${ew}`;
}

function dmsPart(value, pos, neg) {
  const abs = Math.abs(value);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = (mFloat - m) * 60;
  return `${d}°${String(m).padStart(2, '0')}'${s.toFixed(1)}"${value >= 0 ? pos : neg}`;
}

export function formatDMS(lon, lat) {
  return `${dmsPart(lat, 'N', 'S')} ${dmsPart(lon, 'E', 'W')}`;
}

export function parseRadius(value, units) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return units === 'nm' ? n * NM_M : n * 1000;
}

export function radiusDisplay(m, units) {
  if (!Number.isFinite(m)) return '';
  return units === 'nm' ? (m / NM_M).toFixed(1) : (m / 1000).toFixed(2);
}

const RING_PRESET_NM = [5, 10, 25, 50, 100];

export function defaultRingRadiiM() {
  return RING_PRESET_NM.map((nm) => nm * NM_M);
}
