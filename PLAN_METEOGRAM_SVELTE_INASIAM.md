# IMPLEMENTATION PLAN — METEOGRAM BOTTOM SHEET UNTUK SVELTE WEATHER VIEWER

> Target: menambahkan meteogram profesional yang terinspirasi pola interaksi INA-SIAM ke aplikasi cuaca Svelte yang **sudah ada**, tanpa merombak peta, timeline, data pipeline, atau desain global. Fokus: ringan, padat informasi, tidak terlihat seperti template AI generik.

## 0. Instruksi utama untuk Claude Code

1. **Audit project terlebih dahulu**: versi Svelte/SvelteKit, komponen MapLibre, timeline prakiraan, store/runes, format data NWP, endpoint/API, styling, unit/timezone, mekanisme pemilihan lokasi, dan dependensi chart yang sudah terpasang.
2. Tampilkan ringkasan temuan dan rencana file yang akan dibuat/diubah sebelum implementasi. Jika komponen chart existing sudah memenuhi kebutuhan, **reuse** daripada memasang library baru.
3. Implementasi bertahap dengan perubahan kecil dan terisolasi. Jangan membuat halaman baru, mengganti layout utama, atau menimpa fitur timeline existing.
4. Jangan mengarang data, field, endpoint, nama model, kondisi cuaca, ataupun ambang operasional. Jika data kurang, tampilkan status 'Tidak tersedia' dan dokumentasikan kebutuhan data.
5. Jangan menggunakan mock data dalam jalur produksi. Mock boleh hanya untuk story/demo/test yang diberi label jelas.
6. Ikuti pola TypeScript, lint, formatter, test, dan komponen UI yang sudah ada. Utamakan aksesibilitas dan performa.

## 1. Hasil akhir dan pengalaman pengguna

- Klik lokasi di peta MapLibre → tampil marker terpilih → request meteogram untuk titik tersebut → bottom sheet muncul dari bawah.
- Sheet memiliki state `closed`, `half` (~45–50vh), dan `expanded` (~75–80vh, dibatasi agar header/timeline tetap dapat digunakan). Pada mobile gunakan batas viewport yang aman.
- **Timeline prakiraan existing tidak hilang**. Timeline selalu berada tepat di atas tepi sheet saat terbuka; ketika sheet ditutup kembali ke posisi semula. Timeline **bukan child** dari meteogram.
- Drag handle untuk memperbesar/mengecilkan panel; close button dan tombol expand/collapse; tidak perlu animasi berlebihan.
- Tab `Overview`, `Temperature`, `Precipitation`, `Wind`, `Atmosphere` hanya ditampilkan jika datanya didukung. Overview menampilkan suhu (line + subtle area fill), hujan (bars), ikon kondisi cuaca mengikuti kurva suhu, dan arah/kecepatan angin di strip bawah.
- Tooltip bersama pada timestep terdekat menampilkan valid time (timezone jelas), suhu, curah hujan dan interval akumulasi, angin, tutupan awan, tekanan/kelembapan bila ada, dan deskripsi kondisi cuaca bila klasifikasi tersedia.
- Klik/hover grafik memperlihatkan crosshair; klik grafik memilih waktu pada timeline dan peta. Perubahan timeline peta memindahkan crosshair meteogram tanpa fetch ulang.
- Tampilkan model, run time, valid time range, lokasi koordinat, satuan, dan status loading/error/empty.

## 2. Bahasa desain: Meteorological Workstation

**Jangan buat AI-slop**: tidak ada neon gradient, glow, glass blur berat, floating cards bertumpuk, ilustrasi 3D, shadow besar, radius 24px, ikon emoji sebagai ikon produksi, atau animasi spring berlebihan.

