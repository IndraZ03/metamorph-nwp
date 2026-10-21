# IMPLEMENTATION PLAN — DRAWING & FORECAST ANNOTATION

> **Untuk Claude Code — integrasikan ke NWP Viewer WebGIS yang SUDAH ADA.**
> Fokus: ringan, profesional, modular, dan drawing menjadi layer WebGIS yang persisten.

## 0. Instruksi wajib sebelum coding

1. Audit struktur repository, framework, map engine (MapLibre/Mapbox GL JS/Leaflet/OpenLayers), state management, sistem layer, timeline, proyeksi, serta mekanisme penyimpanan existing.
2. Baca komponen tombol toolbar, sidebar, layer manager, event peta, dan styling. **Jangan membuat ulang aplikasi, map instance, atau sistem layer.**
3. Identifikasi konflik gesture: drag peta, klik layer, hover nilai grid, timeline, dan animasi angin.
4. Buat rencana file yang disentuh dan implementasikan bertahap. Gunakan pola komponen, token desain, dan dependensi existing. Jangan mengganti stack.
5. Jika belum ada library drawing, pilih yang paling kompatibel dan kecil untuk map engine existing. Pertimbangkan Terra Draw + adaptor yang sesuai untuk MapLibre; Leaflet-Geoman atau drawing berbasis Leaflet; interaksi native OpenLayers. Tambahkan Turf.js secara selektif hanya bila diperlukan, dengan tree-shaking. Verifikasi kompatibilitas versi.
6. Jangan membuat backend baru kecuali diperlukan; gunakan API dan storage existing. Jelaskan batasan penyimpanan lokal jika backend tidak tersedia.

## 1. Tujuan produk

Bangun fitur **Drawing & Forecast Annotation** untuk Forecaster on Duty (FOD): menggambar, mengukur, memberi label, dan menyimpan objek spasial di atas layer NWP. Setiap drawing menjadi **objek pada drawing layer** yang terdaftar di layer manager existing. Layer dapat dinyalakan/dimatikan, diurutkan, dan dipulihkan. Drawing tidak boleh mengubah data NWP.

## 2. Perilaku tombol dan sidebar (wajib)

- Tambahkan atau gunakan tombol **Drawing** pada toolbar existing dengan ikon yang konsisten.
- Klik pertama: buka sidebar drawing. Klik tombol yang sama lagi: **tutup sidebar**. Jangan membuat dua tombol open/close yang membingungkan; tombol close di header sidebar boleh menjadi alternatif.
- State `isDrawingSidebarOpen` tunggal sebagai sumber kebenaran. Tombol menunjukkan state aktif dan memiliki `aria-expanded`, `aria-controls`, tooltip, serta keyboard support.
- Saat sidebar ditutup, **semua drawing tetap terlihat di peta** sesuai visibilitas layer. Sidebar tertutup bukan berarti layer tersembunyi.
- Saat sidebar ditutup di tengah proses menggambar, batalkan hanya *draft geometry* yang belum selesai, bukan objek yang sudah disimpan. Berikan escape/cancel yang jelas.
- Sidebar responsif: desktop sebagai panel samping berukuran kira-kira 300–340 px; mobile sebagai drawer yang tidak memotong kontrol penting. Integrasikan dengan layout existing, jangan menutupi kontrol vital.
- Transisi `transform`/`opacity` sekitar 160–220 ms, hindari animasi layout berat. Hormati `prefers-reduced-motion`.
- Sidebar **lazy mount** atau lazy load konten berat saat pertama dibuka. Ketika ditutup, lepaskan listener mode aktif yang tidak diperlukan.

## 3. Arah desain UI — modern, dinamis, anti-AI-slop

