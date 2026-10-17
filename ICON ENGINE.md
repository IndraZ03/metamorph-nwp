# ICON NWP Processing Engine & WebP Tile Pipeline

Backend engine pengolahan data cuaca numerik model **ICON (DWD Open Data)** khusus **Domain Indonesia**. Data numerik GRIB2 di-pre-render menjadi piramida citra **WebP Tiles (XYZ)** sebelum disajikan ke frontend, memastikan visualisasi peta bebas lag di sisi client.

---

## 1. Spesifikasi Teknis

- **Model**: ICON Global (Icosahedral Nonhydrostatic, DWD Deutscher Wetterdienst).
- **Resolusi Asli**: R03B07 (~13 km global, 2.949.120 sel tidak terstruktur).
- **Domain Ekstraksi**: Indonesia Bounding Box (Lat `-15.0°` s/d `12.0° N`, Lon `88.0°` s/d `148.0° E`).
- **Target Grid**: Regular Mercator/Equirectangular 541 × 1201 piksel (resolusi spatial `0.05°` ≈ 5.5 km).
- **Format Output**: Slippy Map WebP Tiles (`/{z}/{x}/{y}.webp`), Zoom 4 s/d 7.
- **Ukuran per Tile**: Rata-rata 300 s/d 800 bytes (hemat bandwidth dan memory).
- **Siklus Model (Runs)**: `00`, `06`, `12`, `18` UTC.
  - Run `00` & `12` UTC: Timestep 000–078 (interval 1 jam) + 081–180 (interval 3 jam) = **113 timesteps** (Maksimal 180 jam).
  - Run `06` & `18` UTC: Timestep 000–048 (interval 1 jam) + 051–120 (interval 3 jam) = **73 timesteps** (Maksimal 120 jam).

---

## 2. Parameter Meteorologi Didukung

| Parameter ID | Nama Parameter | Folder DWD | Variable DWD | Satuan Asli | Satuan Output | Rentang Nilai | Sifat |
|---|---|---|---|---|---|---|---|
| `t_2m` | 2m Temperature | `t_2m/` | `T_2M` | Kelvin ($K$) | Celsius (°C) | $-10.0$ s/d $45.0$ °C | Instantaneous |
| `relhum_2m` | 2m Relative Humidity | `relhum_2m/` | `RELHUM_2M` | $\%$ | $\%$ | $0.0$ s/d $100.0$ % | Instantaneous |
| `tot_prec` | Rain Accumulation | `tot_prec/` | `TOT_PREC` | $kg/m^2$ | $mm$ | $0.0$ s/d $250.0$ mm | Akumulasi sejak $t=0$ |
| `pmsl` | Sea Level Pressure | `pmsl/` | `PMSL` | $Pa$ | $hPa$ | $996.0$ s/d $1020.0$ hPa | Instantaneous |
| `td_2m` | 2m Dew Point | `td_2m/` | `TD_2M` | Kelvin ($K$) | Celsius (°C) | $10.0$ s/d $32.0$ °C | Instantaneous |
| `cape_ml` | CAPE (Mixed Layer) | `cape_ml/` | `CAPE_ML` | $J/kg$ | $J/kg$ | $0.0$ s/d $4000.0$ J/kg | Instantaneous |
| `clct` | Total Cloud Cover | `clct/` | `CLCT` | $\%$ | $\%$ | $0.0$ s/d $100.0$ % | Instantaneous |

---

## 3. Skema Colormap & Transparansi

Setiap parameter dipetakan ke Look-Up Table (LUT) 256-level RGBA:
- `t_2m`: Biru tua (-10°C) → Cyan (0°C) → Hijau (15°C) → Kuning (24°C) → Oranye (30°C) → Merah (37°C) → Ungu (45°C). Alpha uniform 70%.
- `relhum_2m`: Transparan di <35%, hijau muda (50%) → toska (70%) → biru pekat (85%) → indigo (100%).
- `tot_prec`: Strict zero-threshold. 0 s/d 0.5 mm 100% transparan. Hujan ringan (2 mm, biru muda) → sedang (10 mm, toska) → lebat (25 mm, hijau) → sangat lebat (50 mm, kuning) → ekstrem (>100 mm, ungu pekat).
- `pmsl`: Gradien isobar tropis. Violet (<1000 hPa) → cyan → hijau netral → amber → merah (>1016 hPa).
- `td_2m`: Skala kelembapan termal tropis. Kering (khaki) → nyaman (hijau) → lembap (cyan) → gerah (biru pekat) → ekstrem (violet).
- `cape_ml`: Indikator konveksi. <100 J/kg transparan. Hijau muda (500) → kuning (1000) → oranye (2000) → merah (3000) → neon fuchsia (>4000).
- `clct`: Awan putih non-linear alpha ramp. <12% transparan, gradasi opacity hingga 85% pada tutupan awan 100%.

---

## 4. Struktur File Engine

