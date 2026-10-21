# Instruksi AI: Implementasi dan Aktivasi Potensi Longsor Eksperimental

## 0. Instruksi utama untuk AI penerus

Baca seluruh file sebelum bertindak. Kerjakan di root repository `metamorph-nwp` pada PC tujuan; jangan mengasumsikan path `C:\metamorph-nwp` tersedia. Periksa `CLAUDE.md`, dokumentasi setup, `git status`, struktur proyek, dan perintah yang benar-benar tersedia. Pertahankan perubahan pengguna. Jangan commit, push, menghapus cache, mengganti branch, atau membuka layanan ke internet tanpa izin.

**File Markdown bukan executable dan tidak membawa source code.** File ini instruksi untuk AI dengan akses repository dan terminal. Jika source landslide sudah tersedia, audit lalu jalankan setup. Jika belum tersedia, implementasikan spesifikasi di bagian 8 sebelum menjalankan perintah modulnya. Jangan mengklaim selesai hanya karena dokumen ini tersedia.

Pada PC asal, perubahan landslide belum di-commit saat dokumen dibuat. `git clone` dari remote saja mungkin belum membawa implementasi ini. Pilihan pemindahan: salin source terbaru beserta file baru, atau minta pengguna menyinkronkan commit yang diperlukan. Jangan menimpa source PC tujuan tanpa membandingkan isinya. Jangan menyalin `.venv/`, `node_modules/`, kredensial, atau output sintetis test sebagai data produksi.

Dokumen pendamping, jika tersedia: `docs/LANDSLIDE_EXPERIMENTAL.md`.

Sumber wajib:
- WMS yang dipilih pengguna: `https://gis.bnpb.go.id/server/services/inarisk/INDEKS_KERENTANAN_TANAH_LONGSOR/ImageServer/WMSServer?request=GetCapabilities&service=WMS`
- REST untuk data numerik: `https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_KERENTANAN_TANAH_LONGSOR/ImageServer`
- Gunakan **kerentanan**, bukan menggantinya diam-diam dengan `INDEKS_BAHAYA_TANAHLONGSOR`.

Lanjutkan pekerjaan lokal yang aman tanpa pertanyaan pilihan kosmetik. Hentikan dan laporkan jika akses data, izin, disk, atau dependensi native menghalangi; jangan membuat pengganti data asli. Sebelum unduhan nasional berukuran besar atau publikasi keluar PC, pastikan izin operator dan kapasitas tersedia. Jangan menjalankan ulang unduhan besar secara membabi buta.

---

# Runbook Operasional

File instruksi terstruktur untuk dieksekusi otomatis oleh AI / Claude Code pada PC atau environment lain.

---

## 1. Context & Task Summary
- **Project Repo**: `metamorph-nwp` (Svelte 5 frontend + FastAPI backend + Python NWP engine).
- **Goal**: Inisialisasi, pengujian, dan penyiapan pipeline prakiraan potensi tanah longsor eksperimental berbasis **Indeks Kerentanan BNPB InaRISK** (`INDEKS_KERENTANAN_TANAH_LONGSOR`) dan akumulasi curah hujan forward 24 jam ECMWF IFS (`R24_forward(t) = TP(t+24) - TP(t)`).
- **Method Version**: `experimental_v2_vulnerability`.
- **Target OS**: Windows / Linux / macOS (command cross-platform disediakan).

---

## 2. Dependency Prerequisites

### 2.1 Python Environment
PC asal teruji memakai Python 3.12.9. Gunakan Python 3.12 bila kompatibel dengan proyek; jangan menganggap semua kombinasi OS dan versi Python telah diuji. Buat virtual environment lokal terlebih dahulu:

```bash
python -m venv .venv
```

Aktifkan di PowerShell: `.\.venv\Scripts\Activate.ps1`.
Aktifkan di Linux/macOS: `source .venv/bin/activate`.
Jika aktivasi diblokir kebijakan OS, gunakan interpreter `.venv` secara eksplisit; jangan melemahkan kebijakan sistem.

