<script>
  import { REQUIRED_FLOOD_DISCLAIMER, formatWib } from '../services/flood.js';
  let { metadata = null, step = null, error = '', notice = '', opacity = 0.6, visible = true,
    indicator = 'rainfall', mode = 'screening', onIndicator, onMode, onOpacity, onVisibility, onClose } = $props();
  const row = $derived(metadata?.steps?.find((r) => r.step === step));
</script>

<section class="flood-legend" aria-label="Indonesia Flood Potential">
  <div class="flex justify-between gap-2 items-center">
    <h3 class="text-xs font-bold text-white">Indonesia Flood Potential</h3>
    <button type="button" onclick={onClose} aria-label="Tutup banjir" class="text-slate-300">✕</button>
  </div>
  <p class="text-[10px] text-amber-300 my-2">Eksperimental · ECMWF IFS × InaRISK BNPB</p>
  <label class="block text-xs">Mode
    <select value={mode} onchange={(e) => onMode(e.currentTarget.value)} class="bg-slate-800 w-full p-1.5 mt-1 rounded">
      <option value="screening">A · Indikator hujan dan spasial</option>
      <option value="bayuadji" disabled>B · Bayuadji — NOT_CONFIGURED</option>
      <option value="combined">C · Indikator berdampingan (eksploratif)</option>
    </select>
  </label>
  <label class="block text-xs mt-2">Lapisan
    <select value={indicator} onchange={(e) => onIndicator(e.currentTarget.value)} class="bg-slate-800 w-full p-1.5 mt-1 rounded">
      <option value="rainfall">Hujan P24 trailing</option>
      <option value="hazard">Indeks Bahaya Banjir</option>
      <option value="vulnerability">Indeks Kerentanan Banjir</option>
    </select>
  </label>
  <div class="mt-2 text-[11px] space-y-1">
    <p>Run: {formatWib(metadata?.run_time)}</p>
    {#if row}<p>P24: {formatWib(row.window_start)} — {formatWib(row.window_end)}</p>
      <p>Kelengkapan piksel hujan: {Math.round((row.completeness ?? 0) * 100)}%</p>{/if}
    {#if error}<p role="status" class="text-amber-300">{error}</p>{/if}
    {#if notice}<p class="text-amber-300">{notice}</p>{/if}
  </div>
  <div class="my-3">
    <div class="h-2 rounded" style="background:linear-gradient(to right,rgb(30,180,230),rgb(180,50,200))"></div>
    <div class="flex justify-between text-[10px] mt-1"><span>0</span><span>{indicator === 'rainfall' ? '≥200 mm / 24 jam' : '1'}</span></div>
    <p class="text-[10px] text-slate-400">Skala tampilan kontinu, bukan batas kategori resmi. NoData transparan; nol tetap nilai sah.</p>
  </div>
  <div class="text-[11px] space-y-1 border-y border-slate-700 py-2">
    <p>Bahaya BNPB: {metadata?.indices?.hazard?.status ?? 'unavailable'}</p>
    <p>Kerentanan BNPB: {metadata?.indices?.vulnerability?.status ?? 'unavailable'}</p>
    <p>Bayuadji: NOT_CONFIGURED · probabilitas tidak tersedia.</p>
    <p>Kategori BMKG dan kelas BNPB: belum terverifikasi.</p>
    <p>AR7 tertimbang: belum terkonfigurasi; decay belum terverifikasi.</p>
    {#if mode === 'combined'}<p>Indikator berdampingan pada inspeksi titik. Tidak ada skor atau kategori gabungan.</p>{/if}
  </div>
  <div class="mt-2 flex justify-between text-[11px]">
    <label for="flood-opacity">Opasitas {Math.round(opacity * 100)}%</label>
    <button type="button" onclick={onVisibility}>{visible ? 'Sembunyikan' : 'Tampilkan'}</button>
  </div>
  <input id="flood-opacity" class="w-full" type="range" min="0.1" max="1" step="0.05" value={opacity} oninput={(e) => onOpacity(Number(e.currentTarget.value))}/>
  <p class="text-[10px] text-slate-400 mt-2">Indeks direratakan ke grid ECMWF, bukan peningkatan resolusi. Indeks 0–1 bukan probabilitas banjir. Model belum memprediksi aliran sungai, lokasi atau kedalaman genangan.</p>
  <p class="text-[10px] text-slate-400 mt-2">{REQUIRED_FLOOD_DISCLAIMER}</p>
</section>

<style>
  .flood-legend { position:fixed; bottom:24px; left:24px; z-index:40; width:min(340px,calc(100vw - 32px)); max-height:calc(100dvh - 120px); overflow-y:auto; padding:14px; border-radius:16px; background:rgba(15,23,42,.94); color:#cbd5e1; border:1px solid rgba(255,255,255,.15); backdrop-filter:blur(16px); }
  @media(max-width:1200px) { .flood-legend { left:16px; bottom:150px; max-height:calc(100dvh - 230px); } }
</style>
