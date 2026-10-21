export const FLOOD_API = '/api/flood/forecast';

export const REQUIRED_FLOOD_DISCLAIMER =
  'Produk ini merupakan indikasi potensi banjir berdasarkan prakiraan curah hujan ECMWF dan informasi spasial InaRISK BNPB. Produk belum menggantikan peringatan dini resmi dan tidak merepresentasikan prediksi pasti lokasi, waktu, atau kedalaman genangan.';

export async function fetchFloodMetadata(signal) {
  const response = await fetch(`${FLOOD_API}/metadata`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('Data banjir ECMWF/InaRISK belum tersedia');
  const data = await response.json();
  if (data.product !== 'indonesia_flood_potential'
      || !/^\d{8}T\d{2}-[a-f0-9]{16}$/.test(data.publication_id || '')
      || !Number.isFinite(Date.parse(data.run_time))
      || !Array.isArray(data.bbox) || data.bbox.length !== 4 || !data.bbox.every(Number.isFinite)
      || !Number.isInteger(data.minzoom) || !Number.isInteger(data.maxzoom)
      || !Array.isArray(data.steps) || !data.steps.every((row) => Number.isInteger(row.step)
        && row.step >= 0 && typeof row.ready === 'boolean' && Number.isFinite(Date.parse(row.valid_time)))) {
    throw new Error('Metadata banjir tidak valid');
  }
  return data;
}

export function floodTileUrl(metadata, step, indicator = 'rainfall') {
  const pub = encodeURIComponent(metadata.publication_id || metadata.run_id);
  const validIndicator = ['rainfall', 'hazard', 'vulnerability'].includes(indicator) ? indicator : 'rainfall';
  return `${FLOOD_API}/tile/${pub}/${encodeURIComponent(step)}/{z}/{x}/{y}.webp?indicator=${validIndicator}`;
}

export async function fetchFloodPoint(metadata, step, lat, lon, signal) {
  const query = new URLSearchParams({
    run: metadata.publication_id || metadata.run_id,
    step: String(step),
    lat: String(lat),
    lon: String(lon),
  });
  const response = await fetch(`${FLOOD_API}/point?${query}`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('Data titik banjir tidak tersedia');
  return response.json();
}

export const formatWib = (iso) => (iso ? new Date(iso).toLocaleString('id-ID', {
  timeZone: 'Asia/Jakarta', dateStyle: 'medium', timeStyle: 'short',
}) + ' WIB' : '—');

export function pointContent(data) {
  const container = document.createElement('div');
  container.style.cssText = 'color:#0f172a;max-width:320px;font-size:12px;line-height:1.45;white-space:pre-line;font-family:sans-serif;';

  const r24 = data.rainfall_p24_mm == null ? 'NoData' : `${data.rainfall_p24_mm.toFixed(1)} mm (unverified class)`;
  const ant7 = data.antecedent_7d_mm == null ? 'NoData' : `${data.antecedent_7d_mm.toFixed(1)} mm (raw)`;
  const ar7 = data.ar7_weighted_mm == null ? 'Belum terkonfigurasi (decay tidak terverifikasi)' : `${data.ar7_weighted_mm.toFixed(1)} mm`;
  const hz = data.hazard_index == null ? 'NoData' : Number(data.hazard_index).toFixed(3);
  const vn = data.vulnerability_index == null ? 'NoData' : Number(data.vulnerability_index).toFixed(3);

  const bayuStatus = data.bayuadji_model?.status || 'NOT_CONFIGURED';
  const bayuProb = data.bayuadji_model?.probability != null ? `${(data.bayuadji_model.probability * 100).toFixed(1)}%` : 'null (nonaktif)';

  const lines = [
    'Potensi Banjir — Eksperimental',
    `Awal Jendela: ${formatWib(data.window_start)}`,
    `Akhir Jendela: ${formatWib(data.window_end)}`,
    '----------------------------------------',
    `P24 Trailing: ${r24}`,
    `Antecedent 7-hari: ${ant7}`,
    `AR7 Tertimbang: ${ar7}`,
    `Indeks Bahaya BNPB (0-1): ${hz}`,
    `Indeks Kerentanan BNPB (0-1): ${vn}`,
    `Model Bayuadji: ${bayuStatus} (Probabilitas: ${bayuProb})`,
    '----------------------------------------',
    REQUIRED_FLOOD_DISCLAIMER
  ];

  container.textContent = lines.join('\n');
  return container;
}