Pastikan packages terinstall di Python environment:
```bash
python -m pip install -r backend/requirements.txt
python -m pip install -r engine/requirements.txt
python -m pip install pytest pytest-asyncio
```

Packages esensial yang wajib ada:
- `fastapi`, `uvicorn`, `httpx` (API backend)
- `numpy`, `rasterio`, `pillow`, `requests` (Raster engine)
- `eccodes` (ECMWF GRIB decoding)
- `pytest` (Test verification)

`rasterio` dan `eccodes` dapat memerlukan library native GDAL/ecCodes. Verifikasi import dan pembacaan GRIB nyata. Jika gagal, perbaiki pemasangan sesuai OS; jangan menghapus validasi atau menggantinya dengan data sintetis.

### 2.2 Node.js Environment
Gunakan Node.js versi LTS yang didukung `package.json`; Node.js 22 LTS menjadi pilihan bila tidak ada ketentuan proyek. Bila `package-lock.json` tersedia dan sinkron, jalankan:
```bash
npm ci
```
Jika lockfile tidak ada, gunakan `npm install`. Jangan memperbarui dependensi atau lockfile tanpa kebutuhan.

---

## 3. Automated Verification Checklist

Jalankan pengujian unit dan integrasi untuk memvalidasi algoritma klasifikasi, boundary half-cell tie breaking, dan route API:

```bash
python -m pytest tests/
```

**Kriteria Sukses:**
- Baseline PC asal: 23 test lulus; jumlah dapat bertambah bila test baru ditambahkan. Jalankan ulang di PC tujuan, jangan menyalin klaim kelulusan:

  - `tests/test_landslide_temporal.py` (15 tests)
  - `tests/test_landslide_integration.py` (8 tests)
- Tidak ada error kegagalan assert.

Verifikasi frontend build:
```bash
npm run build
```
**Kriteria Sukses:**
- Vite build selesai menghasilkan bundle di `dist/` tanpa error fatal.

---

## 4. Production Pipeline Execution Steps

### Langkah 1: Ingest Raster Kerentanan BNPB InaRISK
Unduh dan simpan cache Float32 dari REST ImageServer BNPB:
```bash
python -m engine.landslide.run ingest
```
- **Target Output**: `engine/output/landslide/hazard/bnpb_vulnerability.tif`
- **Metadata**: `engine/output/landslide/hazard/bnpb_meta.json`
- Cakupan nasional dapat memerlukan miliaran pixel, beberapa GB disk dan banyak request. Pastikan izin unduhan, ruang disk, dan konektivitas. Ingest saat ini bukan resumable per chunk; kegagalan dapat mengulang unduhan.
- **Catatan**: Setelah penyebab kegagalan diperbaiki, paksa pembaruan hanya bila diperlukan:
  ```bash
  python -m engine.landslide.run ingest --force --chunk-size 1024
  ```

### Langkah 2: Proses Run ECMWF
Pilih run nyata dari data tersedia, jangan memakai tanggal contoh sebagai run terbaru. Format `YYYYMMDDTHH` dalam UTC. Pastikan akumulasi presipitasi (`tp`) beserta metadata dan checksum tersimpan di `engine/output/landslide/precipitation/<RUN_ID>/`. Perintah berikut hanya contoh; ganti `20261018T00` dengan run nyata:
```bash
python -m engine.landslide.run process 20261018T00
```
- Bila retensi TP belum ada, periksa `python -m engine.run --help`. Gunakan pipeline ECMWF proyek yang sama, bukan downloader baru. Contoh pengambilan run terbaru: `python -m engine.run --once`.
- Bila run sudah diproses sebelum retensi TP ditambahkan, evaluasi kebutuhan rebuild dengan `--force` setelah memastikan biaya download dan perubahan output dapat diterima. `--run YYYYMMDDTHH` memilih run tertentu; periksa bantuan versi lokal.
- **Automated Trigger**: Pipeline mencoba memproses longsor setelah pemrosesan cuaca. Keberhasilannya memerlukan cache BNPB serta jendela TP valid. Sukses pipeline cuaca saja bukan bukti sukses longsor.
- Step awal sampai +72 memerlukan data sampai +96 untuk seluruh jendela. Untuk +3, endpoint +27 harus tersedia; pasangan +0/+24 hanya membuktikan jendela +0, bukan seluruh timeline.

