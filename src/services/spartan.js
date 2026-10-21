/**
 * BMKG SPARTAN fire-weather layers (Sistem Peringatan Dini Kebakaran Hutan dan Lahan).
 *
 * Pola tile terverifikasi upstream:
 *   https://spartan.bmkg.go.id/map/rgb_req/spartan/{product}/0/{start}/{end}/{z}/{x}/{y}.png
 *
 * Fakta terverifikasi:
 * - Tile PNG raster 4 warna (sudah diwarnai server), skema TMS (y dari selatan).
 * - Semantik parameter: {start} = tanggal run/inisialisasi model (YYYYMMDD0000);
 *   {end} = tanggal prakiraan/valid (YYYYMMDD0000).
 * - Selama navigasi timeline prakiraan, {start} tetap pada run model aktif,
 *   sedangkan {end} bergerak sesuai tanggal prakiraan yang dipilih.
 * - Endpoint menyajikan prakiraan lead 0 (hari-H) sampai lead 7 (mis. run 21 Okt melayani valid 21–28 Okt).
 * - Produk dc / isi / bui mengembalikan tile 200 seperti dmc / fwi / ffmc.
 * - Palet warna tile (analisis piksel): #006FFF, #4CE600, #FFFF01, #FF0000.
 */

// Produk FWI System (Canadian Forest Fire Weather Index System) yang dipakai SPARTAN.
// Urutan: tiga produk dari permintaan awal dulu, lalu tiga komponen sisanya.
export const SPARTAN_PRODUCTS = [
  {
    id: 'fwi',
    code: 'FWI',
    name: 'Fire Weather Index',
    desc: 'Indeks gabungan potensi kebakaran — ringkasan utama SPARTAN.',
  },
  {
    id: 'ffmc',
    code: 'FFMC',
    name: 'Fine Fuel Moisture Code',
    desc: 'Kadar air bahan bakar halus (dedaunan, ranting kecil) — cepat kering, cepat terbakar.',
  },
  {
    id: 'dmc',
    code: 'DMC',
    name: 'Duff Moisture Code',
    desc: 'Kadar air lapisan humus — bahan bakar sedang.',
  },
  {
    id: 'dc',
    code: 'DC',
    name: 'Drought Code',
    desc: 'Kekeringan lapisan dalam — indikator kemarau panjang.',
  },
  {
    id: 'isi',
    code: 'ISI',
    name: 'Initial Spread Index',
    desc: 'Kecepatan awal penyebaran api (kombinasi angin + FFMC).',
  },
  {
    id: 'bui',
    code: 'BUI',
    name: 'Buildup Index',
    desc: 'Total bahan bakar yang tersedia untuk terbakar (DMC + DC).',
  },
];

// Kelas bahaya SPARTAN (4 kelas). Warna diambil dari palet tile asli.
// Label kelas = skema 4 kelas SPARTAN; cocokkan dengan legenda di spartan.bmkg.go.id bila ragu.
export const SPARTAN_CLASSES = [
  { label: 'Rendah', color: '#006FFF' },
  { label: 'Sedang', color: '#4CE600' },
  { label: 'Tinggi', color: '#FFFF01' },
  { label: 'Ekstrem', color: '#FF0000' },
];

// Lead 0–7 terverifikasi pada 2026-10-21; setiap tanggal tetap diperiksa saat dipilih.
export const SPARTAN_FORECAST_DAYS = 7;
export const SPARTAN_MAX_RANGE_DAYS = SPARTAN_FORECAST_DAYS;

// Tile contoh di Kalimantan Tengah (darat) untuk verifikasi ketersediaan data.
const SAMPLE_TILE = { z: 8, x: 208, y: 128 };

