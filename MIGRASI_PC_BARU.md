# Panduan Migrasi Metamorph NWP ke PC Windows Baru

Panduan ini untuk memindahkan proyek beserta data ECMWF, GFS, ICON, longsor, dan banjir. Prioritas: gunakan data yang sudah tersedia dahulu, baru aktifkan pembaruan otomatis.

## 1. Persiapan PC baru

- Windows 10/11 64-bit.
- Node.js dan npm. Dokumentasi mencatat minimum Node.js 18; gunakan rilis LTS yang masih didukung.
- Git for Windows bila ingin mempertahankan workflow Git.
- Python beserta pip dan dukungan virtual environment.
- Internet untuk memasang dependensi, peta dasar/feed daring, dan memperbarui prakiraan.
- SSD dengan ruang kosong cukup untuk ukuran folder sumber, dependensi, serta tambahan data hasil unduhan/proses. Ukuran dataset belum diukur; periksa Properties folder sebelum menyalin.

### Versi referensi PC lama

Versi berikut terverifikasi pada PC sumber, **bukan minimum wajib**:

| Komponen | Versi |
|---|---|
| Node.js | v24.16.0 |
| npm | 11.13.0 |
| Python pada `.venv` | 3.14.5 |
| Git | 2.54.0.windows.1 |

Dokumentasi proyek mencatat Python 3.10+, sedangkan `engine/environment.yml` menggunakan Python 3.12. Untuk lingkungan baru, Python 3.12 melalui Conda merupakan pilihan yang tercatat untuk dependensi geospasial/native. Jangan menganggap seluruh wheel native tersedia untuk setiap versi Python terbaru.

## 2. Backup dan salin dari PC lama

**Penting: clone Git saja tidak cukup. Ada perubahan lokal yang belum semuanya masuk commit.**

1. Hentikan updater dan proses penulisan data sebelum menyalin agar manifest dan tile konsisten. Simpan backup sumber; jangan hapus proyek lama.
2. Salin folder proyek ke drive eksternal atau jaringan, lalu ke PC baru, misalnya `C:\metamorph-nwp`.
3. Pertahankan kode lokal, `package.json`, `package-lock.json`, konfigurasi proyek, dan folder data di bawah.
4. Jangan membawa `node_modules` atau `.venv` sebagai pengganti instalasi baru. Keduanya dibuat ulang di PC tujuan.
5. Folder build sementara, log, dan `.claude/worktrees` tidak diperlukan untuk menjalankan aplikasi. Folder `.git` berguna bila ingin mempertahankan riwayat serta status perubahan lokal.

### Folder data yang harus ikut

| Folder | Isi/fungsi |
|---|---|
| `engine/output` utuh | Hasil ECMWF, tile visual/numerik, manifest, longsor, banjir |
| `data` utuh | Data GFS, ICON, grids, cache, dan metadata updater |
| `public` | Aset statis aplikasi |
| `src`, `backend`, `engine` | Kode aplikasi dan pemrosesan |

Jangan hanya menyalin gambar WebP. Metadata, manifest, file latest, serta data numerik diperlukan untuk timeline, meteogram, dan inspeksi titik.

Rincian data bencana yang perlu dipertahankan:

```text
engine/output/landslide/
  hazard/
  precipitation/
  runs/
  latest.json
  status.json

engine/output/flood/
  sources/
  history/
  runs/
  latest.json
  status.json
```

Banjir menggunakan data hujan bersama dari `engine/output/landslide/precipitation`. Jangan menghapus folder tersebut meskipun hanya memakai banjir.

Data model lain berada antara lain di:

```text
data/gfs/
data/tiles/icon/
data/tiles_numeric/icon/
data/grids/icon/
data/cache/
data/updater/
```

Jika ada konfigurasi lokal atau variabel lingkungan khusus, catat nilainya untuk dipasang ulang. Jangan membagikan token, kredensial, atau file rahasia ke repositori publik. Isi konfigurasi rahasia PC lama belum diinventarisasi dalam panduan ini.

## 3. Instal dependensi frontend

Buka PowerShell di PC baru:

```powershell
Set-Location C:\metamorph-nwp
node --version
npm --version
npm ci
```

`npm ci` memakai `package-lock.json` agar versi dependensi mengikuti proyek. Jika lockfile tidak cocok dengan `package.json`, periksa perbedaannya; jangan langsung menghapus lockfile.

## 4. Instal Python dan dependensi backend/engine

Pilih **salah satu** lingkungan berikut.

### Pilihan A — Conda, sesuai environment proyek

Pasang Miniconda/Miniforge, lalu jalankan pada terminal yang mengenali `conda`:

```powershell
Set-Location C:\metamorph-nwp
conda env create -f engine/environment.yml
conda activate ecmwf
python -m pip install -r engine/requirements.txt -r engine/gfs/requirements.txt -r backend/requirements.txt
```

Environment YAML saja belum mencakup semua dependensi backend/GFS. Tetap jalankan pemasangan gabungan requirements.

Untuk seluruh perintah berikut yang menggunakan `.\.venv\Scripts\python.exe`, ganti dengan `python` jika menggunakan Conda. Aktifkan `conda activate ecmwf` di setiap terminal backend/updater.

### Pilihan B — Python native dan `.venv`

Pastikan `python` menunjuk instalasi Python yang dipilih, bukan alias Microsoft Store.

```powershell
Set-Location C:\metamorph-nwp
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r engine/requirements.txt -r engine/gfs/requirements.txt -r backend/requirements.txt
```

Tidak perlu mengaktifkan `.venv` bila memanggil `python.exe` dengan path lengkap.

### Dependensi native penting

- **ecCodes**: diperlukan untuk membaca GRIB. Paket Python terpasang belum selalu berarti library native sudah bisa ditemukan.
- **rasterio/GDAL**: diperlukan pemrosesan raster longsor dan banjir. Gunakan paket/wheel yang cocok dengan versi Python dan Windows; jangan memasang kombinasi native secara acak.
- WSL **bukan syarat wajib** menurut panduan instalasi terbaru proyek.

Cek impor dasar:

```powershell
.\.venv\Scripts\python.exe -c "import fastapi, uvicorn, rasterio, xarray, cfgrib, eccodes; print('Import dependency OK')"
.\.venv\Scripts\python.exe -m pip check
```

Cek ini belum membuktikan seluruh proses decode GRIB atau pemrosesan nasional berhasil. Untuk updater, jalankan preflight pada bagian 7.

## 5. Nyalakan web dan layanan longsor/banjir

Gunakan dua terminal terpisah. Biarkan keduanya terbuka.

### Terminal 1 — Backend API

```powershell
Set-Location C:\metamorph-nwp
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8003
```

Alternatif entry point proyek:

```powershell
.\.venv\Scripts\python.exe -m backend.run_engine --serve --port 8003
```

Pilih salah satu, bukan keduanya. Entry point proyek memakai host `0.0.0.0`; perintah Uvicorn di atas membatasi akses ke PC sendiri. Default port CLI proyek adalah `8000`, jadi tulis `--port 8003` agar cocok dengan proxy frontend.

### Terminal 2 — Frontend

```powershell
Set-Location C:\metamorph-nwp
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Buka:

```text
http://127.0.0.1:5173/
```

Vite melayani data ECMWF/GFS/ICON langsung dari folder lokal. API longsor dan banjir diteruskan ke backend `http://127.0.0.1:8003`.

Jika backend sengaja dipindah ke alamat/port lain, atur sebelum menjalankan frontend:

```powershell
$env:NWP_API_ORIGIN = 'http://127.0.0.1:8003'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Jangan membuka port ke internet untuk migrasi lokal ini. Akses dari perangkat lain memerlukan pengaturan host, firewall, dan keamanan tersendiri.

## 6. Verifikasi hasil migrasi

Pada terminal ketiga:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8003/health'
Invoke-RestMethod 'http://127.0.0.1:5173/api/landslide/forecast/status'
Invoke-RestMethod 'http://127.0.0.1:5173/api/flood/forecast/status'
```

Periksa di browser:

- Peta dasar tampil.
- Layer ECMWF, GFS, dan ICON yang datanya disalin tampil.
- Timeline memuat run dan waktu prakiraan yang sesuai.
- Klik titik peta; nilai numerik dan meteogram tampil.
- Layer longsor dan banjir bisa dibuka; status tersedia dan waktu publikasinya benar.
- Wind barb terlihat dan kontrol timeline berfungsi.

HTTP 200 saja tidak cukup: beberapa tile yang hilang bisa dibalas gambar transparan. Pastikan layer benar-benar terlihat dan nilai numerik tersedia.

Data hasil salin tidak otomatis menjadi prakiraan terbaru. Periksa waktu run sebelum dipakai.

## 7. Pembaruan otomatis — setelah migrasi lolos

Jangan langsung menjalankan download, ingest BNPB, rebuild, atau cleanup pada validasi pertama. Gunakan hasil proses yang sudah disalin dahulu.

Cek kesiapan updater:

```powershell
Set-Location C:\metamorph-nwp
.\.venv\Scripts\python.exe -m engine.hourly --preflight
.\.venv\Scripts\python.exe -m engine.retention --dry-run
```

`--dry-run` tidak menghapus data, tetapi dapat membuat lock/direktori konfigurasi.