### Langkah 3: Periksa Status Publikasi
```bash
python -m engine.landslide.run status
```
Pastikan `hazard_cached: true` dan `latest_run` menampilkan run ID yang aktif.

---

## 5. Menjalankan Server Lokal untuk Review

Terminal 1 (Backend FastAPI):
```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```
- Berjalan di `http://localhost:8000`.
- Endpoint metadata: `http://localhost:8000/api/landslide/forecast/metadata`.
- Endpoint status: `http://localhost:8000/api/landslide/forecast/status`.

Terminal 2 (Frontend Vite Dev Server):
```bash
npm run dev
```
- Akses URL yang dicetak Vite, biasanya `http://localhost:5173`.
- Proxy longsor memakai `NWP_API_ORIGIN`, default `http://127.0.0.1:8000`. Sesuaikan hanya bila backend berjalan di port lain.
- `dist/` saja tidak menjalankan API atau pipeline. Deployment produksi memerlukan backend dan routing `/api/landslide/forecast/` yang benar; jangan membuka akses publik tanpa izin.
- Buka layer "Prakiraan Potensi Tanah Longsor".
- Pastikan kartu legenda menampilkan:
  - `Eksperimental · Model ECMWF IFS × BNPB InaRISK (Kerentanan)`
  - Ambang `Indeks Kerentanan > 0.666` (Bahaya), `0.333 - 0.666` (Siaga), `<= 0.333` (Waspada).

---

## 6. Troubleshooting & Recovery Commands

| Masalah | Penyebab | Solusi |
| :--- | :--- | :--- |
| **HTTP 503 saat akses `/metadata`** | Cache belum dibuat atau belum ada run ECMWF forward-24h yang selesai diproses. | Jalankan `python -m engine.landslide.run ingest` lalu `python -m engine.landslide.run process <RUN_ID>`. |
| **Lock Error: `processing.lock` exists** | Proses sebelumnya crash atau terhenti paksa saat publishing. | Pastikan proses Python mati, lalu hapus lock: `rm engine/output/landslide/processing.lock` (Linux/Mac) atau `Remove-Item engine/output/landslide/processing.lock` (PowerShell). |
| **Tile HTTP 404** | Zoom di luar rentang $z \in [3, 6]$ atau publikasi lama berbeda metode. | Gunakan zoom level 3–6 dan pastikan metadata publikasi merujuk `experimental_v2_vulnerability`. |
| **`BNPB cache source mismatch`** | Cache di disk masih berasal dari layer bahaya lama (`bnpb_hazard.tif`). | Jalankan `python -m engine.landslide.run ingest --force` untuk mengunduh cache kerentanan. |

---