- Visual seperti tool GIS operasional profesional: presisi, ringkas, konsisten, bukan dashboard template generik.
- Ikuti tema aplikasi yang ada. Gunakan panel solid/semi-transparan seperlunya; blur ringan hanya jika aman untuk GPU. Hindari glassmorphism berlebihan, glow, gradient ramai, emoji sebagai ikon UI, shadow besar, dan animasi dekoratif.
- Tipografi hierarkis jelas, padding konsisten, separator halus, ikon satu keluarga, state hover/active/focus yang tegas.
- Header: `Drawing Tools`, subteks singkat `Forecast annotation`, ikon close.
- Kelompok kontrol berbentuk compact tool grid / segmented buttons:
  1. **Draw** — Select/Edit, Pen, Line, Arrow, Polygon, Rectangle, Circle, Star Marker, Text.
  2. **Measure** — Distance/Bearing, Radius Ring, Concentric Rings, Bearing Sector, Area, Route Distance.
  3. **Weather** — High/Low, CB/TS, heavy rain, warning area, wind/storm motion, trough/convergence/front symbols (simbol harus diberi legenda dan tidak diklaim sebagai observasi otomatis).
  4. **Layers** — daftar drawing layers dan objects, toggle visibility, rename, reorder, lock, duplicate, delete.
- Tampilkan **contextual inspector** hanya ketika tool/objek dipilih: label, ukuran font, warna stroke/fill, opacity, ketebalan garis, dash, unit, koordinat, radius, azimuth, dan valid time bila relevan.
- Footer compact: Undo, Redo, Clear (dengan konfirmasi), Save, Export.
- Pertahankan ruang peta seluas mungkin; hindari panel bertingkat yang selalu terbuka.

## 4. KATALOG DRAWING INTI — LENGKAP (WAJIB DIBANGUN BERTAHAP)

> **Jangan batasi Drawing pada sembilan ikon.** Semua alat berikut harus masuk dalam spesifikasi dan menu yang terorganisasi. Implementasikan tool dasar terlebih dahulu, kemudian tool kompleks dengan dependensi minimal. Alat yang belum selesai tidak boleh ditampilkan sebagai tombol palsu yang terlihat berfungsi. Setiap alat memiliki tooltip, shortcut bila masuk akal, state aktif, cancel, edit ulang, dan penyimpanan sebagai feature pada drawing layer.

### 4.1 Point & Marker Tools
1. **Point Marker** — titik sederhana dengan warna/ukuran custom.
2. **Star Marker ★** — bintang berwarna dengan **label nama di bawah bintang**, center aligned, offset stabil saat zoom.
3. **Custom Icon Marker** — simbol dari atlas SVG lokal (tanpa request icon per marker).
4. **Numbered Marker** — pin bernomor untuk titik analisis berurutan.
5. **Coordinate Marker** — pin dengan koordinat lat/lon dan opsi copy koordinat.
6. **Text Annotation** — teks bebas, font size, alignment, halo/background opsional.
7. **Callout / Leader Label** — label dengan garis penunjuk ke lokasi tertentu.
8. **High / Low Marker** — simbol tekanan H/L, warna dan label custom.
9. **Weather Symbol Marker** — CB/TS, hujan, angin kencang, peringatan; simbol manual, bukan observasi.

### 4.2 Line & Path Tools
10. **Straight Line** — garis dua titik.
11. **Polyline** — garis multi-vertex, label opsional.
12. **Freehand Pen** — coretan bebas dengan sampling dan simplifikasi.
13. **Smooth / Curved Line** — kurva dari control points; simpan control points agar dapat diedit kembali.
14. **Arrow Line** — garis dengan arrowhead awal/akhir/both.
15. **Multi-arrow Path** — panah berulang di sepanjang lintasan.
16. **Dashed / Dotted Line** — style garis putus-putus/titik.
17. **Parallel / Offset Line** — garis paralel dengan offset km/NM.
18. **Perpendicular Line** — garis tegak lurus dari segmen referensi.
19. **Route / Waypoint Path** — lintasan dengan titik-titik bernama dan jarak per segmen.
20. **Storm Track Path** — lintasan fenomena cuaca dengan posisi/timestamp manual dan arah gerak.

### 4.3 Area & Shape Tools
21. **Polygon** — poligon multi-vertex, fill/outline/label.
22. **Multipolygon** — satu objek terdiri dari beberapa area terpisah.
23. **Rectangle** — area kotak yang dapat diedit.
24. **Rotated Rectangle** — persegi panjang dengan orientasi yang dapat diubah.
25. **Circle** — pusat dan radius geodesik.
26. **Ellipse** — sumbu mayor/minor, orientasi dan titik pusat; metadata parametris dipertahankan.
27. **Freehand Area / Lasso** — coretan tertutup menjadi poligon yang disederhanakan.
28. **Triangle / Regular Polygon** — segitiga dan poligon beraturan dengan jumlah sisi pilihan.
29. **Donut / Polygon Hole** — membuat area berlubang/pengecualian.
30. **Buffer Zone** — buffer geodesik di sekitar titik, garis, atau poligon.
31. **Route Corridor** — koridor sepanjang jalur dengan lebar km/NM yang bisa diedit.
32. **Bearing Sector / Wedge** — juring dari pusat, azimuth awal/akhir dan radius.

