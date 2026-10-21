# Prakiraan Potensi Tanah Longsor — Eksperimental

Dokumen teknis implementasi fitur prakiraan potensi tanah longsor berbasis integrasi Indeks Kerentanan BNPB InaRISK dan Prakiraan Akumulasi Curah Hujan 24 Jam ke Depan dari ECMWF IFS (Integrated Forecasting System).

---

## 1. Arsitektur & Alur Data

Sistem berjalan secara **offline-first** dan **terproses di backend** (staged publication). Browser tidak melakukan komputasi raster berat, melainkan menerima visualisasi berupa WebP losslessly-encoded raster tiles dan data numerik tervalidasi via REST API.

```
+-------------------------------------------------------------------------+
|                              DATA SOURCES                               |
|                                                                         |
|  [Official BNPB InaRISK ImageServer]        [ECMWF IFS Open Data GRIB]  |
|   - EPSG:3395 (Mercator), ~100m             - EPSG:4326, 0.25 deg grid  |
|   - Single-band Float32 Index [0..1]        - Total Precipitation (tp)  |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                           BACKEND INGESTION                             |
|                                                                         |
|  1. BNPB Ingestion (engine.landslide.hazard)                            |
|     - Chunked exportImage (1024x1024)                                   |
|     - Masking sentinel NoData (-3.40282e38 & masks) -> NaN              |
|     - Cache: engine/output/landslide/hazard/bnpb_vulnerability.tif             |
|     - Metadata & SHA-256: bnpb_meta.json                                |
|                                                                         |
|  2. ECMWF Ingestion & Retention (engine.run & landslide.precipitation)  |
|     - Ekstraksi tp sebelum penghapusan file GRIB asli                   |
|     - Validasi eccodes: accum, stepUnits in ('1','h'), units in ('m')   |
|     - Penyimpanan NPZ + JSON sidecar ber-checksum SHA-256               |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        PROCESSING & PUBLICATION                         |
|                       (engine.landslide.processor)                      |
|                                                                         |
|  - Exclusive process lock: engine/output/landslide/processing.lock      |
|  - Hitung curah hujan 24 jam ke depan:                                  |
|      R24_forward(t) = TP(t + 24) - TP(t)                                |
|  - Reproyeksi & agregasi rata-rata indeks kerentanan ke grid ECMWF:         |
|      rasterio.warp.reproject(resampling=Resampling.average)             |
|  - Klasifikasi biner & matriks potensi (classify_arrays)                |
|  - Penyimpanan staged output di temporary directory:                    |
|      * GeoTIFF uint8 EPSG:4326 dengan nearest overviews                 |
|      * NPZ numerik terkompresi (cat, rain, hazard, lats, lons)          |
|      * Tile visual WebP lossless (z=3..6)                               |
|      * Signature konten (SHA-256) -> publication_id: {run}-{digest}     |
|  - Atomic publication: pemindahan folder utuh & update latest.json      |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                           API & PRESENTATION                            |
|                                                                         |
|  - FastAPI Endpoints (/api/landslide/forecast):                         |
|      * GET /status: status ketersediaan cache kerentanan & run terakhir     |
|      * GET /metadata: metadata publikasi, daftar timestep, ambang       |
|      * GET /tile/{run}/{step}/{z}/{x}/{y}.webp: visual tiles            |
|      * GET /point?lat=&lon=&step=&run=: inspeksi numerik titik          |
|  - Vite Proxy: meneruskan /api/landslide/forecast ke backend FastAPI    |
|  - Svelte 5 Native MapLibre UI:                                         |
|      * MapLibre Raster Layer (nearest resampling, dynamic opacity)      |
|      * Native ForecastControl: timeline bersama satu kontrol            |
|      * LandslideLegend: kartu legenda, batas ambang dinamis, disclaimers|
|      * Map Click: Popup inspeksi nilai dengan DOM textContent sanitasi  |
+-------------------------------------------------------------------------+
```

---

## 2. Formula & Definisi Metodologi

### 2.1 Definisi Jendela Forward 24-Hour
Timestep prakiraan yang dipilih merepresentasikan **titik awal (start)** dari jendela 24 jam ke depan:
$$\text{Window}(t) = [t, t + 24]$$