## 7. Strict Implementation Guardrails
AI penerus dilarang melanggar batasan berikut:
1. **Dilarang membuat website terpisah**; fitur harus terintegrasi di dalam aplikasi Svelte MapLibre yang ada.
2. **Dilarang menduplikasi pipeline ECMWF**; gunakan retensi `tp` terintegrasi di `engine/run.py`.
3. **Dilarang melakukan raster calculation berat di sisi browser client**; seluruh resampling grid dan klasifikasi wajib di-bake di backend menjadi WebP tile lossless.
4. **Dilarang melabeli indeks sebagai probabilitas** atau peringatan resmi PVMBG/BNPB/BMKG.
5. **Dilarang mengubah output `nodata` (255) menjadi `no_trigger` (0)** ketika data indeks kerentanan tidak valid/di luar coverage.
6. Jangan merombak arsitektur, merusak layer cuaca, menambahkan timeline slider kedua, neural network, machine learning, atau weighted overlay dengan bobot subjektif.
7. Jangan menambah threshold tanpa dasar. Batas 0.333/0.666 bersifat provisori, bukan kelas resmi BNPB. Ambang hujan 30 mm/24h merupakan adaptasi eksperimental dari referensi Yuniawan et al. (2022), DOI `10.3390/geosciences12030129`; bukan bukti validasi matriks kerentanan-hujan. Verifikasi sumber sebelum membuat klaim ilmiah tambahan.
8. Data sintetis hanya untuk automated testing di direktori sementara. Jangan mengembalikannya sebagai forecast aktual. Data belum tersedia harus tampil tidak tersedia.
9. Status `no_trigger` tidak berarti aman dari seluruh kemungkinan longsor. Kerentanan bukan bahaya fisik atau kestabilan lereng.
10. File unduhan dan arsip ekstraksi tidak tepercaya. Gunakan direktori baru dan kosong untuk tiap unduhan/ekstraksi, terpisah dari skrip buatan sendiri; jangan menjalankan interpreter atau build tool dari direktori unduhan. Python yang membaca unduhan dijalankan dengan `-I`; untuk modul proyek, gunakan runner tepercaya yang mempertahankan isolasi dan menambahkan hanya root source tepercaya ke import path. Jangan menjalankan skrip unduhan. Aturan ini tidak melarang menjalankan kode proyek tepercaya yang memang diminta pengguna.
11. Jangan menghapus `processing.lock` hanya karena file ada. Verifikasi tidak ada proses aktif, lalu minta izin sebelum penghapusan. Jangan membunuh proses Python lain.
12. Jangan melakukan redistribusi publik data BNPB sebelum ketentuan lisensi diverifikasi.

---

## 8. Spesifikasi implementasi bila source belum tersedia

Bagian ini menjadi kontrak implementasi, bukan instruksi untuk membuat modul duplikat bila fitur sudah ada. Baca kode lokal, sesuaikan idiom proyek, lalu edit bagian minimum yang diperlukan.

### 8.1 File dan tanggung jawab

| File | Tanggung jawab |
| --- | --- |
| `engine/landslide/__init__.py` | Package pipeline longsor. |
| `engine/landslide/config.py` | URL sumber, path, domain, ambang, kode kategori, versi metode. |
| `engine/landslide/hazard.py` | Metadata ArcGIS, raw Float32 export per chunk, masking, cache dan provenance. Nama legacy dipertahankan. |
| `engine/landslide/pipeline.py` | Reproyeksi dan agregasi indeks ke grid ECMWF dengan average. |
| `engine/landslide/precipitation.py` | Retensi TP, validasi metadata GRIB, checksum dan jendela forward. |
| `engine/landslide/rainfall.py` | Definisi waktu run dan jendela forecast UTC. |
| `engine/landslide/classify.py` | Klasifikasi array dan kelas indeks, tanpa komputasi browser. |
| `engine/landslide/tiles.py` | Sampling nearest kategori, tile XYZ WebP lossless. |
| `engine/landslide/storage.py` | JSON atomik dan SHA-256. |
| `engine/landslide/processor.py` | Lock, validasi input, staging, signature, publikasi versi immutable. |
| `engine/landslide/api.py` | FastAPI metadata, status, tile, inspeksi titik. |
| `engine/landslide/run.py` | CLI `ingest`, `process`, `status`. |
| `engine/decode.py`, `engine/run.py` | Retensi TP dalam pipeline ECMWF yang sama sebelum GRIB dihapus, trigger processor dengan kegagalan terisolasi. |
| `backend/app.py` | Registrasi router longsor tanpa mengganggu API cuaca. |
| `src/services/landslide.js` | Fetch metadata/titik, URL tile dan popup DOM aman. |
| `src/components/LandslideLegend.svelte` | Legenda dinamis, opacity, visibility, disclaimer kerentanan. |
| `src/components/ForecastControl.svelte`, `src/App.svelte`, `src/components/Toolbar.svelte` | Integrasi layer, timeline bersama, step unavailable, popup dan lifecycle fetch/layer. Adaptasikan komponen yang sudah ada. |
| `vite.config.js` | Proxy API longsor ke FastAPI untuk lingkungan lokal sesuai pola proyek. |
| `backend/requirements.txt`, `engine/requirements.txt` | Dependensi tambahan minimum, bukan upgrade massal. |
| `tests/test_landslide_temporal.py`, `tests/test_landslide_integration.py` | Test algoritma, provenance, API, tile dan migrasi sumber. |