### 4.4 Measurement & Aviation Geometry Tools
33. **Distance + True Bearing** — dua titik, km/NM, azimuth 0–360°.
34. **Multi-segment Distance** — panjang tiap segmen dan total.
35. **Radius Ring** — satu ring dengan radius custom km/NM.
36. **Concentric Rings** — beberapa ring dari satu pusat; preset 5/10/25/50/100 NM dapat diedit.
37. **Bearing & Range Fan** — beberapa garis bearing dari satu titik dengan jarak tertentu.
38. **Area & Perimeter** — km²/NM² serta keliling km/NM.
39. **Coordinate Inspector / Converter** — decimal degrees, DMS, DDM; copy coordinates.
40. **Runway Extended Centerline** — perpanjangan garis runway berdasarkan dua titik/orientasi input; bukan data aeronautika resmi.
41. **Approach / Departure Corridor** — zona sketsa referensi dengan bearing, panjang, dan lebar custom.
42. **Nearest Distance to Feature** — jarak terpendek dari titik referensi ke garis/area drawing.
43. **Back Bearing** — arah balik dihitung secara geodesik, bukan asumsi selalu +180° pada lintasan panjang.

**Akurasi:** 1 NM = 1.852 km. Gunakan geodesic distance/destination/bearing, bukan ukuran pixel atau jarak mentah Web Mercator. Default bearing adalah **true north**; magnetic bearing hanya dengan sumber deklinasi yang valid dan diberi label jelas. Untuk circle/sector/ellipse, simpan parameter asli selain polygon approximation agar edit tidak kehilangan presisi.

### 4.5 Geometry Editing & Boolean Operations
44. **Select / Inspect** — klik objek untuk melihat properti.
45. **Move / Drag** — geser seluruh objek.
46. **Vertex Edit** — pindah/tambah/hapus vertex; snapping jika diaktifkan.
47. **Multi-select** — pilih beberapa objek, operasi massal.
48. **Duplicate** — duplikasi objek dan style.
49. **Rotate / Resize** — untuk shape yang mendukung, simpan parameter edit.
50. **Split Polygon** — potong polygon menggunakan garis.
51. **Merge / Union** — gabungkan poligon.
52. **Intersect** — ambil area irisan dua polygon.
53. **Difference / Erase** — kurangi area dengan polygon lain.
54. **Polygon Hole** — buat/ubah ring interior.
55. **Snap to Vertex / Edge** — snapping opsional dengan toleransi pixel terkontrol.
56. **Simplify Geometry** — sederhanakan geometri dengan preview dan undo.
57. **Reverse Line Direction** — balik arah line/arrow.
58. **Bring Forward / Send Backward** — urutan objek dalam kelompok drawing.
59. **Group / Ungroup** — kelola beberapa feature sebagai satu grup logis.
60. **Lock / Unlock** — cegah edit tidak sengaja.

**Khusus boolean geometry:** validasi self-intersection, winding/ring closure, hasil kosong, multipolygon, dan koordinat antimeridian bila relevan. Jalankan operasi berat hanya ketika diminta, bukan setiap pointermove. Gunakan library geometri hanya bila engine existing tidak menyediakan operasi tersebut.

### 4.6 Meteorological Drawing & Aviation Annotations
61. **Trough Line** — garis palung tekanan dengan style/label khusus.
62. **Ridge Line** — garis punggung tekanan.
63. **Convergence Line** — garis konvergensi.
64. **Shear Line** — garis belokan/pergeseran angin.
65. **Cold / Warm / Occluded / Stationary Front** — style garis front dengan simbol berulang yang benar; legend wajib.
66. **Isobar / Isotherm Manual Line** — garis analisis manual dengan nilai label.
67. **Storm Motion Vector** — panah dengan speed kt/km/h dan direction.
68. **CB / Thunderstorm Area** — polygon preset cuaca signifikan.
69. **Heavy Rain / Strong Wind Area** — polygon preset, label dapat diedit.
70. **Warning / Watch / Advisory Area** — preset area perhatian, tanpa mengklaim peringatan resmi.
71. **Forecast Confidence Area** — label tingkat keyakinan dan catatan analis.
72. **Airport / Site Reference Point** — marker referensi ARP/AWS/AWOS dengan koordinat yang disediakan user/data existing.