- Panel solid `#13171C`, border `#343B45` 1px, radius atas 8–10px, shadow minimal bila diperlukan.
- Grid chart tipis `#343D47`, label sekunder `#94A3B8`, teks utama `#E5E7EB`.
- Temperature line coral `#F08D82`, fill transparan ~10–15%.
- Precipitation bar biru `#68B8D8` dengan opacity terukur; **sumbu hujan berbeda dari sumbu suhu**, jangan menggabungkan skala.
- Wind barbs biru muda/abu, simbol dan ukuran konsisten; legend ringkas.
- Typography Inter atau font aplikasi existing, `font-variant-numeric: tabular-nums`; ukuran label tetap terbaca.
- Gunakan garis pemisah, spacing 8px grid, serta pengelompokan informasi; chart adalah fokus utama.
- Hindari 120 ikon di atas kurva sekaligus. Terapkan sampling berdasarkan pixel spacing dan zoom; tooltip tetap mendukung semua timestep.
- Hormati `prefers-reduced-motion`.

## 3. Struktur komponen yang disarankan (sesuaikan project)

```text
WeatherViewer / existing map page
├── MapLibreMap (existing)
├── ExistingMapControls
├── ForecastTimeline (existing, sibling, always visible)
├── MeteogramSheet.svelte
│   ├── SheetHandle.svelte
│   ├── MeteogramHeader.svelte
│   ├── MeteogramTabs.svelte
│   ├── MeteogramChart.svelte
│   ├── WeatherConditionOverlay.svelte
│   ├── WindBarbStrip.svelte
│   └── MeteogramTooltip.svelte
└── existing shared weather state

lib/meteogram/
├── types.ts
├── normalize.ts
├── conditions.ts
├── icon-map.ts
├── chart-options.ts
├── sampling.ts
├── units.ts
└── cache.ts
```

Nama file bersifat rekomendasi, jangan duplikasi utilitas yang sudah tersedia.

## 4. Layout dan stacking: sheet + timeline persistent

Gunakan satu container peta yang memiliki posisi relatif, sheet overlay absolute/fixed terhadap viewport viewer, timeline sebagai **sibling** dengan z-index lebih tinggi. Contoh layering: map 0, map controls 20, sheet 40, timeline 50, navbar/modal 60. Perhatikan stacking context dari `transform`, `filter`, dan `isolation` pada parent.

**Penting:** Timeline mengikuti **tinggi sheet yang terlihat**, bukan di-hardcode ke `bottom: 0` saat sheet terbuka. Gunakan satu sumber nilai `sheetVisibleHeight` (px) atau CSS custom property `--meteogram-visible-height`. Timeline memakai `bottom: calc(var(--meteogram-visible-height) + var(--timeline-gap))`; ketika closed, kembali ke offset existing. Integrasikan offset existing agar tidak menggeser timeline yang sudah berfungsi.

Saat drag, perbarui transform sheet dan posisi timeline dalam satu `requestAnimationFrame`, hindari Svelte reactive update pada setiap pointer event bila menimbulkan rerender chart/peta. Setelah drag selesai, snap ke state terdekat. Terapkan `pointercapture`, `touch-action: none` hanya pada handle, batas drag, Escape untuk menutup, tombol keyboard-accessible, dan cleanup event listeners.

Gunakan CSS `transform: translate3d(...)` untuk animasi; hindari mengubah tinggi DOM chart terus-menerus. **Jangan `map.resize()` tiap frame** jika peta tetap full-viewport di belakang overlay. Pastikan timeline tidak tertutup oleh sheet dan tombol peta penting tidak menjadi inaccessible.

## 5. Model data dan kontrak API

Buat tipe normalisasi berbasis timestamp UTC (ISO atau epoch ms) dan koordinat valid:

```ts
export type MeteogramPoint = {
  validTime: string; // ISO 8601 UTC
  temperatureC?: number | null;
  dewPointC?: number | null;
  relativeHumidityPct?: number | null;
  pressureHpa?: number | null;
  totalCloudCoverPct?: number | null;
  precipitationMm?: number | null;
  precipitationIntervalHours?: number | null;
  convectivePrecipitationMm?: number | null;
  windSpeedMs?: number | null;
  windDirectionDeg?: number | null; // meteorological FROM direction
  windGustMs?: number | null;
  capeJkg?: number | null;
  lightningProbabilityPct?: number | null;
  weatherCode?: string | number | null; // hanya bila ada dari sumber resmi
};

export type MeteogramSeries = {
  latitude: number;
  longitude: number;
  modelId: string;
  runTime: string;
  points: MeteogramPoint[];
};
```

Semua field opsional: jangan berasumsi seluruh parameter tersedia. Normalisasi nilai missing, konversi unit dan timezone di satu lapisan. **Bedakan precipitation accumulated-from-run vs interval precipitation**: jika sumber berupa akumulasi kumulatif, hitung selisih antar valid time dengan penanganan reset/negatif dan metadata interval; jangan menampilkan kumulatif sebagai curah hujan per jam. Sesuaikan cadence forecast dan hindari interpolasi yang menyiratkan data observasi.

Pengambilan titik grid: gunakan metode existing bila ada (nearest grid point atau interpolasi yang terdokumentasi). Cantumkan metode yang digunakan; jangan klaim nilai grid sebagai observasi titik. Cache key minimal `{model,run,lat/lon grid atau cell id,parameter set}`. Abort request ketika lokasi berganti cepat; jangan overwrite data lokasi terbaru dengan respons lama.

## 6. Kondisi cuaca pada kurva suhu (fitur utama ala INA-SIAM)

### 6.1 Urutan sumber kondisi cuaca

1. **Prioritas:** kode cuaca resmi/model-provided jika memang tersedia dan terdokumentasi.
2. Jika tidak tersedia, turunkan kategori dengan aturan transparan dari parameter yang benar-benar ada (misalnya TCC + precipitation interval + informasi siang/malam).
3. Bila bukti tidak cukup, pakai `unknown` / 'Kondisi tidak tersedia', bukan membuat ikon badai tanpa dasar.

### 6.2 Contoh kategori internal

`clear_day`, `clear_night`, `partly_cloudy_day`, `partly_cloudy_night`, `cloudy`, `rain`, `heavy_rain`, `thunderstorm_potential`, `unknown`.

**Ambang kategori harus ditentukan dari dokumentasi data/model dan disetujui sesuai kebutuhan produk**. Jangan otomatis menggunakan CAPE tinggi = petir. Thunderstorm hanya diklaim sebagai prakiraan petir jika sumber menyediakan parameter/kode yang mendukung; bila menggunakan proxy konveksi, label jelas sebagai **potensi**, bukan kejadian pasti. Intensitas hujan perlu memperhitungkan interval akumulasi, bukan hanya mm mentah.

Siang/malam dihitung dari elevasi matahari di **koordinat lokasi dan validTime** (library kecil yang sudah tersedia, atau algoritma teruji), bukan hanya jam lokal statis.

### 6.3 Overlay ikon pada grafik

- Render ikon cuaca sebagai **SVG statis**, bukan emoji, bukan animated GIF. Pilih set yang konsisten (mis. Meteocons static SVG atau weather-icons) dan cek lisensi aset.
- Ikon mengikuti X = timestamp forecast dan Y = nilai temperature pada chart, dengan offset ~12–18px ke atas garis. Bila suhu null, jangan tempatkan ikon pada posisi palsu.
- Gunakan `chart.convertToPixel({xAxisIndex:0,yAxisIndex:0}, [timestamp, temperature])` untuk ECharts; hanya setelah chart memiliki layout valid.
- Buat overlay absolut `pointer-events:none` agar pan/tooltip chart tidak terganggu. Ikon bersifat dekoratif; deskripsi kondisi tersedia melalui tooltip/aksesibilitas.
- Recalculate posisi ikon saat chart resize, zoom, atau data berubah; **jangan** saat crosshair waktu bergeser.
- Sampling ikon menurut ruang: target minimum ~32–44px horizontal antarikon dan interval yang selaras timestep; utamakan ikon ketika kondisi berubah. Pastikan ikon tidak keluar plot, menutupi label, atau bertabrakan dengan suhu puncak.
- Opsional: alternatif 'weather strip' tetap pada baris terpisah jika kurva terlalu padat, tetapi default tetap mengikuti suhu seperti referensi INA-SIAM.

