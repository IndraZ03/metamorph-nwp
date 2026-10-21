# Dokumentasi Teknis Meteogram Metamorph-NWP

## 1. Ringkasan & Desain Interaksi
Meteogram titik meteorologi diimplementasikan sebagai panel **Bottom Sheet non-modal** berbasis Svelte 5 runes dengan integrasi **Apache ECharts (modular & lazy-loaded)**.

### Perilaku Interaksi:
- **Pemicu Pembukaan:** Tombol **Meteogram** muncul di dalam popup inspect NWP tepat di bawah daftar nilai meteorologi setelah pengguna mengklik peta. Klik peta tidak membuka sheet secara otomatis; pengguna memiliki kontrol penuh.
- **Tiga State Sheet:**
  - `closed`: sheet tersembunyi, variabel CSS `--meteogram-visible-height` bernilai `0px`.
  - `half`: tinggi ~48vh (maks 440px), ideal untuk melihat grafik suhu & hujan sekaligus peta.
  - `expanded`: tinggi ~78vh (maks viewport aman), menampilkan detail lengkap dan multi-subplot.
- **Timeline Sibling:** `ForecastTimeline` tetap menjadi sibling (bukan child) dari meteogram. Posisinya digerakkan dinamis melalui `calc(var(--meteogram-visible-height, 0px) + 16px)` dalam `requestAnimationFrame` yang sama dengan sheet.
- **Sinkronisasi Waktu:**
  - Klik/Enter pada grafik atau tabel meteogram mengikat waktu ke langkah prakiraan terdekat via `nearestStep(nwpSteps, timestamp)` dan memanggil `seekNwpStep`.
  - Menggeser timeline peta hanya memperbarui crosshair/sorotan grafik tanpa melakukan fetch ulang atau `setOption` penuh.

---

## 2. Pemetaan Parameter Model (ECMWF, GFS, ICON)

| Field Normalisasi | Unit | ECMWF | GFS | ICON | Catatan Ilmiah & Semantik |
|---|---|---|---|---|---|
| `temperatureC` | °C | `t2m` | `temperature` | `t_2m` | Suhu udara permukaan pada ketinggian 2 meter. |
| `dewPointC` | °C | `d2m` | `dew_point` | `td_2m` | Titik embun 2 meter. |
| `relativeHumidityPct` | % | `rh` | `rh` | `relhum_2m` | Kelembapan relatif 2 meter (0–100%). |
| `pressureHpa` | hPa | `msl` | `pressure` | `pmsl` | Tekanan udara tereduksi ke permukaan laut (MSLP). |
| `totalCloudCoverPct` | % | `tcc` × 100 | `clouds` | `clct` | ECMWF menyimpan fraksi 0–1; GFS & ICON persen (0–100%). |
| `precipitationMm` | mm | `tp` (kumulatif) | `rain` (window) | `tot_prec` (kumulatif) | Dihitung per interval aktual (lihat Bagian 3). |
| `windSpeedMs` | m/s | `wind10m` | `wind` | Diturunkan dari U/V | Kecepatan angin rata-rata 10 meter. |
| `windDirectionDeg` | ° | `u10`, `v10` | `u10`, `v10` | `u_10m`, `v_10m` | Arah meteorologis *FROM* (0° Utara, 90° Timur, 180° Selatan, 270° Barat). Kondisi tenang (*calm*) bernilai `null`. |
| `maximumWindMs` | m/s | — | — | `wind_10m` | **Perhatian:** Field `wind_10m` pada ICON bersumber dari `VMAX_10M` (hembusan maksimum), bukan angin rata-rata. |
| `capeJkg` | J/kg | `cape` | `cape` | `cape_ml` | Most-unstable (ECMWF), Surface (GFS), Mixed-layer (ICON). |

---

