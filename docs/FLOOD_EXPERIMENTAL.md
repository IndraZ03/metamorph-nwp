# Indonesia Flood Potential (Eksperimental)

Lapisan potensi banjir eksperimental berbasis prakiraan curah hujan ECMWF IFS dan informasi spasial InaRISK BNPB pada grid numerik native ECMWF (~0.25° / ~25 km).

```
   ┌───────────────────────┐         ┌─────────────────────────┐
   │ ECMWF IFS TP (Retained│         │ InaRISK BNPB Rasters    │
   │ mm, regular native)   │         │ (Bahaya & Kerentanan)   │
   └──────────┬────────────┘         └────────────┬────────────┘
              │                                   │
              ▼                                   ▼
    Jendela Trailing 24h               Averaging & Reprojection
    P24(t) = TP(t) - TP(t-24h)          ke Grid Native ECMWF
              │                                   │
              ├───────────────────────────────────┤
              ▼                                   ▼
       Skala Kontinu                    Skala Kontinu
       Curah Hujan P24                  Indeks BNPB (0 - 1)
              │                                   │
              └─────────────────┬─────────────────┘
                                │
                                ▼
                   API & UI Eksploratif
                   Indikator Berdampingan
            (Tanpa probabilitas atau kategori palsu)
```

## Disclaimer Wajib
> Produk ini merupakan indikasi potensi banjir berdasarkan prakiraan curah hujan ECMWF dan informasi spasial InaRISK BNPB. Produk belum menggantikan peringatan dini resmi dan tidak merepresentasikan prediksi pasti lokasi, waktu, atau kedalaman genangan.

## Metodologi dan Batasan Ilmiah
1. **Jendela Waktu Trailing 24 Jam**:
   - $P_{24}(t) = \text{TP}(t) - \text{TP}(t - 24\text{ jam})$ untuk $(t - 24\text{ jam}, t]$.
   - Tidak menggunakan asumsi nol bila ada interval hilang atau tidak lengkap.
   - Langkah prakiraan awal ($t < 24$) ditandai eksplisit `ready: false` dengan kelengkapan 0.0.

2. **Antecedent Precipitation**:
   - Rentang 7 hari pendahuluan $(t - 192\text{ jam}, t - 24\text{ jam}]$ disimpan sebagai interval mentah.
   - Nilai tertimbang $\text{AR7}$ dan faktor peluruhan (decay factor $d$) **tidak dikonfigurasi** (`NOT_CONFIGURED`) karena parameter resmi belum terverifikasi dari literatur primer.

3. **Status Model Bayuadji**:
   - Status model: `NOT_CONFIGURED`.
   - Probabilitas banjir dan kategori: `null`.
   - Tidak menghasilkan nilai dummy atau estimasi dari grafik.

4. **Klasifikasi Kategori Hujan BMKG**:
   - Status: `unverified`.
   - Nilai curah hujan numerik ditampilkan kontinu tanpa rekayasa kategori resmi.

5. **Indeks Bahaya dan Kerentanan BNPB**:
   - Sumber bahaya: `https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_BAHAYA_BANJIR/ImageServer`
   - Sumber kerentanan: `https://gis.bnpb.go.id/server/rest/services/inarisk/layer_kerentanan_banjir/ImageServer`
   - Nilai kontinu $0.0 - 1.0$ direratakan ke grid native ECMWF. Tidak mengklaim peningkatan resolusi atau asesmen lokal 100 meter.

6. **Mode Gabungan**:
   - Ditampilkan sebagai indikator berdampingan (`exploratory_indicators`) pada legenda dan inspeksi titik.
   - Tidak menggunakan matriks pembobotan arbitrer atau skor gabungan tanpa metodologi tervalidasi.

## Endpoint API (`/api/flood/forecast`)
- `GET /status`: Status ketersediaan publikasi dan kesiapan pemrosesan.
- `GET /metadata`: Manifest publikasi immutable (bounding box, rentang zoom, daftar langkah, status model).
- `GET /times`: Daftar waktu dan status kelengkapan jendela.
- `GET /model`: Status modul ilmiah (Bayuadji, BMKG, integrasi).
- `GET /tile/{run}/{step}/{z}/{x}/{y}.webp?indicator={rainfall|hazard|vulnerability}`: WebP visual tile 256×256.
- `GET /point?lat={lat}&lon={lon}&step={step}&run={run}`: Nilai numerik titik lat/lon pada langkah prakiraan.

## Perintah CLI
```bash
# Smoke test raw Float32 TIFF export dari layanan BNPB
python -I engine/flood_cli.py smoke-export --kind hazard

# Ingest raster kontinu nasional (memerlukan izin unduhan)
python -I engine/flood_cli.py ingest --kind hazard
python -I engine/flood_cli.py ingest --kind vulnerability

# Proses run prakiraan ECMWF
python -I engine/flood_cli.py process 20261018T00

# Status pipeline
python -I engine/flood_cli.py status

# Daftar calon prune saja; --apply ditolak sampai reader leases tersedia
python -I engine/flood_cli.py prune --keep 3
```