```
backend/
├── app.py                      # FastAPI server (Manifest & WebP tile endpoints)
├── requirements.txt            # Dependensi Python
├── run_engine.py               # CLI runner & daemon entrypoint
└── engine/
    ├── __init__.py
    ├── config.py               # Konfigurasi koordinat, bounding box, resolusi, parameter
    ├── colormaps.py            # Matriks LUT RGBA 256-level & fungsi apply_colormap
    ├── grid.py                 # Invariant coordinate loader & cKDTree spatial indexer
    ├── downloader.py           # In-memory streaming bz2 decompressor & DWD crawler
    ├── processor.py            # Ekstraksi array eccodes, konversi unit, interpolasi grid
    ├── tiler.py                # Pemotong piramida Slippy Map XYZ & WebP encoder
    ├── manifest.py             # Metadata generator & auto-pruning folder run lama
    └── scheduler.py            # Pipeline runner & background poller realtime
```

---

## 5. Alur Kerja Engine (Pipeline Workflow)

1. **Spatial Pre-indexing (`grid.py`)**:
   - Sekali saat inisialisasi, engine mengunduh koordinat `CLAT` dan `CLON` dari DWD.
   - 124.765 sel yang berada di dalam domain Indonesia disaring.
   - Bobot interpolasi Inverse Distance Weighting (IDW, $k=4$) dihitung via `scipy.spatial.cKDTree` ke grid regular 541 × 1201 titik.
   - Hasil di-cache ke `data/cache/icon_indo_grid.npz`. Interpolasi runtime berjalan <50 milidetik.

2. **Downloader Tanpa Disk I/O Mentah (`downloader.py`)**:
   - File `.grib2.bz2` diunduh lewat stream HTTP.
   - Langsung didekompresi di memori RAM via `bz2.decompress()`. File GRIB2 mentah tidak disimpan ke disk.

3. **Tile Generation Paralel (`tiler.py`)**:
   - Matriks 2D dipotong per tile $256 \times 256$ piksel pada zoom 4, 5, 6, dan 7.
   - Proses rendering dan kompresi WebP (Q=85) dieksekusi paralel menggunakan `ThreadPoolExecutor`.
   - Tile kosong / di luar daratan Indonesia yang 100% transparan dilewati untuk menghemat disk.

4. **Manifest Incremental (`manifest.py`)**:
   - Setelah setiap timestep selesai di-render, `manifest.json` langsung diperbarui.
   - Frontend dapat langsung menampilkan timestep awal tanpa harus menunggu jam 180 selesai diproses.

5. **Disk Retention Management**:
   - Hanya 2 run siklus terbaru yang disimpan di disk (`RETENTION_RUNS = 2`).
   - Run yang lebih lama dari 2 siklus dihapus otomatis untuk mencegah disk penuh.

---

## 6. API Endpoints

Base URL: `http://localhost:8000`

### `GET /health`
Status server dan model aktif.
```json
{
  "status": "ok",
  "model": "ICON-Global",
  "domain": "Indonesia"
}
```

### `GET /api/icon/runs`
Daftar seluruh run ID yang tersedia di penyimpanan lokal.
```json
{
  "runs": ["2026101700"]
}
```

### `GET /api/icon/manifest`
Metadata lengkap run terbaru untuk konsumsi MapLibre/Leaflet:
```json
{
  "model": "ICON-Global",
  "source": "DWD Open Data",
  "domain": {
    "name": "Indonesia",
    "bounds": [[-15.0, 88.0], [12.0, 148.0]],
    "zoom_min": 4,
    "zoom_max": 7
  },
  "run_id": "2026101700",
  "run_time": "2026-10-17T00:00:00Z",
  "updated_at": "2026-10-17T07:07:00Z",
  "tile_url_template": "/api/icon/tiles/{run}/{param}/{step}/{z}/{x}/{y}.webp",
  "parameters": [
    {"id": "t_2m", "name": "Temperature 2m", "unit": "°C", "range": [-10.0, 45.0], "is_accum": false},
    {"id": "relhum_2m", "name": "Relative Humidity", "unit": "%", "range": [0.0, 100.0], "is_accum": false},
    {"id": "tot_prec", "name": "Rain Accumulation", "unit": "mm", "range": [0.0, 250.0], "is_accum": true},
    {"id": "pmsl", "name": "Mean Sea Level Pressure", "unit": "hPa", "range": [996.0, 1020.0], "is_accum": false},
    {"id": "td_2m", "name": "Dew Point 2m", "unit": "°C", "range": [10.0, 32.0], "is_accum": false},
    {"id": "cape_ml", "name": "CAPE (Mixed Layer)", "unit": "J/kg", "range": [0.0, 4000.0], "is_accum": false},
    {"id": "clct", "name": "Total Cloud Cover", "unit": "%", "range": [0.0, 100.0], "is_accum": false}
  ],
  "timesteps": [
    {
      "step": 0,
      "step_str": "000",
      "valid_time": "2026-10-17T00:00:00Z",
      "params": ["cape_ml", "clct", "pmsl", "relhum_2m", "t_2m", "td_2m", "tot_prec"]
    },
    {
      "step": 1,
      "step_str": "001",
      "valid_time": "2026-10-17T01:00:00Z",
      "params": ["cape_ml", "clct", "pmsl", "relhum_2m", "t_2m", "td_2m", "tot_prec"]
    }
  ]
}
```