/** Date -> 'YYYYMMDD0000' (SPARTAN memakai pukul 0000). */
export function formatSpartanDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}0000`;
}

/** 'YYYYMMDD0000' -> Date lokal. */
export function parseSpartanDate(s) {
  return new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8));
}

export function addDays(d, n) {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}

/** Tanggal hari ini dalam zona Asia/Jakarta (SPARTAN memakai tanggal lokal BMKG). */
export function todayWIB() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const get = (t) => +parts.find((p) => p.type === t).value;
  return new Date(get('year'), get('month') - 1, get('day'));
}

/** 'YYYYMMDD0000' -> label '17 Okt 2026' (id-ID). */
export function spartanDateLabel(s) {
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parseSpartanDate(s));
}

/** 'start' + 'end' -> label rentang '17–24 Okt 2026'. */
export function spartanRangeLabel(start, end) {
  const a = parseSpartanDate(start);
  const b = parseSpartanDate(end);
  const sameMonth =
    a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear();
  const dayFmt = new Intl.DateTimeFormat('id-ID', { day: 'numeric' });
  const fullFmt = new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
  if (sameMonth) {
    return `${dayFmt.format(a)}–${fullFmt.format(b)}`;
  }
  return `${fullFmt.format(a)} – ${fullFmt.format(b)}`;
}

/** Template tile MapLibre lewat proxy Vite (skema TMS, seperti layer satelit). */
export function spartanTileTemplate({ product, start, end }) {
  return `/api/proxy-spartan-tile/{z}/{x}/{y}.png?product=${product}&start=${start}&end=${end}`;
}

function spartanSampleTileUrl({ product, start, end }) {
  return `/api/proxy-spartan-tile/${SAMPLE_TILE.z}/${SAMPLE_TILE.x}/${SAMPLE_TILE.y}.png?product=${product}&start=${start}&end=${end}`;
}

/** Cek ketersediaan; hanya HTTP 404 berarti data belum tersedia. */
export async function verifySpartan({ product, start, end, signal }) {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(signal.reason);
  if (signal?.aborted) forwardAbort();
  else signal?.addEventListener('abort', forwardAbort, { once: true });
  const timeout = setTimeout(() => {
    controller.abort(new DOMException('Pemeriksaan KARHUTLA melewati batas waktu.', 'TimeoutError'));
  }, 10000);
  try {
    controller.signal.throwIfAborted();
    const res = await fetch(spartanSampleTileUrl({ product, start, end }), {
      signal: controller.signal,
      cache: 'no-store',
    });
    // Status saja sudah cukup; jangan unduh seluruh tile untuk discovery.
    if (res.body) void res.body.cancel().catch(() => {});
    controller.signal.throwIfAborted();
    if (res.status === 404) return false;
    if (!res.ok) {
      throw new Error(`Gagal memeriksa pembaruan KARHUTLA (HTTP ${res.status}).`);
    }
    return true;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', forwardAbort);
  }
}

/**
 * Cari run terbaru dari hari ini (WIB), maksimal lima kandidat secara default.
 * Mundur hanya bila lead 0 mengembalikan 404; kegagalan pemeriksaan diteruskan.
 * Mengembalikan Date untuk run terverifikasi, atau null bila semua 404.
 */
export async function findLatestValidSpartanStart(product = 'fwi', daysBack = 5, signal) {
  signal?.throwIfAborted();
  const base = todayWIB();
  for (let i = 0; i < daysBack; i++) {
    const start = addDays(base, -i);
    const startStr = formatSpartanDate(start);
    signal?.throwIfAborted();
    if (await verifySpartan({ product, start: startStr, end: startStr, signal })) {
      return start;
    }
  }
  return null;
}

/**
 * 8 frame prakiraan harian (lead 0..7).
 * startDate tetap pada tanggal run model, endDate dan token mengikuti tanggal valid.
 * Timestamps menunjukkan tengah malam WIB untuk sinkronisasi ForecastTimeline.
 */
export function buildSpartanFrames(start) {
  const startDate = formatSpartanDate(start);
  return Array.from({ length: SPARTAN_FORECAST_DAYS + 1 }, (_, i) => {
    const validDate = addDays(start, i);
    const endDate = formatSpartanDate(validDate);
    return {
      token: endDate,
      startDate,
      endDate,
      t:
        Date.UTC(
          +endDate.slice(0, 4),
          +endDate.slice(4, 6) - 1,
          +endDate.slice(6, 8)
        ) -
        7 * 3600000,
      label: spartanDateLabel(endDate),
      leadDay: i,
    };
  });
}