## 3. Logika Akumulasi & Differencing Hujan
- **ECMWF & ICON (Kumulatif):**
  - Nilai pada jam awal (baseline) tidak diasumsikan 0; interval dihitung dari selisih `rawRain[i] - rawRain[i-1]`.
  - Jika terjadi penurunan kumulatif (*reset* model atau run baru), selisih negatif **tidak diisi nol atau nilai saat ini**, melainkan bernilai `null` sampai pasangan baru yang kompatibel terbentuk.
- **GFS (Jendela Waktu Eksplisit):**
  - Parsing string rentang seperti `"0-1 hour acc fcst"` atau `"3-6 hours"`.
  - Hanya jendela berturut-turut dari origin yang sama yang dihitung selisihnya jika saling bertumpuk. Jendela yang tidak valid atau ambigu tidak diubah menjadi mm/jam rekaan.

---

## 4. Sampling & Caching
- **Metode Sampling:** Pengambilan sampel berbasis pixel pada tile WebP numerik terrain-RGB (`readNumericPixel`). Nilai didekode via formula `((R * 65536 + G * 256 + B) / 10) - 1000`. Nilai alpha 0 adalah `nodata`.
- **Presisi:** 0.1 unit sumber.
- **Pembekuan Zoom:** Zoom sampling dibekukan pada zoom maksimum yang didukung model saat titik dipilih agar resolusi sampel konsisten saat peta di-zoom oleh pengguna.
- **Batas Konkurensi:** Worker pool membatasi konkurensi fetch maksimum **6 request aktif simultan** (`runWithConcurrency`).
- **Signature Kesiapan Cache:** Cache `_seriesCache` menggunakan `meteogramManifestKey` yang mengabaikan field dinamis seperti `updated_at`, sehingga polling berkala yang tidak mengubah run atau timestep tidak memicu refetch yang sia-sia.
- **Deduplikasi:** Timestep duplikat dalam manifest secara otomatis disaring.

---

## 5. Hasil Verifikasi, Pengujian & Palet
- **Pengujian Unit Otomatis (`node:test`):**
  - Seluruh 63 pengujian lulus (53 baseline regresi + 10 suite baru `meteogram.test.js`).
  - Menguji: konversi angin vektor ke skalar & arah FROM, parsing GFS rain window, differencing kumulatif & reset ECMWF, status kondisi unknown, konsistensi cache key & manifest signature, validasi koordinat luar wilayah, kepatuhan batas konkurensi <= 6, mock sampling ECMWF, dan penanganan GFS/ICON VMAX.
- **Hasil Build Bundle (`npm run build`):**
  - ECharts dimuat secara modular dan dinamis (*lazy code-splitting*). Chunks grafik (`charts`, `components`, `renderers`) terisolasi dari bundle awal halaman peta (`index--*.js`).
- **Audit Palet Warna:**
  - Suhu: `#F08D82`, Hujan: `#68B8D8`, Latar Surface: `#13171c`.
  - *CVD Separation:* PASS (ΔE 12.5 protan, 27.7 tritan).
  - *Normal-vision Floor:* PASS (ΔE 21.1 normal).
  - *Contrast vs Surface:* PASS (>= 3:1 WCAG).
  - *Catatan Lightness/Chroma:* Lightness berada di 0.74 (di atas batas dark mode 0.67 pada validator) untuk mempertahankan keterbacaan tinggi di atas surface gelap.

---

## 6. Batasan Operasional & Data Saat Ini
1. **Klasifikasi Kondisi Cuaca:** Belum ada aturan kode cuaca atau ambang operasional yang disetujui secara resmi. Meteogram dengan jujur menampilkan status *"Kondisi tidak tersedia"* dan tidak mengarang ikon/kondisi cuaca.
2. **Ketersediaan Timestep Lokal:** Manifest lokal ICON saat ini hanya menyediakan step `000` tanpa komponen angin vektor U/V. Grafik menampilkan data titik tunggal (*single point*) secara akurat tanpa mengekstrapolasi kurva palsu.