Untuk variabel presipitasi kumulatif dari awal run model ($\text{start\_step} = 0$):
$$R_{24\text{\_forward}}(t) = \text{TP}(t + 24) - \text{TP}(t)$$

**Contoh Operasional:**
Jika pada $t = +3$ jam akumulasi hujan $\text{TP}(+3) = 5\text{ mm}$, dan pada $t = +27$ jam akumulasi hujan $\text{TP}(+27) = 85\text{ mm}$, maka curah hujan 24 jam ke depan untuk jendela $+3 \rightarrow +27$ jam adalah:
$$R_{24\text{\_forward}}(+3) = 85\text{ mm} - 5\text{ mm} = 80\text{ mm}$$

Jika data berupa interval inkremental tak teratur, sistem menjumlahkan segmen kontigu tanpa celah (gap-free sum) dengan memverifikasi:
$$\text{start\_step}_{i} = \text{end\_step}_{i-1} \quad \text{dan} \quad \text{end\_step}_n = t + 24$$
Setiap ketidaksesuaian kesinambungan waktu atau nilai hujan negatif menghasilkan status `NoData`.

### 2.2 Matriks Keputusan Potensi (Vulnerability $\times$ Rainfall)
Klasifikasi potensi longsor ditentukan melalui kombinasi kelas kerentanan BNPB dan pemicu curah hujan 24 jam:

**Varian `experimental_v2_vulnerability`:** Sumber perhitungan diganti sesuai pilihan pengguna menjadi Indeks Kerentanan, bukan Indeks Bahaya. Kerentanan tidak identik dengan bahaya fisik atau kestabilan lereng. Matriks ini belum divalidasi untuk memprediksi kejadian longsor; referensi ambang hujan tidak memvalidasi penggabungannya dengan indeks kerentanan.

| Kelas Kerentanan (Averaged Index) | Curah Hujan 24 Jam ($R_{24}$) | Status / Kategori | Kode Raster | Nilai RGBA Tile |
| :--- | :--- | :--- | :---: | :--- |
| **Valid (Rendah / Sedang / Tinggi)** | $< 30.0\text{ mm}$ | `no_trigger` (Tanpa Pemicu) | `0` | `(0, 0, 0, 0)` Transparan |
| **Rendah** ($0.0 \le \text{Index} \le 0.333$) | $\ge 30.0\text{ mm}$ | `waspada` (Waspada) | `1` | `(234, 179, 8, 255)` #EAB308 |
| **Sedang** ($0.333 < \text{Index} \le 0.666$) | $\ge 30.0\text{ mm}$ | `siaga` (Siaga) | `2` | `(249, 115, 22, 255)` #F97316 |
| **Tinggi** ($0.666 < \text{Index} \le 1.0$) | $\ge 30.0\text{ mm}$ | `bahaya` (Bahaya) | `3` | `(220, 38, 38, 255)` #DC2626 |
| **Tidak Valid / NoData** (indeks kerentanan atau hujan tidak tersedia) | Berapa pun | `nodata` (NoData) | `255` | `(0, 0, 0, 0)` Transparan |

> **Prinsip Validasi Krusial:**
> Jika data indeks kerentanan bernilai `NoData` (misalnya di perairan atau luar wilayah), output **wajib** berupa `nodata` (kode 255), **bukan** `no_trigger` (kode 0), meskipun curah hujan bernilai 0 mm.

### 2.3 Status Provisori Batas Kelas Kerentanan
Batas kelas kerentanan provisori yang digunakan:
- Rendah: $0.0 \le \text{Index} \le 0.333$
- Sedang: $0.333 < \text{Index} \le 0.666$
- Tinggi: $0.666 < \text{Index} \le 1.0$

Batas pembagian sepertiga ini bersifat **provisori (sementara)** karena metadata ImageServer BNPB InaRISK tidak mendefinisikan skema simbolisasi resmi atau class breaks kuantitatif untuk layer raster F32 tersebut. Batas ini dapat disesuaikan melalui environment variable `LANDSLIDE_HAZARD_LOW_MAX` dan `LANDSLIDE_HAZARD_MEDIUM_MAX` bila BNPB mempublikasikan standar klasifikasi resmi.