**Standar simbol:** jangan mengarang simbol seolah standar WMO/ICAO. Pakai aset/pedoman yang sudah tersedia atau tandai sebagai custom analysis symbols. Semua anotasi manual harus dapat dibedakan dari produk resmi/otomatis.

### 4.7 Styling & Label Inspector (untuk SEMUA objek relevan)
- Stroke color, fill color, stroke width, fill opacity, line opacity, dash pattern.
- Arrowhead shape/size/placement, icon shape/size/rotation, symbol color.
- Label text, font size/weight, text halo, background, label position, x/y offset, visibility by zoom.
- Geometry units km/NM dan km²/NM², radius, start/end azimuth, center coordinates, length/area.
- Custom name, description, notes, severity/category, author, created/updated time.
- Optional model, model run time, forecast valid time, timezone, always-visible vs time-scoped.
- Preset styles: normal, focus, warning, CB, heavy rain, wind, reference point.
- Copy style / paste style dan reset style.

### 4.8 Tool UX dan prioritas implementasi
**Toolbar sidebar (kelompok yang mudah dipindai):**
- **Draw:** Point, Star, Text, Callout, Line, Polyline, Freehand, Curve, Arrow, Polygon, Rectangle, Circle, Ellipse, Lasso.
- **Measure:** Distance/Bearing, Multi-distance, Radius, Rings, Sector, Area/Perimeter, Coordinates, Route Corridor.
- **Weather:** H/L, CB/TS, Trough, Ridge, Convergence, Shear, Fronts, Storm Motion, Warning Area.
- **Edit:** Select, Vertex, Move, Multi-select, Duplicate, Split, Merge, Intersect, Difference, Hole, Rotate, Offset, Lock.
- **Layers:** User Drawing groups, visibility, reorder, rename, group, save/export/import.

**P0 — wajib usable lebih dahulu:** Select, Point, Star+label, Text, Freehand, Line, Polyline, Arrow, Polygon, Rectangle, Circle, Distance/Bearing, Radius, Rings, Sector, Area, basic edit, style, undo/redo, layer registration, persistence.

**P1 — setelah P0 stabil:** Curve, ellipse, lasso, buffer/corridor, route, callout, coordinate converter, weather symbols, vertex snapping, duplicate, multi-select, runway centerline, advanced labeling.

**P2 — advanced operations:** Split, merge, intersect, difference, polygon hole, rotate/resize, offset, storm track, front symbol rendering, group/ungroup, advanced geodesic edge cases.

**Jangan mengimplementasikan semua P0–P2 sekaligus secara monolitik.** Buat registry tool yang extensible dengan lazy-loaded modules. Tampilkan tool hanya ketika implementasinya siap, dan jangan meninggalkan placeholder yang menyesatkan.

## 5. Drawing sebagai layer WebGIS (KRITIS)

- Integrasikan ke **layer manager existing**, jangan membangun sistem layer paralel yang terpisah.
- Gunakan kelompok induk `User Drawings` dan sublayer opsional (contoh `Analisis Shift Pagi`, `Area Hujan`, `Titik Penting`).
- Setiap objek memiliki ID unik stabil, `layerId`, `type`, `geometry`, `properties`, `style`, `visible`, `locked`, `createdAt`, `updatedAt` dan opsional `model`, `runTime`, `validTime`, `author`.
- Gunakan **GeoJSON FeatureCollection** untuk geometri standar; simpan metadata dan parameter khusus (circle center/radius, sector bearings, label offset) dalam `properties` atau skema pendamping yang terversi.
- Layer rendering harus menggunakan source/layer native map engine jika memungkinkan, bukan satu DOM marker untuk setiap vertex atau polygon.
- Star/text labels dapat memakai symbol layer dan glyph/icon atlas bila memungkinkan; HTML marker hanya untuk kasus sedikit objek dan terukur.
- Sinkronkan `visible`, z-order, rename, lock, dan delete antara sidebar drawing dan layer manager.
- Layer NWP, basemap, batas administrasi, timeline, raster tiles, dan wind animation **tidak boleh terdampak** oleh pengeditan drawing.
- Pilih z-index / layer order yang membuat anotasi terlihat tanpa menutup pop-up atau kontrol UI. Berikan pengaturan layer order yang aman.
- **Tutup sidebar tidak menghapus, menyembunyikan, atau mereset drawing.**
- Beri pilihan mode objek: `Always visible` atau `Specific valid time` agar anotasi dapat mengikuti timestep NWP tanpa salah konteks.