## 7. Chart: pilih ringan tetapi lengkap

- Audit chart library existing dulu. Jika belum ada, pilih **Apache ECharts modular imports** untuk multi-axis + bar/line + tooltip, atau uPlot bila existing dan overlay kompleks dapat diimplementasikan tanpa banyak kode tambahan.
- Dynamic import chart hanya saat sheet pertama dibuka; jangan load seluruh ECharts bundle di initial map load.
- Gunakan canvas renderer untuk grafik utama, overlay SVG ringan untuk ikon/wind barbs.
- Sumbu X = UTC timestamp; label hari + jam sesuai timezone UI yang dipilih. Sumbu Y kiri = °C, Y kanan = mm per interval. Jangan samakan skala.
- Kurva suhu line halus secukupnya tetapi jangan smoothing berlebihan yang menciptakan ekstrem palsu. Hujan bar dengan lebar mengikuti interval forecast.
- Gunakan tooltip HTML **satu instance** yang mengikuti hover; tampilkan satuan, periode akumulasi, valid time, dan model.
- Wind barbs berada di strip tersendiri di bawah chart, sejajar dengan waktu. Pastikan meteorological wind-from convention, satuan knots/m/s, serta konvensi barb 5/10/50 knot. Jika menggunakan panah sederhana, beri label arah yang jelas dan jangan menyebutnya barb.
- `ResizeObserver` debounce atau RAF, `chart.resize()` hanya bila ukuran panel stabil/berubah bermakna. `chart.dispose()` pada unmount.

## 8. Sinkronisasi waktu dua arah tanpa feedback loop

- Reuse store/runes timeline yang sudah ada; **satu sumber kebenaran** `selectedForecastTime`.
- Klik meteogram → set time → timeline dan layer peta pindah ke valid time terdekat yang benar-benar tersedia.
- Geser timeline → update crosshair/highlight meteogram tanpa refetch atau rebuild semua opsi chart.
- Hover meteogram **tidak otomatis** mengganti layer peta (hindari fetch dan rerender map saat mouse bergerak); klik yang commit waktu.
- Hindari event loop: perubahan programatik crosshair tidak memicu handler klik.
- Ketika timestep model meteogram dan timestep layer peta berbeda, lakukan nearest-valid-time yang terdokumentasi, tampilkan valid time aktual, dan hindari asumsi kedua sumber identik.

## 9. Performa dan stabilitas

- Lazy load chart dan icon assets; gunakan caching dan request cancellation.
- Data satu titik dimuat sekali per kombinasi model/run/lokasi; jangan refetch ketika tab/sheet state berubah.
- Maksimal ikon terlihat berdasarkan pixel density, bukan jumlah timestep mentah; tetap pertahankan data penuh untuk tooltip.
- Hindari membuat ratusan komponen Svelte untuk setiap titik chart; chart mengelola line/bars dalam canvas.
- Drag menggunakan transform dan RAF; jangan rebuild chart setiap frame.
- Jangan memanggil `map.resize()`/mengubah source layer peta saat sheet drag.
- Jika ukuran dataset besar, lakukan normalisasi satu kali per respons dan memoize transformasi.
- Tambahkan loading skeleton sederhana, empty state, retry error, fallback parameter hilang, dan cleanup semua listener/observer.
- Uji dengan DevTools Performance dan Network: initial map load sebelum/sesudah, JS chunk chart, FPS drag, jumlah fetch per interaksi, dan memori setelah 20 kali open/close. **Jangan mengklaim angka performa tanpa pengukuran.**