### 8.2 Akuisisi dan grid

- Periksa metadata REST `?f=json`: single-band `F32`, CRS dan ukuran pixel nyata. Catatan PC asal: EPSG:3395, sekitar 100 m dan indeks 0–1; validasi ulang layanan di PC tujuan.
- Ambil `/exportImage` dengan `f=image`, `format=tiff`, `pixelType=F32`, `interpolation=RSP_NearestNeighbor`, `renderingRule={"rasterFunction":"None"}`, `bboxSR` dan `imageSR` sesuai CRS. Gunakan chunk 1024 atau batas layanan yang lebih kecil.
- Jangan menghitung dari warna PNG/JPEG WMS. Validasi dimensi, CRS, transform dan rentang nilai hasil ekspor. Mask sentinel ESRI `<= -1e30`, raster mask, NaN/Inf menjadi NoData; jangan menganggapnya nol.
- Cache raw raster dengan SHA-256, URL sumber, metadata layanan, fingerprint, bbox dan waktu pemeriksaan. Cache lama hanya boleh dipakai jika sumber/fingerprint/bbox sesuai dan umur kurang dari kebijakan 30 hari. Kegagalan unduhan tidak boleh merusak cache valid sebelumnya.
- Domain baseline WGS84 `[94.0, -11.5, 141.5, 6.5]`. Resample indeks valid memakai `rasterio.warp.Resampling.average` ke koordinat ECMWF yang sebenarnya; klasifikasi dilakukan setelah agregasi. Jangan melakukan interpolasi kategori secara bilinear.

### 8.3 TP dan klasifikasi

- Retain TP asli beserta run UTC, valid time, start/end step, step type, step units, units stored, koordinat dan SHA-256. NPZ wajib dimuat dengan `allow_pickle=False`.
- Ubah meter menjadi mm tepat satu kali. Tolak satuan tak dikenal, run campur, grid tak cocok, checksum salah dan akumulasi reset/negatif yang tidak sah.
- Rumus: `R24_forward(t) = TP(t+24) - TP(t)` untuk akumulasi sejak run. Contoh test saja: TP(+3)=5 mm, TP(+27)=85 mm menghasilkan 80 mm.
- Untuk interval inkremental, jumlahkan hanya rentang kontigu yang menutup tepat `[t,t+24]`; tolak gap, overlap atau endpoint hilang. Jangan menyisipkan data hujan palsu.
- Start forecast baseline +0..+72 setiap 3 jam. Tandai setiap jendela tidak lengkap sebagai `ready: false` dengan alasan; jangan hilangkan diam-diam atau tampilkan sebagai hujan nol.

| Kondisi | Kode | Nama | RGBA |
| --- | --- | --- | --- |
| Indeks/hujan tidak valid | 255 | `nodata` | `(0,0,0,0)` |
| Indeks valid 0..1, hujan <30 mm | 0 | `no_trigger` | `(0,0,0,0)` |
| Hujan >=30 mm, 0 <= indeks <=0.333 | 1 | `waspada` | `(234,179,8,255)` |
| Hujan >=30 mm, 0.333 < indeks <=0.666 | 2 | `siaga` | `(249,115,22,255)` |
| Hujan >=30 mm, 0.666 < indeks <=1 | 3 | `bahaya` | `(220,38,38,255)` |