**Peringatan: perintah berikut melakukan unduhan dan cleanup nyata. Retensi dapat menghapus prakiraan dengan waktu valid lebih lama dari UTC sekarang dikurangi 15 jam. Simpan backup dan periksa hasil dry-run sebelum melanjutkan.**

Jika sudah siap:

```powershell
.\.venv\Scripts\python.exe -m engine.hourly --once
```

Untuk memasang task berkala pada lingkungan `.venv`:

```powershell
.\install-hourly.ps1 -Python 'C:\metamorph-nwp\.venv\Scripts\python.exe'
Get-ScheduledTask -TaskName 'Metamorph-NWP-Hourly'
```

Sesuaikan path jika folder proyek berbeda. Untuk Conda, gunakan path absolut `python.exe` dari environment `ecmwf`, bukan path `.venv` contoh di atas. Task PC lama tidak otomatis ikut pindah.

Jalankan task secara manual bila ingin mengujinya:

```powershell
Start-ScheduledTask -TaskName 'Metamorph-NWP-Hourly'
```

Alternatif pemrosesan ECMWF sekali, bila memang diperlukan:

```powershell
.\.venv\Scripts\python.exe -m engine.run --once
```

Unduh ulang tidak menjamin run historis lama masih tersedia. Jangan memakai data sintetis smoke test sebagai pengganti prakiraan aktual.

## 8. Internet dan sumber data

Akses jaringan diperlukan sesuai fitur yang dipakai:

- ECMWF Open Data.
- DWD Open Data untuk ICON.
- Penyedia data GFS yang dikonfigurasi engine.
- BNPB/InaRISK untuk ingest sumber longsor dan banjir.
- BMKG untuk feed satelit terkait.
- Penyedia peta dasar dan reverse geocoding Nominatim.

Salin cache/output lama mengurangi kebutuhan mengunduh ulang dan memproses raster besar. Namun feed daring tetap tidak tersedia ketika offline. Periksa izin/lisensi sebelum membagikan ulang data BNPB secara publik.

Longsor dan banjir merupakan produk **eksperimental**, bukan pengganti peringatan dini resmi.

## 9. Masalah umum

| Gejala | Pemeriksaan/perbaikan |
|---|---|
| Web tidak bisa dibuka | Pastikan terminal Vite masih hidup dan port `5173` sesuai |
| Port sudah dipakai | Jangan menyalakan server duplikat; periksa proses yang memakai port |
| Longsor/banjir mendapat 503 | Pastikan backend aktif pada `8003` dan `NWP_API_ORIGIN` sesuai |
| Peta ada tetapi layer kosong | Periksa folder data, manifest/latest, run terkait, dan waktu prakiraan |
| Meteogram tidak punya nilai | Pastikan tile/data numerik ikut disalin, bukan hanya visual WebP |
| `ModuleNotFoundError` | Jalankan Python dari environment yang sama dengan tempat requirements dipasang |
| ecCodes tidak ditemukan | Periksa library native ecCodes dan kecocokan lingkungan Python |
| Rasterio/GDAL gagal dipasang | Gunakan versi Python/wheel yang didukung atau lingkungan Conda proyek |
| Task otomatis tidak berjalan | Pasang ulang task dengan path Python/proyek PC baru dan cek hasil preflight |
| PowerShell menolak script instalasi task | Periksa kebijakan script Windows; jangan menonaktifkan perlindungan secara global |

## Checklist akhir

- [ ] Backup PC lama masih tersedia.
- [ ] Kode lokal terbaru ikut tersalin, termasuk perubahan belum commit.
- [ ] `engine/output` dan `data` tersalin utuh.
- [ ] Dependensi Node.js terpasang ulang.
- [ ] Lingkungan Python dibuat ulang dan requirements terpasang.
- [ ] Backend port `8003` sehat.
- [ ] Web port `5173` bisa dibuka.
- [ ] ECMWF/GFS/ICON dan data numerik diperiksa.
- [ ] Status longsor/banjir serta waktu run diperiksa.
- [ ] Updater baru diaktifkan setelah backup dan validasi.

## Referensi proyek

- `INSTALLATION.md`
- `engine/environment.yml`
- `engine/requirements.txt`
- `engine/gfs/requirements.txt`
- `backend/requirements.txt`
- `docs/LANDSLIDE_EXPERIMENTAL.md`
- `docs/FLOOD_EXPERIMENTAL.md`

Panduan disusun 22 Oktober 2026 dari konfigurasi dan dokumentasi proyek. Instalasi pada PC tujuan belum diuji; ukuran serta kelengkapan seluruh dataset dan konfigurasi rahasia lokal belum diinventarisasi.