### `GET /api/icon/tiles/{run}/{param}/{step}/{z}/{x}/{y}.webp`
Slippy Map tile citra visual WebP.
- Header: `Content-Type: image/webp`
- Header: `Cache-Control: public, max-age=604800, immutable`
- Tile kosong/luar area: Mengembalikan $1\times 1$ WebP transparan (status 200, 30 bytes) untuk mencegah error 404 pada map viewer.

### `GET /api/icon/tiles-numeric/{run}/{param}/{step}/{z}/{x}/{y}.webp`
Slippy Map tile numerik WebP lossless (Terrain-RGB scheme) untuk inspeksi nilai fisik langsung di sisi client (canvas/pixel inspection):
- **Encoding**: 24-bit RGB integer dengan presisi 0.1
- **Formula Encode**: `val_int = int((val + 1000.0) * 10)`
- **Formula Decode**: `val = ((R * 65536 + G * 256 + B) / 10.0) - 1000.0`
- Alpha channel = 0 menandakan area nodata / laut tanpa nilai.

### `GET /api/icon/point`
Endpoint sampling titik untuk pop-up interaktif saat pengguna mengklik peta.
- **Query Params**:
  - `lat`: Latitude (misal `-6.2088`)
  - `lon`: Longitude (misal `106.8456`)
  - `step`: Timestep prakiraan (misal `000`, `003`)
  - `run`: Opsional (default run aktif terbaru)
  - `param`: Opsional (`all` untuk seluruh 7 parameter, atau ID spesifik seperti `t_2m`)
- **Struktur Response Pop-up**:
```json
{
  "status": "success",
  "run_id": "2026101706",
  "run_time": "2026-10-17T06:00:00Z",
  "valid_time": "2026-10-17T06:00:00Z",
  "tanggal": "17 Oktober 2026, 13:00 WIB",
  "koordinat": {
    "latitude": -1.2654,
    "longitude": 116.8312
  },
  "lokasi": {
    "kecamatan": "Telaga Sari",
    "kabupaten_kota": "Balikpapan",
    "provinsi": "Kalimantan Timur",
    "negara": "Indonesia",
    "display_name": "Telaga Sari, Balikpapan Kota, Balikpapan, Kalimantan Timur, Indonesia"
  },
  "nilai": {
    "t_2m": {
      "name": "Temperature 2m",
      "value": 30.47,
      "unit": "°C",
      "is_accum": false
    },
    "relhum_2m": {
      "name": "Relative Humidity",
      "value": 70.67,
      "unit": "%",
      "is_accum": false
    },
    "tot_prec": {
      "name": "Rain Accumulation",
      "value": 0.0,
      "unit": "mm",
      "is_accum": true
    },
    "pmsl": {
      "name": "Mean Sea Level Pressure",
      "value": 1009.22,
      "unit": "hPa",
      "is_accum": false
    },
    "td_2m": {
      "name": "Dew Point 2m",
      "value": 24.46,
      "unit": "°C",
      "is_accum": false
    },
    "cape_ml": {
      "name": "CAPE (Mixed Layer)",
      "value": 943.16,
      "unit": "J/kg",
      "is_accum": false
    },
    "clct": {
      "name": "Total Cloud Cover",
      "value": 58.06,
      "unit": "%",
      "is_accum": false
    }
  }
}
```

---

## 7. Panduan Menjalankan Engine (CLI)

### Instalasi Dependensi
```bash
pip install -r backend/requirements.txt
```

### Test Pengolahan 1 Step (Semua Parameter)
```bash
# Olah step 000 untuk seluruh 7 parameter
python backend/run_engine.py --test-step 0

# Olah step spesifik untuk 1 parameter saja (misal rain accumulation jam ke-3)
python backend/run_engine.py --test-step 3 --param tot_prec
```

### Menjalankan Download & Render Penuh Run Terbaru
```bash
# Memproses seluruh timestep maksimal (120h atau 180h)
python backend/run_engine.py --run-all

# Membatasi jumlah timestep (misal hanya 12 timestep awal)
python backend/run_engine.py --run-all --max-steps 12
```

### Menjalankan Daemon Auto-Update Realtime
Daemon mengecek direktori DWD setiap 15 menit. Begitu run baru rilis, download dan render otomatis berjalan di background.
```bash
python backend/run_engine.py --daemon
```

### Menjalankan Server API WebP Tiles
```bash
python backend/run_engine.py --serve --port 8000
```
Server aktif di `http://localhost:8000`. Dokumentasi OpenAPI/Swagger interaktif tersedia di `http://localhost:8000/docs`.
