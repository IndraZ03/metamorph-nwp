# GFS Tile Engine — Metamorph NWP

Engine untuk layer GFS di peta: unduh GFS 0.25° (NOAA), olah jadi **WebP tiles
(XYZ, Web Mercator)** khusus domain Indonesia, plus manifest run/valid time.
**Engine saja — tanpa visualisasi.** Frontend memakai manifest + tile URL.

Detail arsitektur: baca `PLAN.md`.

## Variabel

temperature (°C) · dew_point (°C) · rh (%) · pressure (hPa) · rain (mm,
akumulasi APCP) · cape (J/kg) · clouds (%)

## Timestep

Maksimal: per jam f000–f120 + per 3 jam f123–f384 = **209 timestep** per run.
Run baru tiap 6 jam (00/06/12/18 UTC).

## Jalankan

```bash
cd <repo>
python -m venv .venv && source .venv/bin/activate
pip install -r engine/gfs/requirements.txt

# cek run terbaru yang tersedia
python -m engine.gfs.run latest

# uji cepat: proses 2 timestep pertama saja
python -m engine.gfs.run all --run auto --max-hours 1

# proses satu run penuh
python -m engine.gfs.run all --run auto

# serve tiles + manifest API
python -m engine.gfs.run serve --port 8080
```

## Auto-update (cron, tiap 30 menit)

```cron
*/30 * * * * cd /path/to/metamorph-nwp && /path/to/.venv/bin/python -m engine.gfs.run all --run auto >> /var/log/gfs-engine.log 2>&1
```

Pipeline idempotent: run yang sudah lengkap dilewati. Retensi default:
2 run terbaru (lihat `RETENTION_RUNS` di `config.py`).

## API server

- `GET /api/gfs/latest` — manifest run terbaru
- `GET /api/gfs/runs` — daftar run
- `GET /api/gfs/runs/<run>/manifest.json`
- `GET /tiles/gfs/<run>/<valid>/<variable>/<z>/<x>/<y>.webp`

Contoh pemakaian dari frontend (nanti): baca `latest.json`, ambil
`tile_url_template`, ganti `{run}` / `{valid}` / `{variable}` / `{z}/{x}/{y}`.

## Struktur data

```
data/gfs/
  tiles/gfs/<run YYYYMMDDHH>/<valid YYYYMMDDHH>/<variable>/<z>/<x>/<y>.webp
  tiles/gfs/<run>/manifest.json
  latest.json
```

## Tes

```bash
python -m unittest discover -s engine/gfs/tests -v
```

## Catatan penting

- **Jangan menaikkan paralelisme download sembarangan.** NOMADS/S3
  men-throttle klien agresif; pacing (delay + retry + backoff) ada di
  `config.py` dan sengaja dibuat sopan.
- APCP di f000 tidak ada di file GFS → dirender 0 mm.
- `rain_step_range` per timestep tercatat di manifest (jendela akumulasi
  membesar di forecast jauh, misal 6 jam) — frontend harus menampilkannya
  di label layer.