## 10. Fase implementasi dan acceptance criteria

### Fase 1 — Audit dan integrasi shell
- Identifikasi file map, timeline, state, sumber model, endpoint, dan style existing.
- Implementasikan bottom sheet 3 state + drag + close + keyboard + timeline persistent.
- **Lulus:** timeline tetap terlihat saat closed/half/expanded dan saat drag; peta tidak reinitialize; tidak ada layout shift yang mengganggu.

### Fase 2 — Kontrak data dan integrasi nyata
- Implementasikan fetch/adapter existing backend untuk titik terpilih.
- Normalisasi UTC, unit, curah hujan interval, missing value, metadata run/model.
- **Lulus:** klik lokasi berbeda memberi data berbeda sesuai backend, request lama dibatalkan, tidak ada data palsu.

### Fase 3 — Meteogram utama
- Implementasikan chart suhu + curah hujan dengan sumbu terpisah, tooltip, loading/error/empty, responsive sizing.
- **Lulus:** tooltip dan valid time tepat; panel dapat di-resize tanpa distorsi chart.

### Fase 4 — Weather condition icons dan wind barbs
- Implementasikan classifier berbasis parameter nyata + day/night, SVG icon map, sampling/collision, overlay mengikuti kurva suhu, wind strip.
- **Lulus:** ikon sesuai data dan tidak overlap berlebihan; parameter tak tersedia diberi status jelas; tidak mengklaim badai petir hanya dari CAPE.

### Fase 5 — Sinkronisasi dan polishing
- Sinkronisasi klik chart ↔ timeline ↔ layer peta; perbaiki tooltip, timezone, mobile safe-area, reduced motion.
- **Lulus:** tidak ada feedback loop, refetch tidak perlu, timeline tidak hilang.

### Fase 6 — Performance test dan cleanup
- Audit bundle, CPU, FPS drag, network, memory leak, responsiveness, aksesibilitas.
- **Lulus:** tidak ada regresi besar dibanding baseline terukur; hasil lint/typecheck/build/test sukses.

## 11. Kasus uji wajib

1. Open/close panel 20 kali, cek listeners dan memory.
2. Drag cepat half ↔ expanded, timeline tetap mengikuti tanpa jitter.
3. Klik titik berbeda beruntun, hanya respons titik terakhir yang tampil.
4. Ganti run/model saat panel terbuka; metadata dan data tersinkron.
5. Timestep hujan kumulatif, reset akumulasi, nilai null, timestamp duplikat, dan timezone.
6. Forecast 1h, 3h, 6h; ikon tidak terlalu rapat.
7. Siang/malam pada koordinat berbeda; ikon berubah berdasarkan solar elevation.
8. Mobile 360px, tablet, desktop 16:9; browser zoom 125% dan 200%.
9. Keyboard navigation, focus management, screen-reader labels, reduced motion.
10. Timeline memilih waktu yang tidak ada persis di dataset meteogram; nearest timestamp konsisten dan transparan.

## 12. Output yang harus diserahkan Claude Code

- Ringkasan audit existing project dan dependensi yang direuse.
- Daftar file dibuat/diubah beserta alasan.
- Implementasi per fase dengan test dan instruksi menjalankan.
- Dokumentasi mapping parameter model → seri chart → kondisi cuaca.
- Hasil build/typecheck/lint/test dan catatan hasil profiling nyata.
- Daftar batasan yang belum dapat dipenuhi karena data model tidak tersedia.

**Prinsip final:** jangan meniru screenshot secara pixel-perfect jika mengorbankan keterbacaan atau performa. Replikasi **pola interaksi dan kekayaan informasi** INA-SIAM, dengan visual yang lebih tertata, ilmiah, dan konsisten dengan project existing.