## 6. State, persistence, dan export

- Pisahkan state: `sidebarOpen`, `activeTool`, `draftGeometry`, `selectedFeatureId`, `drawingLayers`, `history`.
- Draft disimpan terpisah dari committed feature. Commit hanya saat geometri valid dan pengguna menyelesaikan drawing.
- Autosave ringan dengan debounce setelah commit/edit, bukan setiap mousemove. Gunakan mekanisme penyimpanan existing; jika tidak ada backend, gunakan IndexedDB untuk banyak objek dan jelaskan bahwa data hanya tersimpan pada browser/perangkat tersebut.
- Tombol Save eksplisit tetap tersedia dan beri indikator `Saved / Unsaved / Saving / Error` yang akurat.
- Undo/redo berbasis perintah atau snapshot terbatas; batas histori masuk akal dan tidak menyimpan seluruh raster/map state.
- Export/import **GeoJSON** dengan validasi skema dan ukuran file; export **PNG** harus mencakup layer drawing dan attribution dengan benar, tanpa mengasumsikan semua raster cross-origin bisa diekspor.
- PDF/KML dapat dijadikan fase opsional jika library existing mendukung.
- Hapus satu objek, hapus layer, dan clear all harus berbeda, dengan konfirmasi untuk aksi destruktif.
- Sanitasi semua label, nama layer, dan file impor; jangan merender input pengguna sebagai HTML mentah.

## 7. Arsitektur dan performa

- **Satu map instance**, reuse map context existing.
- **Satu drawing controller/manager** yang mengelola mode dan listener; setiap mode eksklusif, sehingga tool tidak saling berebut event.
- Lazy load modul drawing saat sidebar pertama dibuka. Jangan import paket geometri besar ke initial bundle jika tidak dibutuhkan.
- Update preview geometri maksimal sekali per animation frame; commit perubahan ke source setelah aksi selesai; jangan `setData` penuh untuk setiap mousemove jika ada cara incremental/temporary source.
- Gunakan native GPU/vector layers bila tersedia; minimalkan DOM nodes dan React/Vue rerenders.
- Freehand: distance threshold, point sampling, simplification toleransi yang menyesuaikan zoom; jangan mengubah bentuk terlalu agresif.
- Hindari perhitungan geodesik berat saat pointer bergerak; throttle dan hitung ulang pada commit.
- Pisahkan `draft source` dan `committed source`; update hanya yang berubah.
- Bersihkan event listeners, subscriptions, dan temporary layers saat unmount/mode switch; cegah memory leak.
- Jangan menghentikan animasi angin atau melakukan full reload map saat toggle sidebar.
- Uji dengan ratusan objek dan garis panjang; ukur FPS, interaksi pan/zoom, ukuran bundle, dan memory dibanding baseline existing.
- Tidak ada klaim angka performa tanpa pengukuran pada project aktual.

## 8. Interaksi penting dan edge cases

1. Klik Drawing -> sidebar terbuka; klik lagi -> tertutup; ulangi berkali-kali tanpa listener ganda.
2. Setelah menggambar polygon, toggle sidebar tertutup -> polygon tetap terlihat sebagai layer.
3. Saat mode drawing aktif, drag/click tidak mengaktifkan hover inspect atau aksi layer NWP yang bertabrakan; mode select/pan mengembalikan gesture normal.
4. Esc membatalkan draft; tidak menghapus objek tersimpan.
5. Undo/redo berlaku pada create/edit/delete, tidak pada perubahan timestep NWP.
6. Perubahan basemap, model, run time, valid time, zoom, dan refresh layer NWP tidak menghapus drawing.
7. Star marker tetap punya label di bawah simbol saat pan/zoom, tidak duplikat dan tidak terpotong secara tidak wajar.
8. Pengukuran km/NM benar; radius dan bearing sektor konsisten setelah zoom.
9. Import invalid GeoJSON ditolak dengan error jelas; data existing tidak tertimpa.
10. Penyimpanan gagal tidak mengklaim sukses; data draft/unsaved dipertahankan bila memungkinkan.
11. Aksesibilitas: focus trap bila drawer modal pada mobile, keyboard navigation, tooltip, focus visible, reduced motion.
12. Tangani resize, mobile touch, pointer cancel, dan double-click zoom conflict.

