# Panduan Instalasi di PC Baru (Metamorph NWP)

Dokumen ini berisi langkah lengkap instalasi dan setup proyek **Metamorph NWP** pada perangkat/PC baru.

---

## 1. Prasyarat Sistem (Prerequisites)

Sebelum mulai, pastikan perangkat baru sudah terpasang perangkat lunak berikut:

### Wajib:
1. **Git**
   - Download: [git-scm.com](https://git-scm.com/downloads)
   - Verifikasi instalasi di terminal:
     ```bash
     git --version
     ```
2. **Node.js** (Rekomendasi versi LTS: Node.js 18.x atau 20.x ke atas)
   - Download: [nodejs.org](https://nodejs.org/)
   - Verifikasi di terminal (Node & NPM):
     ```bash
     node -v
     npm -v
     ```

### Opsional (Rekomendasi Developer):
- **Visual Studio Code**: [code.visualstudio.com](https://code.visualstudio.com/)
  - Ekstensi pendukung di VS Code:
    - *Svelte for VS Code* (`svelte.svelte-vscode`)
    - *Tailwind CSS IntelliSense* (`bradlc.vscode-tailwindcss`)
    - *ESLint* / *Prettier*
- **Python 3.10+** (diperlukan untuk engine ECMWF/GFS/ICON, updater otomatis, dan utilitas `bmkg-test.py`; frontend saja tidak memerlukannya):
  - Download: [python.org](https://www.python.org/)
  - Verifikasi: `python --version`

---

## 2. Langkah Instalasi Langkah demi Langkah

### Langkah 1: Setup Identitas Git (Jika Git baru diinstall)
Jalankan perintah ini sekali di terminal PC baru:
```bash
git config --global user.name "Nama Anda"
git config --global user.email "email@anda.com"
```

### Langkah 2: Clone Repository
Pilih direktori kerja yang diinginkan, buka Terminal / PowerShell, lalu clone repo:
```bash
git clone https://github.com/username/metamorph-nwp.git
```
*(Ganti URL di atas dengan URL remote Git proyek Anda jika menggunakan SSH atau repo private).*

Masuk ke folder proyek:
```bash
cd metamorph-nwp
```

### Langkah 3: Install Dependencies
Jalankan package manager untuk mengunduh seluruh library yang dibutuhkan:
```bash
npm install
```

Paket utama yang akan terpasang otomatis:
- **Svelte 5** & **Vite** (Core framework & bundler)
- **Tailwind CSS** & **Skeleton UI** (Styling & komponen UI)
- **MapLibre GL** (Peta interaktif & visualisasi spasial radar/satelit)
- **Lucide Svelte** (Koleksi icon)

---

## 3. Menjalankan Aplikasi di Mode Development

Untuk menyalakan server lokal development:
```bash
npm run dev
```

Output terminal akan menampilkan URL lokal:
```text
  VITE v5.4.10  ready in 350 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

Buka peramban (browser) dan akses alamat:
```
http://localhost:5173
```

Aplikasi siap digunakan dan mendukung Hot Module Replacement (HMR). Setiap perubahan kode di folder `src/` akan langsung dimuat ulang otomatis di browser.

---

## 4. Build untuk Production

Jika ingin membuat bundle siap deploy:

1. **Build aset produksi:**
   ```bash
   npm run build
   ```
   File hasil kompilasi akan tersimpan di dalam folder `dist/`.

2. **Preview hasil build secara lokal:**
   ```bash
   npm run preview
   ```

---

## 5. Pengujian Utilitas BMKG (Opsional)

Proyek ini menyertakan skrip Python `bmkg-test.py` untuk menguji ketersediaan feed radar cuaca dan satelit Himawari-9 BMKG secara mandiri.

Jalankan perintah:
```bash
python bmkg-test.py
```
Hasil uji dan contoh file citra akan tersimpan ke folder `samples/`.

---

## 6. Masalah Umum & Solusi (Troubleshooting)

### A. PowerShell Script Execution Disabled (Windows)
Jika saat menjalankan `npm run dev` muncul error:
`File ... cannot be loaded because running scripts is disabled on this system.`

**Solusi:**
Buka PowerShell as Administrator, jalankan:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### B. Port 5173 Sudah Digunakan
Jika port 5173 terpakai oleh aplikasi lain, Vite akan otomatis beralih ke port berikutnya (misal 5174). Anda juga bisa memaksa port tertentu melalui:
```bash
npm run dev -- --port 3000
```

### C. Masalah Instalasi Dependencies (`node_modules`)
Jika terjadi konflik versi dependensi pada instalasi baru:
```bash
# Hapus cache dan folder lama
npm cache clean --force
rm -rf node_modules package-lock.json

# Install ulang
npm install
```

### D. Versi Node.js Tidak Cocok
Svelte 5 dan Vite 5 membutuhkan Node.js **versi 18.0.0 atau lebih tinggi**.
Periksa versi Anda dengan `node -v`. Jika versi lebih rendah, lakukan update Node.js via installer resmi atau gunakan Node Version Manager (seperti `nvm-windows` / `fnm`).

## Updater forecast Windows tanpa jendela

Gunakan checkout permanen, bukan worktree agen. Python dan `pythonw.exe` harus berasal dari environment yang sama; jangan gunakan alias WindowsApps. Instal dependensi dari `engine/requirements.txt`, `engine/gfs/requirements.txt`, dan `backend/requirements.txt` pada environment pilihan, termasuk library native ecCodes. Jalankan dari root proyek:

```powershell
& 'C:\Python314\python.exe' -m engine.hourly --preflight
& 'C:\Python314\python.exe' -m engine.retention --dry-run
```

Preflight memeriksa modul dan library ecCodes. Pada environment implementasi Python 3.14 tersedia tetapi dependensi engine belum terpasang; aktivasi task diblokir sampai preflight berhasil. Periksa kompatibilitas wheel/native library sebelum memilih versi Python.

Retensi berlaku untuk **valid_time < UTC sekarang - 15 jam**, bukan umur run. Batas tepat 15 jam dan forecast masa depan tetap disimpan, termasuk run lama. Manifest diperbarui atomik sebelum artefak dihapus. Nama tak dikenal dipertahankan. Dry-run hanya inventaris, tidak mengubah manifest/forecast; file lock dan direktori konfigurasi dapat dibuat. Tinjau inventaris dan konfirmasi cakupan sebelum menjalankan mode nyata.

Setelah persetujuan inventaris, pengujian manual nyata: `& 'C:\Python314\python.exe' -m engine.hourly --once`. Ini melakukan download dan cleanup nyata. Daemon default interval 3600 detik, timeout total per model 21600 detik (6 jam); gunakan `--timeout` lebih besar untuk bake panjang. Model berjalan sebagai subprocess terpisah, tidak overlap antarsiklus. Exit sukses pipeline belum menjamin semua timestep tersedia; periksa status/ready/params pada manifest dan log untuk hasil parsial. Log berotasi: `data/updater/hourly.log`; lock OS dilepas saat proses mati.

Pemasangan (tidak otomatis menjalankan task):

```powershell
.\install-hourly.ps1 -Python 'C:\Python314\python.exe'
Get-ScheduledTask -TaskName 'Metamorph-NWP-Hourly'
Start-ScheduledTask -TaskName 'Metamorph-NWP-Hourly'
Stop-ScheduledTask -TaskName 'Metamorph-NWP-Hourly'
.\install-hourly.ps1 -Uninstall
```

Installer memakai login pengguna saat ini, hak terbatas, `pythonw.exe`, working directory checkout, IgnoreNew, retry crash, tanpa batas durasi task. Task tak dikenal tidak ditimpa; task managed harus dihapus eksplisit sebelum reinstall. Stop task menghentikan daemon; penghentian paksa Task Scheduler belum diverifikasi untuk seluruh child process. Periksa proses Python milik updater sebelum restart; jangan menghentikan proses Python lain. Timeout normal membunuh dan menunggu child yang dimiliki runner. Lock dilepas OS saat pemilik mati. PC mati/sleep berarti tidak ada pembaruan; setelah bangun daemon melanjutkan tanpa mengejar jadwal tertinggal. Pemeriksaan tiap jam tidak menjamin provider menerbitkan run tiap jam. Task native Windows telah dipasang pada checkout ini; status runtime harus tetap diperiksa, bukan diasumsikan dari konfigurasi task.

### Pemeriksaan kebaruan otomatis

```powershell
& '.\engine\.venv\Scripts\python.exe' -m engine.health --check --json
```

Perintah ini read-only: membandingkan run lokal dengan run terbaru yang terkonfirmasi pada penyedia dan memeriksa parameter serta keberadaan sampel artefak visual/numeric. Bukan pemeriksaan integritas seluruh tile atau jaminan seluruh horizon upstream sudah dipublikasikan. Exit 0 hanya jika semua model `healthy`; jaringan gagal menghasilkan `unknown`, bukan sukses. Updater menyimpan hasil sebelum/sesudah siklus pada `data/updater/status.json`, termasuk `checked_at` dan `last_verified_at`. Status tersebut snapshot, bukan heartbeat real-time; periksa umurnya. Siklus gagal dicoba kembali setelah maksimal 5 menit menunggu, tanpa menumpuk worker. Bake panjang tetap dibatasi timeout total 6 jam.

TLS Windows menggunakan `truststore` dan certificate store OS. Verifikasi sertifikat tetap aktif; jangan gunakan `verify=False`. Semua eksekusi menggunakan Python native, tidak membutuhkan WSL.