### 2.4 Adaptasi Ambang Batas Curah Hujan (Yuniawan et al., 2022)
Ambang batas pemicu curah hujan sebesar **$30\text{ mm}$** mengacu pada literatur ilmiah:
> Yuniawan et al. (2022), *Revised Rainfall Threshold in the Indonesian Landslide Early Warning System*, Geosciences 12(3), 129. [doi:10.3390/geosciences12030129](https://doi.org/10.3390/geosciences12030129)

**Penjelasan Adaptasi:**
Spesifikasi pengguna memberi referensi ambang hujan harian 30 mm dari paper tersebut. Isi lengkap paper belum berhasil diverifikasi independen dalam lingkungan ini (akses penerbit sebelumnya mengembalikan HTTP 403); waktu observasi harian dan validitas ambang untuk tiap wilayah belum dipastikan. Sistem mengadaptasi ambang menjadi **jendela bergerak 24 jam ke depan** pada timestep prakiraan ($+0, +3, +6, \dots, +72$ jam). Ini perubahan metodologi eksperimental, bukan reproduksi tervalidasi dari sistem peringatan dalam paper. Kinerja prediksi, false alarm, dan missed event belum dievaluasi.

---

## 3. Sumber Data & Karakteristik Spasial

### 3.1 Peta Kerentanan Tanah Longsor BNPB InaRISK
- **URL Layanan:** `https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_KERENTANAN_TANAH_LONGSOR/ImageServer`
- **Tipe Data:** ArcGIS ImageServer, Raster Float32, 1 band.
- **Rentang Nilai:** $0.0$ sampai $1.0$ (Indeks Kerentanan Relatif).
- **Resolusi Spasial:** pixelSizeX/pixelSizeY 100 m pada metadata EPSG:3395 yang diperiksa; resolusi tanah bergantung lintang.
- **Proyeksi Asli:** EPSG:3395 (WGS 84 / World Mercator).
- **Sentinel NoData:** Server mengekspor nilai NoData sebagai IEEE 754 Float32 sentinel $-3.4028235 \times 10^{38}$ tanpa menyertakan tag `GDAL_NODATA`. Sistem secara khusus memfilter nilai $\le -10^{30}$, nilai non-finite, dan raster mask menjadi `NaN`.
- **Interpretasi Rerata Grid (Grid-Mean):** Saat disagregasikan ke grid model cuaca ECMWF ($0.25^\circ \approx 25\text{ km}$), indeks kerentanan BNPB direratakan (`Resampling.average`). Nilai yang dihasilkan merepresentasikan **rerata kerentanan dalam grid $25\text{ km}$**, sehingga nilai ekstrem mikro-topografi lereng lokal dapat tersamarkan.
- **Batasan Lisensi & Hukum:** Metadata layanan BNPB tidak menyertakan klausul lisensi terbuka tertulis. Penggunaan layer ini ditujukan semata-mata untuk riset dan pembuktian konsep eksperimental internal; redistribusi data publik harus diverifikasi dengan ketentuan resmi BNPB.

### 3.2 Model Cuaca ECMWF IFS (Integrated Forecasting System)
- **Sumber:** ECMWF Open Data (`ecmwf-opendata`).
- **Domain:** Indonesia & sekitarnya ($94.0^\circ\text{BT} - 141.5^\circ\text{BT},\ -11.5^\circ\text{LS} - 6.5^\circ\text{LU}$).
- **Resolusi:** $0.25^\circ \times 0.25^\circ$, koordinat WGS84 (EPSG:4326).
- **Parameter:** Total Precipitation (`tp`), satuan meter ekuivalen air dikonversikan ke milimeter ($\times 1000$).
- **Pembaruan:** Siklus operasional 00, 06, 12, 18 UTC.
- **Lisensi:** Creative Commons Attribution 4.0 International (CC-BY-4.0).

---

## 4. Referensi API

Semua endpoint berada di bawah prefix `/api/landslide/forecast`.

Nama field `hazard_*`, array NPZ `hazard`, direktori `hazard/`, dan environment variable `LANDSLIDE_HAZARD_*` dipertahankan untuk kompatibilitas. Pada metode `experimental_v2_vulnerability`, field tersebut berisi **kerentanan**. Metadata menyatakan `index_type: "vulnerability"` serta URL asli dalam `hazard_source.source`. API menolak publikasi metode/sumber lama, bukan melabelinya ulang. Contoh JSON berikut ilustrasi kontrak API, bukan prakiraan aktual.

### 4.1 Status Sistem
- **Method:** `GET`
- **Path:** `/api/landslide/forecast/status`
- **Response 200 OK:**
```json
{
  "available": true,
  "run_id": "20261018T00",
  "processing": {
    "state": "ready",
    "run_id": "20261018T00",
    "publication_id": "20261018T00-7f2e1a4b9c8d3e5f",
    "checked_at": "2026-10-18T02:00:00Z"
  },
  "hazard_cached": true,
  "experimental": true
}
```

### 4.2 Metadata Publikasi Terakhir
- **Method:** `GET`
- **Path:** `/api/landslide/forecast/metadata`
- **Status:** `200 OK` (atau `503 Service Unavailable` bila data belum diproses).
- **Contoh Response 200:**
```json
{
  "product": "landslide_potential",
  "title": "Prakiraan Potensi Tanah Longsor — Eksperimental",
  "status": "experimental",
  "model": "ECMWF_IFS",
  "run_id": "20261018T00",
  "publication_id": "20261018T00-7f2e1a4b9c8d3e5f",
  "run_time": "2026-10-18T00:00:00Z",
  "method_version": "experimental_v2_vulnerability",
  "index_type": "vulnerability",
  "rain_threshold_24h_mm": 30.0,
  "hazard_class_boundaries_provisional": true,
  "hazard_low_max": 0.333,
  "hazard_medium_max": 0.666,
  "hazard_resampling": "average valid index to ECMWF grid; classes applied after aggregation",
  "bbox": [94.0, -11.5, 141.5, 6.5],
  "minzoom": 3,
  "maxzoom": 6,
  "tile_url": "/api/landslide/forecast/tile/{run}/{step}/{z}/{x}/{y}.webp",
  "steps": [
    {
      "step": 0,
      "ready": true,
      "forecast_start": "2026-10-18T00:00:00Z",
      "forecast_end": "2026-10-19T00:00:00Z",
      "tiles_count": 84
    },
    {
      "step": 3,
      "ready": false,
      "reason": "Missing endpoint +27"
    }
  ]
}
```

### 4.3 Visual Raster Tiles
- **Method:** `GET`
- **Path:** `/api/landslide/forecast/tile/{run}/{step}/{z}/{x}/{y}.webp`
- **Parameter:**
  - `run`: gunakan `publication_id` dari metadata (`YYYYMMDDTHH-` ditambah 16 digit heksadesimal). `run_id` tanpa hash hanya cocok jika direktori publikasi lama dengan nama itu benar-benar ada; tidak otomatis di-resolve ke versi terbaru.
  - `step`: Timestep awal (integer jam).
  - `z`, `x`, `y`: Indeks tile standar Slippy map (XYZ).
- **Response:** WebP Lossless Image (`image/webp`).
  - Cache-Control: `public, max-age=604800, immutable` untuk tile terbitan tetap.
  - Tile di luar cakupan batas Indonesia menghasilkan tile transparan berukuran 256×256 px.

### 4.4 Inspeksi Numerik Titik (Point Query)
- **Method:** `GET`
- **Path:** `/api/landslide/forecast/point`
- **Query Parameter:**
  - `lat`: Lintang (float, -90..90).
  - `lon`: Bujur (float, -180..180).
  - `step`: Timestep awal (integer $\ge 0$).
  - `run` (opsional): ID publikasi (default ke publikasi terbaru).
- **Contoh Response 200 OK:**
```json
{
  "product": "landslide_potential",
  "status": "experimental",
  "model": "ECMWF_IFS",
  "run_id": "20261018T00",
  "publication_id": "20261018T00-7f2e1a4b9c8d3e5f",
  "run_time": "2026-10-18T00:00:00Z",
  "forecast_step": 0,
  "forecast_start": "2026-10-18T00:00:00Z",
  "forecast_end": "2026-10-19T00:00:00Z",
  "latitude": -6.82,
  "longitude": 107.14,
  "rainfall_24h_mm": 52.4,
  "hazard_index": 0.742,
  "hazard_class": "high",
  "rainfall_trigger": true,
  "rain_threshold_24h_mm": 30.0,
  "category": "bahaya",
  "category_code": 3,
  "method_version": "experimental_v2_vulnerability",
  "index_type": "vulnerability",
  "hazard_index_representation": "mean on ECMWF grid"
}
```

---

## 5. Panduan Operasional

### 5.1 Inisiasi Cache Kerentanan BNPB
Pengambilan BNPB dijalankan eksplisit dan disimpan lokal. Saat perintah `ingest` dijalankan lagi, cache diperbarui jika usia mencapai 30 hari atau fingerprint berubah. Belum ada scheduler refresh BNPB otomatis; jadwalkan perintah ini terpisah. Cakupan nasional memuat sekitar 1 miliar pixel sumber (beberapa GB sebelum kompresi) dan banyak request; siapkan waktu, disk, dan kebijakan penggunaan layanan.
```bash
# Ingest cache resmi BNPB (estimasi download bertahap)
python -m engine.landslide.run ingest

# Untuk memaksa pembaruan ulang meskipun cache masih ada:
python -m engine.landslide.run ingest --force --chunk-size 1024
```
File cache tersimpan di `engine/output/landslide/hazard/bnpb_vulnerability.tif`.

Migrasi dari sumber bahaya memerlukan ingest kerentanan dan pemrosesan ulang run ECMWF. Cache `bnpb_hazard.tif` tidak dipakai ulang; checksum dan URL sumber wajib sesuai. Publikasi lama tetap tersimpan tetapi tidak disajikan sebagai kerentanan. Publikasi kerentanan pertama menggantikan pointer `latest.json` lama meskipun run lama bertanggal lebih baru; setelah itu urutan waktu dijaga dalam metode yang sama.

### 5.2 Pemrosesan Manual Prakiraan
Jika data ECMWF telah diunduh, pemrosesan potensi longsor dapat dijalankan secara mandiri:
```bash
python -m engine.landslide.run process 20261018T00
```

### 5.3 Memeriksa Status Ketersediaan
Untuk melihat ringkasan kondisi cache, metadata, dan run aktif:
```bash
python -m engine.landslide.run status
```

### 5.4 Pemulihan Lock File (`processing.lock`)
Proses publikasi dilindungi oleh mutual exclusion lock di `engine/output/landslide/processing.lock`. Jika proses terhenti paksa (misalnya crash sistem operasi atau pemadaman listrik):
1. Pastikan tidak ada proses Python `engine.landslide.processor` yang sedang aktif di Task Manager.
2. Hapus file lock secara manual:
   ```powershell
   Remove-Item engine/output/landslide/processing.lock
   ```
3. Jalankan kembali perintah pemrosesan.

### 5.5 Integrasi Otomatis dengan Pipeline ECMWF
Pipeline utama di `engine/run.py` secara otomatis memicu pemrosesan potensi tanah longsor:
1. Sebelum tile cuaca diproses dan file GRIB dihapus, array `tp` diekstrak bersama metadata akumulasi eccodes via `retain_tp`.
2. Setelah seluruh step cuaca ECMWF selesai dipanggang, `engine.run` memanggil `process_landslide(run_id)`.
3. Kegagalan pada pemrosesan longsor diisolasi (`try...except`) dan dicatat pada log tanpa membatalkan publikasi layer cuaca reguler.

### 5.6 Penanganan Missing Steps
Jika satu atau beberapa timestep perantara hilang dari feed ECMWF Open Data:
- Sistem tidak membatalkan seluruh run. Jendela yang memiliki pasangan data lengkap ($t$ dan $t+24$) tetap diterbitkan dengan `ready: true`.
- Jendela yang kehilangan endpoint dicatat secara eksplisit dalam metadata manifest dengan `ready: false` beserta alasannya.
- Frontend secara otomatis menampilkan label *"Tidak tersedia"* pada opsi timestep yang tidak lengkap dan menyajikan banner informatif.

---

## 6. Troubleshooting

1. **Error: "Data BNPB/ECMWF forward-24h belum tersedia" (Status 503)**
   - *Penyebab:* Backend FastAPI belum menemukan `latest.json` di `engine/output/landslide/`.
   - *Solusi:* Jalankan ingest BNPB (`python -m engine.landslide.run ingest`) dan proses minimal satu siklus ECMWF lengkap sampai timestep +24 (`python -m engine.run --once`).
2. **Error: "BNPB raw index outside 0..1"**
   - *Penyebab:* Ekspor mengandung nilai tidak sah di luar toleransi indeks 0–1. Sentinel ESRI yang dikenal telah dimask; error tidak boleh diabaikan atau diubah menjadi nol.
   - *Solusi:* Modul `engine/landslide/hazard.py` telah dilengkapi filter `nodata_mask = (raw <= -1e30) | (~np.isfinite(raw)) | (source.read_masks(1) == 0)` untuk mensterilkan sentinel ESRI.
3. **Error: "Missing TP metadata +24" saat pemrosesan**
   - *Penyebab:* Unduhan ECMWF belum mencapai jam ke-24 atau retention gagal dieksekusi.
   - *Solusi:* Jalankan ECMWF pipeline dengan parameter `--force` untuk memastikan minimal step 0 dan step 24 tersedia.
4. **Tile Browser Mengembalikan 404**
   - *Penyebab:* Permintaan level zoom di luar batas $z \in [3, 6]$.
   - *Solusi:* Konfigurasi map client dibatasi pada zoom minimum 3 dan maksimum 6.

---

## 7. Hasil Pengujian Sistem

Pengujian unit dan integrasi otomatis diimplementasikan menggunakan `pytest` pada direktori `tests/`:

1. **`tests/test_landslide_temporal.py` (15 Pengujian Lulus):**
   - Batas ambang indeks kerentanan ($0.0, 0.333, 0.666, 1.0$) dan penolakan nilai di luar rentang / NaN.
   - Ambang curah hujan ($29.99\text{ mm}, 30.0\text{ mm}, 30.01\text{ mm}$).
   - **Prinsip Validitas:** Indeks kerentanan tidak valid menghasilkan `nodata`, bukan `no_trigger`.
   - Verifikasi contoh spesifikasi: $5\text{ mm} \rightarrow 85\text{ mm} = 80\text{ mm}$ untuk jendela $+3 \rightarrow +27$.
   - Penolakan anomali reset negatif dan konversi satuan ($m \rightarrow mm$).
   - Validasi integritas checksum SHA-256 data TP dan kesesuaian koordinat.
   - Kontinuitas akumulasi bertahap dan deteksi celah (*gap/overlap*).

2. **`tests/test_landslide_integration.py` (8 Pengujian Lulus):**
   - Reproyeksi spasial dan agregasi rata-rata indeks kerentanan ke grid ECMWF.
   - Kesetaraan inspeksi titik dan sampling tile pada koordinat batas (*half-cell tie breaking*).
   - Pipeline pemrosesan end-to-end, idempoten publikasi, dan pembentukan direktori versi.
   - Penanganan respons API saat uninitialized (HTTP 503) dan metadata terbit (HTTP 200).
   - Validasi format tile WebP dan titik koordinat luar wilayah (*out-of-bounds*).

**Eksekusi Keseluruhan:**
```
23 passed, 1 warning
```
Seluruh 23 pengujian unit dan integrasi terverifikasi lulus, termasuk penolakan cache salah sumber dan publikasi metode/sumber lama.

---

## 8. Batasan Ilmiah & Pernyataan Eksperimental

1. **Bukan Peringatan Dini Resmi:** Fitur ini berstatus eksperimental murni untuk riset teknologi dan **bukan peringatan resmi** dari instansi berwenang Republik Indonesia (PVMBG, BNPB, atau BMKG).
2. **Keterbatasan Rerata Grid (Resolution Gap):** Grid cuaca $0.25^\circ\ (\approx 25\text{ km})$ meratakan indeks kerentanan BNPB ($100\text{ m}$). Variasi kerentanan lokal dapat tersamarkan. Layer ini tidak mengukur bahaya fisik atau kestabilan lereng.
3. **Status "Tanpa Pemicu" (No Trigger):** Nilai curah hujan $< 30\text{ mm}$ **tidak menjamin bebas dari risiko tanah longsor**. Kejadian longsor dapat dipicu oleh faktor lain di luar hujan forward 24 jam (misalnya gempa bumi, akumulasi hujan hari-hari sebelumnya/antecedent rainfall, erosi lereng, atau pemotongan tebing buatan).
4. **Indeks Bukan Probabilitas:** Indeks kerentanan BNPB ($0 - 1$) adalah indeks kerentanan relatif, bukan indeks bahaya fisik, indeks risiko, atau persentase probabilitas kejadian.
