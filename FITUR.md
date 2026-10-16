# Fitur-Fitur Aplikasi Web Metamorph NWP

Dokumentasi lengkap fitur, arsitektur visualisasi data cuaca, dan kapabilitas aplikasi **Metamorph NWP Viewer**.

---

## 1. Peta Dasar & Visualisasi Kartografi (Interactive Basemap)

- **Engine MapLibre GL**: Rendering peta berbasis vektor WebGL berperforma tinggi, mulus saat zoom dan pan di seluruh wilayah Indonesia.
- **Tema Carto Dark Matter**: Tampilan basemap gelap elegan (standar aplikasi Karhutla / Geospasial BMKG) yang mengoptimalkan kontras visual data satelit dan radar cuaca.
- **Layer Batas Wilayah & Pesisir (Refined Boundaries)**:
  - Batas Administrasi Provinsi (`boundary_state`) dengan garis putus-putus halus.
  - Batas Kabupaten/Kota (`boundary_county`) aktif otomatis saat memperbesar skala peta (zoom level ≥ 8).
  - Garis Pantai / Pesisir Pulau (`coastline_outline`) untuk memastikan pulau tetap terlihat jelas meskipun tertutup tutupan awan tebal.
  - Batas Antar Negara (`boundary_country_inner`) dengan outline kontras.
  - Urutan layer dinamis (*z-indexing*): batas darat, pantai, dan label nama kota selalu dipertahankan di atas citra awan/radar agar keterbacaan peta tetap terjaga.
- **Navigasi & Kompas**: Kontrol navigasi zoom in/out dan rotasi peta arah utara di pojok kanan bawah.

---

## 2. Fitur Radar Cuaca BMKG (Weather Radar)

- **Katalog Stasiun Radar Seluruh Indonesia**:
  - Mengambil katalog metadata stasiun radar BMKG langsung via endpoint resmi.
  - Mencakup puluhan stasiun radar di Indonesia (seperti Balikpapan/BAL, Jakarta, Medan, Makassar, Surabaya, dll.).
- **Komposit Reflektivitas CMAX (dBZ)**:
  - Menampilkan produk *Column Maximum* (CMAX) reflektivitas awan penghasil hujan.
  - Overlay citra radar dipetakan tepat pada koordinat geografis stasiun berdasarkan *bounding box* spesifik stasiun (TLC & BRC).
- **Auto Fly-To Stasiun**:
  - Kamera peta secara otomatis meluncur (*fly-to smooth animation*) memusatkan pandangan dan zoom ke stasiun radar yang dipilih.
- **Pengaturan Transparansi (Opacity Slider)**:
  - Fleksibilitas mengatur tingkat transparansi layer radar (0% – 100%) langsung dari modal sebelum diterapkan ke peta.
- **Skala Warna & Bar Reflektivitas**:
  - Legenda skala dBZ interaktif (mulai dari 5 dBZ warna cyan hingga 70 dBZ warna ungu pekat) di panel kontrol aktif pojok kiri bawah.

---

## 3. Fitur Citra Satelit Cuaca Himawari-9

- **Observasi Resolusi Tinggi Tiap 10 Menit**:
  - Akses citra satelit meteorologi geostasioner Himawari-9 terkini secara hampir seketika (*near real-time*).
- **Pilihan Kanal Produk Spektral**:
  1. **Visible (VS)**:
     - Citra optik kanal tampak resolusi tinggi untuk memantau tutupan awan fisik di siang hari.
  2. **Enhanced / Infrared (EH)**:
     - Citra inframerah dengan skema pewarnaan temperatur puncak awan (*cloud-top temperature*) untuk mendeteksi potensi awan konvektif tebal (seperti Cumulonimbus / Cb).
- **Protokol TMS (Tile Map Service)**:
  - Integrasi tile raster piramidal multi-resolusi `{z}/{x}/{y}.png` yang ringan, cepat dimuat, dan hemat bandwidth.
- **Dynamic Baserun Resolver**:
  - Algoritma otomatis memindai dan mendeteksi ketersediaan timestamp UTC terbaru yang berstatus `200 OK` (menghindari kegagalan tile 404 akibat lag upload BMKG).
- **Timeline / Pemutar Riwayat Baserun (Historical Runs)**:
  - Panel kontrol dilengkapi *dropdown / switcher* riwayat waktu observasi UTC hingga beberapa jam ke belakang.

---

## 4. Toolbar Aksi Cepat (Circular Action Toolbar)

Toolbar mengambang di sisi kanan layar untuk akses satu klik ke seluruh modal dan model cuaca:
- **Tombol Radar**: Membuka modal pemilihan stasiun radar.
- **Tombol Satelit**: Membuka modal kanal satelit Himawari-9.
- **Status Indikator Aktif**: Dilengkapi indikator cincin bercahaya dan titik hijau berkedip (*pulsing badge*) jika suatu layer sedang tayang di peta.
- **Tooltip Cerdas**: Penjelasan nama tombol saat kursor diarahkan (*hover*).
- **Tombol Model NWP Masa Depan (Upcoming Features)**:
  - Disediakan tombol slot model prediksi cuaca numerik:
    - **ECMWF** (*European Centre for Medium-Range Weather Forecasts*)
    - **AROME**
    - **ACCESS-R**
    - **CAWO**
    - **WRF** (*Weather Research and Forecasting*)
    - **WRF-Chem** (Kimia/Kualitas Udara)
  - Ditandai dengan label status *"segera"*.

---

## 5. Panel Kontrol Layer Aktif & Legenda (Layer Control)

Terletak di pojok kiri bawah layar, berfungsi sebagai pusat informasi data yang sedang dimuat:
- **Status & Nama Layer Aktif**: Menampilkan nama radar/satelit beserta format produknya.
- **Waktu Observasi & Frame File**: Informasi presisi mengenai file frame radar atau timestamp UTC satelit yang sedang dilihat.
- **Legenda dBZ**: Visual panduan nilai reflektivitas untuk interpretasi intensitas hujan secara langsung.
- **Tombol Hapus Layer**: Tombol silang (*close button*) untuk menonaktifkan layer radar atau satelit secara independen tanpa memuat ulang halaman.

---

## 6. Backend Dev Proxy (Bypass CORS & Anti-Hotlinking)

Aplikasi dilengkapi middleware server lokal berbasis Vite untuk memastikan reliabilitas penarikan data BMKG:
- `/api/proxy-cuaca`: Meneruskan permintaan katalog JSON radar dan satelit dari server `cuaca.bmkg.go.id`.
- `/api/proxy-satellite-tile`: Menyediakan streaming tile citra satelit resolusi tinggi dari `satellite.bmkg.go.id` lengkap dengan header `Referer` dan `User-Agent` yang valid.
- **Caching**: Response header dilengkapi `Cache-Control` lokal agar pengulangan zoom peta tidak membebani kuota jaringan dan server asal.

---

## 7. Desain & Antarmuka Modern (UI/UX)

- **Header Branding**: Kartu identitas elegan di kiri atas dengan logo resmi BMKG dan METAMORPH dilengkapi efek *glassmorphism backdrop blur*.
- **State Management Svelte 5**: Dibangun menggunakan sistem *Runes* terbaru Svelte 5 (`$state`, `$derived`, `$props`) yang reaktif, cepat, dan hemat memori.
- **Desain Responsif**: Penataan tata letak otomatis rapi untuk berbagai resolusi layar desktop, laptop, dan monitor operasional.