## Audit sumber — 18 Oktober 2026

- Katalog nasional BNPB mengonfirmasi kedua endpoint di atas, bukan layer IKN atau banjir bandang. Metadata melaporkan F32 satu band, EPSG:3395, pixel 100 m, rentang indeks 0–1, batas export 15000×4100. Kelas numerik resmi/RAT dan izin redistribusi belum terverifikasi.
- Request export kecil sempat memberikan URL TIFF; request lain menghasilkan error layanan 503. Payload TIFF nyata belum berhasil diuji dalam pekerjaan ini. Metadata atau URL output bukan bukti raw export valid. Jalankan smoke test sebelum ingest nasional.
- [Referensi Bayuadji](https://www.researchgate.net/publication/343548913_Probabilistic_Rainfall_Threshold_for_Flood_Early_Warning_in_the_Upper_Watersheds_Java_Island_Indonesia) merespons 403. Teks primer, persamaan, koefisien, decay, domain dan kategori belum tersedia.
- [URL BMKG yang diperiksa](https://www.bmkg.go.id/cuaca/probabilistik-curah-hujan.bmkg) mengarah ke `https://web-meteo.bmkg.go.id/` yang merespons 404. Batas serta inklusivitas kategori tidak diisi dari ingatan.

## Operasional dan bagian belum selesai

- **Belum ada publikasi forecast banjir aktual.** Contoh `20261018T00` hanya format run ID; gunakan run yang benar-benar tersedia di retensi ECMWF. Data sintetis hanya ada dalam direktori sementara test.
- Unduhan nasional, smoke test payload BNPB, benchmark RAM/waktu nasional, observasi historis dan validasi DAS belum dijalankan.
- Input TP tetap milik pipeline existing `engine/output/landslide/precipitation`; tidak ada downloader ECMWF kedua. Hook flood berjalan sesudah proses weather/longsor dan kegagalannya tidak menggagalkan produk tersebut.
- Selisih kumulatif hanya sah untuk run/origin akumulasi sama. Interval incremental wajib contiguous; batas jendela tidak diprorata. Nol sah berbeda dari NoData.
- Antecedent native forecast dapat lengkap mulai lead 192 jam jika seluruh jendela sah. Adapter historis **ditolak**, bukan dianggap tervalidasi; perlu kontrak timestamp, satuan, grid, checksum, quality dan pemilihan sumber sebelum diaktifkan. Kelengkapan interval dan fraksi piksel lengkap disimpan terpisah.
- Bayuadji dan kategori BMKG saat ini scaffold fail-closed, **belum ada jalur aktivasi parameter terverifikasi**. Sigmoid stabil tersedia sebagai primitive, bukan model aktif. Agregasi DAS masih `unsupported`. Tidak ada skor/probabilitas gabungan.
- Sumber BNPB hilang/rusak menghasilkan indeks NoData/status masing-masing; P24 sah tetap dapat diterbitkan. `finite_grid_fraction` mengukur fraksi sel ECMWF dengan mean valid, **bukan coverage area subsel**. Coverage berbobot area subsel belum tersedia.
- Cache sumber menggunakan TIFF bertile, overviews, nama SHA-256 immutable, lock ingest dan pointer JSON atomik. Publikasi menggunakan staging, lock proses, signature input dan checksum NPZ. Tile WebP visual dan NPZ numerik sudah tersedia; export GeoTIFF hasil serta checksum tiap tile belum tersedia.
- Point request membaca satu NPZ grid rendah, bukan raster nasional. LRU lintas-request belum dibuat. Prune hanya dry-run; penghapusan ditolak sampai reader leases/pins aman diterapkan. Lock tersisa akibat crash perlu diperiksa operator; jangan hapus ketika proses masih aktif.
- Skala warna P24 0–200 mm adalah skala tampilan kontinu, bukan ambang BMKG; nilai lebih tinggi tetap tersimpan numerik. Skala kedua indeks 0–1 bukan probabilitas. Tidak ada threshold longsor yang dipakai untuk banjir.
- Jalankan CLI dengan `python -I engine/flood_cli.py ...` dari checkout tepercaya. Unduhan disimpan dalam direktori kosong terpisah dari script; jangan menjalankan interpreter/build dari direktori unduhan. Untuk launcher pipeline/backend lain yang membaca unduhan, gunakan `-I` dan tambahkan hanya checkout tepercaya secara eksplisit ke `sys.path`.
- UI menggunakan satu timeline bersama; waktu berlaku dipertahankan bila tersedia, beda run/fallback diberi pemberitahuan. Tile dan inspeksi titik dipin ke publication ID. Tidak ada forecast fixture yang dipasang ke UI produksi.

## Rencana Kalibrasi Lanjutan Berbasis DAS
Untuk mengaktifkan model probabilitas banjir di masa depan:
1. Verifikasi parameter, formula, dan domain spesifik DAS dari literatur primer terbitan resmi.
2. Pengujian out-of-time dan out-of-region berbasis data kejadian historis (reliability, false alarm ratio, missed events).
3. Penyediaan polygon batas DAS dan adapter observasi historis terkurasi.
