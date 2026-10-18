/**
 * BMKG SPARTAN fire-weather layers (Sistem Peringatan Dini Kebakaran Hutan dan Lahan).
 *
 * Pola tile terverifikasi langsung ke upstream (2026-10-18):
 *   https://spartan.bmkg.go.id/map/rgb_req/spartan/{product}/0/{start}/{end}/{z}/{x}/{y}.png
 *
 * Fakta terverifikasi:
 * - Tile PNG raster 4 warna (sudah diwarnai server), skema TMS (y dari selatan).
 * - Tile = agregasi produk selama rentang [start, end]; rentang arbitrer bekerja
 *   (1 hari, 2 hari, 7 hari masing-masing menghasilkan gambar berbeda).
 * - Batas keras: end - start <= 7 hari (rentang 14 hari -> 404).
 * - Data terbit dengan lag ~1 hari (2026-10-18: start 18 Okt -> 404, start 17 Okt -> 200).
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

export const SPARTAN_MAX_RANGE_DAYS = 7;

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

/** Cek satu kombinasi produk + rentang benar-benar tersedia (HTTP 200). */
export async function verifySpartan({ product, start, end }) {
  try {
    const res = await fetch(spartanSampleTileUrl({ product, start, end }));
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Cari tanggal mulai terbaru yang datanya tersedia, mundur dari kemarin (WIB).
 * SPARTAN terbit dengan lag ~1 hari, jadi kemarin adalah kandidat pertama.
 * Mengembalikan Date; fallback kemarin bila semua kandidat gagal (modal akan
 * menampilkan error verifikasi).
 */
export async function findLatestValidSpartanStart(product = 'dmc', daysBack = 5) {
  const base = addDays(todayWIB(), -1);
  for (let i = 0; i < daysBack; i++) {
    const start = addDays(base, -i);
    const startStr = formatSpartanDate(start);
    const endStr = formatSpartanDate(addDays(start, SPARTAN_MAX_RANGE_DAYS));
    if (await verifySpartan({ product, start: startStr, end: endStr })) {
      return start;
    }
  }
  return base;
}
