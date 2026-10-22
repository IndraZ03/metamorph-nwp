// Heuristic condition from parameters the model actually provides.
// No weather-code field exists in the tile contract, so categories come only
// from interval precipitation rate and total cloud cover. CAPE is never used:
// nothing in the source marks lightning, so there is no thunderstorm category.
// Day/night uses solar elevation at the point's own lat/lon and valid time.
// Thresholds are product rules, not model documentation — see docs/METEOGRAM.md.

const RAIN_MM_PER_HOUR = 0.1;
const HEAVY_RAIN_MM_PER_HOUR = 4;
const CLOUDY_PCT = 80;
const PARTLY_CLOUDY_PCT = 30;

/** Solar elevation in degrees. NOAA approximation; null when inputs are not finite. */
export function solarElevationDeg(lat, lon, timeMs) {
  if (![lat, lon, timeMs].every(Number.isFinite)) return null;
  const jd = timeMs / 86400000 + 2440587.5;
  const T = (jd - 2451545.0) / 36525;
  const deg = (x) => ((x % 360) + 360) % 360;
  const L0 = deg(280.46646 + 36000.76983 * T + 0.0003032 * T * T);
  const M = deg(357.52911 + 35999.05029 * T - 0.0001537 * T * T);
  const Mr = M * Math.PI / 180;
  const C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * Math.sin(Mr)
    + (0.019993 - 0.000101 * T) * Math.sin(2 * Mr) + 0.000289 * Math.sin(3 * Mr);
  const omega = 125.04 - 1934.136 * T;
  const lam = (L0 + C - 0.00569 - 0.00478 * Math.sin(omega * Math.PI / 180)) * Math.PI / 180;
  const eps = (23.439291 - 0.0130042 * T + 0.00256 * Math.cos(omega * Math.PI / 180)) * Math.PI / 180;
  const dec = Math.asin(Math.sin(eps) * Math.sin(lam));
  const y = Math.tan(eps / 2) ** 2;
  const Lr = L0 * Math.PI / 180;
  const e = 0.016708634;
  const eqTimeMin = 4 / Math.PI * 180 * (y * Math.sin(2 * Lr) - 2 * e * Math.sin(Mr)
    + 4 * e * y * Math.sin(Mr) * Math.cos(2 * Lr) - 0.5 * y * y * Math.sin(4 * Lr)
    - 1.25 * e * e * Math.sin(2 * Mr));
  const date = new Date(timeMs);
  const minutesUtc = date.getUTCHours() * 60 + date.getUTCMinutes() + date.getUTCSeconds() / 60;
  const trueSolarMin = ((minutesUtc + eqTimeMin + 4 * lon) % 1440 + 1440) % 1440;
  const hourAngle = (trueSolarMin / 4 - 180) * Math.PI / 180;
  const latr = lat * Math.PI / 180;
  const sinEl = Math.sin(latr) * Math.sin(dec) + Math.cos(latr) * Math.cos(dec) * Math.cos(hourAngle);
  return Math.asin(Math.max(-1, Math.min(1, sinEl))) * 180 / Math.PI;
}

/**
 * Derived weather category. Returns null when the point lacks the evidence the
 * rule needs — callers must show "Tidak tersedia", never a guessed icon.
 */
export function classifyWeatherCondition(point, lat, lon) {
  if (!point) return null;
  const rain = point.precipitationMm;
  const hours = point.precipitationIntervalHours;
  if (Number.isFinite(rain) && Number.isFinite(hours) && hours > 0 && rain / hours >= RAIN_MM_PER_HOUR) {
    return rain / hours >= HEAVY_RAIN_MM_PER_HOUR
      ? { id: 'heavy_rain', label: 'Hujan lebat (perkiraan dari laju interval)' }
      : { id: 'rain', label: 'Hujan (perkiraan dari akumulasi interval)' };
  }
  if (!Number.isFinite(point.totalCloudCoverPct)) return null;
  if (point.totalCloudCoverPct >= CLOUDY_PCT) return { id: 'cloudy', label: 'Berawan' };
  if (solarElevationDeg(lat, lon, point.t) == null) return null;
  const day = solarElevationDeg(lat, lon, point.t) > 0;
  if (point.totalCloudCoverPct >= PARTLY_CLOUDY_PCT) {
    return day
      ? { id: 'partly_cloudy_day', label: 'Berawan sebagian' }
      : { id: 'partly_cloudy_night', label: 'Berawan sebagian, malam' };
  }
  return day ? { id: 'clear_day', label: 'Cerah' } : { id: 'clear_night', label: 'Cerah, malam' };
}
