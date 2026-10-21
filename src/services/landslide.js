export const LANDSLIDE_API = '/api/landslide/forecast';

export async function fetchLandslideMetadata(signal) {
  const response = await fetch(`${LANDSLIDE_API}/metadata`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('Data BNPB/ECMWF forward-24h belum tersedia');
  const data = await response.json();
  if (!data.run_id || !Array.isArray(data.steps)) throw new Error('Metadata longsor tidak valid');
  return data;
}

export function landslideTileUrl(metadata, step) {
  return metadata.tile_url.replaceAll('{run}', metadata.publication_id || metadata.run_id)
    .replaceAll('{step}', String(step));
}

export async function fetchLandslidePoint(metadata, step, lat, lon, signal) {
  const query = new URLSearchParams({ run: metadata.publication_id || metadata.run_id, step, lat, lon });
  const response = await fetch(`${LANDSLIDE_API}/point?${query}`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('Data titik tidak tersedia');
  return response.json();
}

export const formatWib = (iso) => iso ? new Date(iso).toLocaleString('id-ID', {
  timeZone: 'Asia/Jakarta', dateStyle: 'medium', timeStyle: 'short',
}) + ' WIB' : '—';

export function pointContent(data) {
  // DOM textContent, never interpret server content as HTML.
  const element = document.createElement('div');
  element.style.cssText = 'color:#0f172a;max-width:300px;font-size:12px;white-space:pre-line';
  const category = { waspada: 'Waspada', siaga: 'Siaga', bahaya: 'Bahaya', no_trigger: 'Tanpa pemicu (bukan berarti aman)', nodata: 'NoData — data tidak tersedia' };
  element.textContent = `Potensi Tanah Longsor — Eksperimental\n${category[data.category] || 'NoData'}\nRun: ${formatWib(data.run_time)}\nMulai: ${formatWib(data.forecast_start)}\nSelesai: ${formatWib(data.forecast_end)}\nHujan 24 jam ke depan: ${data.rainfall_24h_mm == null ? 'NoData' : data.rainfall_24h_mm.toFixed(1) + ' mm'}\nIndeks kerentanan rerata grid: ${data.hazard_index == null ? 'NoData' : data.hazard_index.toFixed(3)} (${data.hazard_class})\nBukan probabilitas atau peringatan resmi.`;
  return element;
}
