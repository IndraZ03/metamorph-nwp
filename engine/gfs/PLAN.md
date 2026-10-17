# GFS Tile Engine — PLAN
# Metamorph NWP Viewer — engine untuk layer GFS di peta.
# Dokumen ini: arsitektur + cara kerja + rollout. Implementasi ada di folder ini.

## Tujuan

Menyediakan layer GFS (NOAA Global Forecast System, 0.25°) untuk peta, dalam
bentuk **WebP tiles (XYZ)** yang sudah di-render sebelumnya (pre-rendered),
sehingga layer di peta cepat dan tidak perlu memproses GRIB di browser.

**Fokus dokumen ini: ENGINE saja.** Tidak ada visualisasi peta di sini.
Frontend (MapLibre/Leaflet) akan memakai manifest + tile URL dari engine ini
di tahap berikutnya.

## Variabel (7)

| Key | Variabel | Sumber GRIB | Satuan tampil | Rentang |
|---|---|---|---|---|
| temperature | Suhu 2 m | TMP 2 m | °C | −5 … 40 |
| dew_point | Titik embun 2 m | DPT 2 m | °C | −5 … 30 |
| rh | Kelembapan relatif 2 m | RH 2 m | % | 0 … 100 |
| pressure | Tekanan permukaan laut | PRMSL | hPa | 990 … 1020 |
| rain | Akumulasi hujan (APCP) | APCP surface | mm | 0 … 50 |
| cape | CAPE | CAPE surface | J/kg | 0 … 4000 |
| clouds | Tutupan awan total | TCDC entire atmosphere | % | 0 … 100 |

Catatan:
- `rain` adalah akumulasi pada jendela statistik GRIB (`stepRange`, misal
  0–1 jam di awal, 6 jam di forecast jauh). Manifest mencatat
  `rain_accum_hours` per timestep agar label frontend benar ("Hujan (6 jam)").
- `rain` di f000 tidak ada di file GFS (akumulasi 0 jam) → dirender 0 mm.
- `clouds` dirender putih dengan alpha = tutupan (langit cerah = transparan).

## Domain & timestep

- Domain: **Indonesia saja** — lat −11 … 6, lon 95 … 141.
- Run GFS: 4× sehari (00/06/12/18 UTC), tersedia ~3–4 jam setelah jam run.
- Timestep **maksimal**: per jam f000–f120 (121 step) + per 3 jam f123–f384 (88 step)
  = **209 timestep** per run, hingga 16 hari ke depan.
- Run time & valid time dicatat di manifest (`run`, `timesteps[].valid`).

## Sumber data — kenapa S3, bukan NOMADS CGI

- NOMADS `filter_gfs_0p25.pl` men-throttle agresif (setelah beberapa request
  cepat berturut-turut, semua request berikutnya 404) dan parameter subregion
  ditolak server saat ini.
- Engine memakai **AWS Open Data bucket NOAA** (`noaa-gfs-bdp-pds`):
  file `.idx` memberi offset byte tiap pesan GRIB → engine mengunduh HANYA
  byte-range 7 variabel yang dibutuhkan via HTTP Range request.
  Per timestep ≈ 5 MB (bukan ~150 MB file penuh).
- Pacing sopan: jeda antar request + retry dengan backoff. Jangan menaikkan
  paralelisme tanpa alasan — diblokir IP lebih mahal daripada lambat.

## Alur pipeline

```
find_latest_run()            # cek siklus terbaru via HEAD .idx (S3)
  → for fh in forecast_hours():
      download_timestep()    # .idx + Range GET 7 variabel → file .grb2 kecil
      decode_timestep()      # cfgrib → numpy grid, crop Indonesia, konversi satuan
      render_timestep()      # grid → canvas Web Mercator → potong jadi tiles WebP
      (hapus .grb2 mentah)
  → write_manifest()         # manifest.json + latest.json
  → cleanup()                # retensi: simpan N run terakhir
```

- Idempotent: run yang sudah diproses dilewati (cek manifest).
- Chunked: unduh/proses per chunk (default 8 timestep) agar disk temp kecil.
- Lock file: cegah dua pipeline jalan bersamaan.

## Tiles

- Skema **XYZ** (standar Leaflet/MapLibre), 256×256, **WebP**, proyeksi
  **Web Mercator (EPSG:3857)**.
- Zoom pre-render default: **0–6** (dapat diubah di `config.py`).
  Di luar bbox Indonesia, piksel transparan (alpha 0).
- Layout disk:
  `tiles/gfs/{run:%Y%m%d%H}/{valid:%Y%m%d%H}/{variable}/{z}/{x}/{y}.webp`
- Resampling: peta indeks bilinear per zoom dihitung sekali, dipakai ulang
  untuk semua timestep (cepat, deterministik).

## Server

`server.py` (stdlib `http.server`, tanpa dependensi):
- `GET /api/gfs/latest` → manifest run terbaru
- `GET /api/gfs/runs` → daftar run yang tersedia
- `GET /api/gfs/runs/{run}/manifest.json`
- `GET /tiles/gfs/...webp` → file tile (Cache-Control 1 jam)
- CORS terbuka agar frontend lain bisa memakainya.

## Auto-update

Jalankan `run.py all --run auto` lewat cron tiap 30 menit. Pipeline akan:
cek run terbaru → proses jika belum ada → update `latest.json`.
Contoh crontab ada di `README.md`.

## Rollout

1. `pip install -r requirements.txt`
2. Uji cepat: `python -m engine.gfs.run all --run auto --max-hours 2`
   (proses 2 timestep pertama, validasi tile + manifest)
3. Jalankan penuh: `python -m engine.gfs.run all --run auto`
4. Serve: `python -m engine.gfs.run serve --port 8080`
5. Cron 30 menit untuk auto-update.
6. Frontend (nanti, di luar scope ini): baca manifest → pasang layer XYZ
   per variabel dengan slider timestep (run + valid time dari manifest).

## File

- `config.py` — domain, variabel, colormap, zoom, path, pacing
- `source.py` — discovery run + download S3 (idx + Range)
- `decode.py` — cfgrib → grid Indonesia + konversi satuan
- `render.py` — resample Mercator + colormap + potong tiles WebP
- `pipeline.py` — orkestrasi + manifest + retensi + lock
- `server.py` — HTTP server tile + API manifest
- `run.py` — CLI
- `tests/` — unit test render (data sintetis) + manifest