## 9. Tahapan implementasi

### Fase 1 — Audit dan fondasi
- Identifikasi engine, dependensi, komponen toolbar/sidebar, layer manager, dan penyimpanan.
- Buat struktur modular, tipe data, state machine mode, dan integrasi tombol toggle.
- Selesaikan sidebar modern yang dapat dibuka/tutup tanpa memengaruhi peta.

### Fase 2 — Drawing inti + integrasi layer
- Implementasikan seluruh tool **P0** dari katalog §4, bukan hanya daftar sembilan alat; gunakan tool registry modular.
- Commit drawing ke `User Drawings` pada layer manager existing.
- Edit/delete, style inspector, visibility, lock, z-order, rename.

### Fase 3 — Measurement
- Distance/bearing, radius, concentric rings, sector, route distance, polygon area.
- Unit km/NM, true bearing, label geodesik, dan pengujian perhitungan.

### Fase 4 — Meteorological tools dan persistence
- Palet simbol cuaca P1, metadata valid time, Save/Load, autosave, undo/redo, import/export GeoJSON, export PNG; lanjutkan tool P1/P2 sesuai kesiapan dan pengujian.

### Fase 5 — Hardening dan optimasi
- Profiling pada dataset nyata; optimasi source updates, freehand simplification, event cleanup, lazy loading, mobile, keyboard, dan regresi fitur existing.
- Tambahkan fitur lanjutan hanya jika fondasi stabil: buffer along line, polygon split/merge, storm ETA, polygon statistics, dan point forecast inspector (membutuhkan data numerik NWP, bukan hanya raster gambar).

## 10. Acceptance criteria (semua wajib)

- [ ] Drawing button berfungsi sebagai toggle dua arah dan state UI konsisten.
- [ ] Sidebar modern, ringkas, responsif, dan tidak merusak layout existing.
- [ ] Semua tool P0 pada katalog §4 berfungsi, dapat diedit/dihapus, dan terdaftar sebagai drawing layer; P1/P2 mengikuti milestone teruji.
- [ ] Marker bintang memiliki nama yang ditampilkan **di bawah bintang**.
- [ ] Semua objek committed terdaftar dalam `User Drawings` pada layer manager existing.
- [ ] Sidebar ditutup -> drawing tetap muncul dan dapat dikontrol dari layer manager.
- [ ] Layer drawing dapat hide/show, rename, lock, dan reorder tanpa memengaruhi layer NWP.
- [ ] Bearing/radius/sector mendukung **km dan NM** dengan kalkulasi geodesik.
- [ ] Save/Load, undo/redo, dan export/import GeoJSON berjalan dengan penanganan error.
- [ ] Map pan/zoom, timeline, hover data, dan wind animation tetap berfungsi.
- [ ] Tidak ada map instance tambahan, event listener bocor, atau redraw raster NWP saat drawing.
- [ ] UI dan fitur diuji di desktop dan mobile.

## 11. Instruksi akhir untuk Claude Code

**Kerjakan langsung pada codebase yang ada.** Mulai dengan membaca struktur project dan melaporkan hasil audit singkat (map engine, layer manager, state, storage, file yang akan disentuh), lalu implementasikan fase demi fase dalam satu pekerjaan terarah. Prioritaskan fitur inti dan stabilitas daripada menambah dependensi. Jangan membuat mockup terpisah, halaman demo, atau aplikasi baru. Ikuti pola desain dan coding convention existing. Setelah selesai, jalankan lint/typecheck/test/build yang tersedia, perbaiki error, dan berikan ringkasan file berubah, cara penggunaan, pengujian, serta batasan yang masih ada.
