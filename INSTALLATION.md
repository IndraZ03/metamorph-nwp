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
- **Python 3.9+** (hanya diperlukan bila ingin menjalankan utilitas uji scraper `bmkg-test.py`):
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