Ambang konfigurasi legacy: `LANDSLIDE_RAIN_THRESHOLD_MM`, `LANDSLIDE_HAZARD_LOW_MAX`, `LANDSLIDE_HAZARD_MEDIUM_MAX`. Validasi finite dan urutan kelas. Legenda wajib membaca nilai metadata, bukan menampilkan konstanta yang bisa berbeda.

### 8.4 Publikasi dan migrasi

- Root output `engine/output/landslide/`: cache `hazard/bnpb_vulnerability.tif`, provenance `hazard/bnpb_meta.json`, TP `precipitation/<RUN_ID>/`, publikasi `runs/<PUBLICATION_ID>/`, pointer `latest.json`, status `status.json`.
- Versi metode `experimental_v2_vulnerability`; metadata wajib `index_type: "vulnerability"` dan `hazard_source.source` URL REST kerentanan di bagian 0.
- Pertahankan field `hazard_index`, `hazard_class`, `hazard_source`, `hazard_low_max`, `hazard_medium_max`, `hazard_class_boundaries_provisional`, array NPZ `hazard`, dan nama konfigurasi legacy untuk kompatibilitas. Dokumentasikan bahwa isinya kerentanan pada metode ini.
- Processor wajib menolak cache dengan checksum atau URL sumber salah. Jangan menamai ulang cache bahaya lama menjadi kerentanan.
- Signature publikasi mencakup metode, provenance sumber, grid, TP, ambang, bbox, zoom dan ketersediaan jendela. `publication_id` format `<RUN_ID>-<16 digit hash heksadesimal>`; input identik menghasilkan ID identik.
- Tulis NPZ (`cat`, `rain`, `hazard`, `lats`, `lons`), GeoTIFF kategori uint8 NoData=255 dan tiles WebP lossless z=3..6 di staging; publish setelah lengkap. Gunakan lock eksklusif dan JSON atomik.
- Pointer lama dengan metode/sumber berbeda harus diganti oleh publikasi kerentanan pertama meskipun timestamp run lama lebih baru. Setelah itu jangan memundurkan latest dalam metode/sumber yang sama.
- Publikasi lama jangan dihapus otomatis. API harus menolaknya sebagai hasil metode baru. Status CLI juga jangan melaporkan latest lama sebagai aktif.

### 8.5 API dan UI

Prefix: `/api/landslide/forecast`.

- `GET /status`: HTTP 200, `available` false jika latest tidak cocok metode/sumber; keberadaan file cache saja tidak membuktikan forecast siap.
- `GET /metadata`: HTTP 503 jika belum ada publikasi kerentanan valid; selain itu metadata lengkap, `publication_id`, daftar step, rentang waktu, ambang, zoom, URL tile, provenance dan batasan.
- `GET /tile/{run}/{step}/{z}/{x}/{y}.webp`: run memakai `publication_id`. Validasi run/step/XYZ, tolak publikasi lama, step unavailable atau zoom tak tersedia. Tile di luar domain pada zoom valid boleh transparan; tile dalam domain yang semestinya ada tetapi hilang harus error, bukan disamarkan transparan.
- Jika ada route tanpa `.webp`, perhatikan urutan registrasi FastAPI agar route generik tidak menangkap `y` bernilai `4.webp` lalu menghasilkan 422.
- `GET /point?run=...&step=...&lat=...&lon=...`: run default latest; kembalikan hujan mm, indeks, kelas, kategori, waktu UTC, threshold, versi dan `index_type`. NaN harus menjadi JSON null. Luar grid menghasilkan NoData.
- Sampling kategori titik dan tile wajib sama. Grid reguler memakai cakupan setengah sel, batas atas eksklusif dan tie-break `floor(f + 0.5)`; dukung urutan lintang naik/turun secara konsisten.
- UI memakai timeline yang sama, waktu lokal WIB berlabel, opacity/visibility, legenda dan popup inspeksi teks aman (`textContent`, bukan HTML dari server). Batalkan/abaikan respons lama ketika model/run/step berubah.
- Semua label indeks harus menyebut kerentanan. Nama kategori `Bahaya` adalah kategori eksperimen, bukan bukti sumbernya Indeks Bahaya.
- Tampilkan bahwa produk bukan peringatan resmi, belum tervalidasi, bukan probabilitas, dan `no_trigger` bukan jaminan aman. Jangan menampilkan tile lama untuk step baru yang unavailable.

---

## 9. Acceptance test dan laporan akhir AI

Gunakan data sintetis hanya dalam test terisolasi. Minimum verifikasi:

- Batas indeks 0, 0.333, 0.666, 1, nilai di luar rentang dan NaN.
- Hujan 29.99 dan 30 mm; indeks invalid dengan hujan nol tetap 255.
- Contoh +3/+27 menghasilkan 80 mm; endpoint/baseline hilang, gap/overlap, reset, satuan tidak didukung, grid/run berbeda dan checksum salah ditolak.
- Agregasi spasial, half-cell tie-break, WebP lossless dan kesamaan nilai titik/tile.
- HTTP 503 sebelum data siap, metadata/point/tile valid setelah publikasi test, penolakan metode/sumber lama, serta penggantian latest lama saat migrasi.
- Pemrosesan idempoten dan tidak merusak layer cuaca ketika longsor gagal.
- `python -m pytest tests/` dan `npm run build` dijalankan ulang pada PC tujuan.

Setelah ingest dan proses data **nyata** selesai, uji backend, bukan sekadar output build:

```bash
curl http://127.0.0.1:8000/api/landslide/forecast/status
curl http://127.0.0.1:8000/api/landslide/forecast/metadata
```

PowerShell dapat menggunakan `Invoke-RestMethod -Uri URL` atau `curl.exe`. Ambil `publication_id` dan step `ready: true` dari response nyata untuk permintaan point/tile; jangan hardcode hash contoh. Cocokkan satu query titik dengan output numerik publikasi dan periksa tampilan peta, perubahan timestep, status unavailable serta console browser. Jika data nyata belum tersedia, laporkan bagian tersebut **belum diuji**, bukan lulus.

Baseline PC asal pada 2026-10-18: 23 test lulus dan build berhasil. Warning yang ditemukan: deprecation pytest/Starlette, referensi state Svelte pada modal radar/satelit, autofocus, warning sintaks CSS, dan bundle besar. Ini riwayat verifikasi, bukan hasil PC tujuan. Ingest nasional dan publikasi forecast nyata belum dijalankan pada tahap tersebut.

Laporan akhir wajib berisi:
1. File yang diubah atau source yang dipindahkan, termasuk perubahan pengguna yang dipertahankan.
2. Perintah yang benar-benar dijalankan dan hasilnya; sebutkan kegagalan/warning.
3. Apakah cache BNPB nyata sudah ada dan tervalidasi.
4. Run ECMWF nyata, endpoint jendela yang tersedia dan publication ID bila ada.
5. Status backend/frontend serta pengujian UI yang benar-benar dilakukan.
6. Bagian yang belum selesai, penyebab dan perintah berikutnya. Jangan menyatakan operasional produksi jika hanya test sintetis/build yang lulus.

---

## 10. Prompt singkat untuk PC tujuan

> Baca `docs/AI_EXECUTION_LANDSLIDE.md` sampai selesai. Terapkan instruksinya pada repository ini. Periksa source yang tersedia lebih dahulu; bila implementasi longsor belum ada, bangun sesuai spesifikasi tanpa menduplikasi pipeline ECMWF atau mengubah layer cuaca. Bila sudah ada, audit dan lanjutkan setup serta verifikasi. Gunakan sumber BNPB Indeks Kerentanan yang ditentukan, bukan Indeks Bahaya. Jangan membuat data forecast palsu. Laporkan perubahan, hasil test/build, status data nyata dan pekerjaan yang belum selesai. Minta izin sebelum unduhan nasional besar, penghapusan, atau publikasi keluar PC.
