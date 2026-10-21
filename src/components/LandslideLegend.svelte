<script>
  let {
    metadata = null,
    step = 0,
    opacity = 0.6,
    visible = true,
    onChangeOpacity,
    onToggleVisibility,
    onClose,
  } = $props();

  const formatWib = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('id-ID', {
        timeZone: 'Asia/Jakarta',
        dateStyle: 'medium',
        timeStyle: 'short',
      }) + ' WIB';
    } catch {
      return iso;
    }
  };

  const currentRow = $derived(
    metadata?.steps?.find((s) => s.step === step) || null
  );

  const rainThreshold = $derived(
    metadata?.rain_threshold_24h_mm ?? 30
  );
  const hazardLowMax = $derived(
    metadata?.hazard_low_max ?? 0.333
  );
  const hazardMediumMax = $derived(
    metadata?.hazard_medium_max ?? 0.666
  );
  const isProvisional = $derived(
    metadata?.hazard_class_boundaries_provisional ?? true
  );
</script>

<div class="landslide-legend-card">
  <!-- Header -->
  <div class="flex items-center justify-between pb-2 border-b border-slate-700/60">
    <div class="flex items-center gap-2">
      <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
      <h3 class="text-xs font-bold text-white tracking-wide">
        Prakiraan Potensi Tanah Longsor
      </h3>
    </div>
    <button
      type="button"
      onclick={onClose}
      class="text-slate-400 hover:text-white p-1 rounded-md transition-colors text-xs cursor-pointer"
      title="Tutup layer longsor"
      aria-label="Tutup"
    >
      ✕
    </button>
  </div>

  <div class="text-[10px] text-amber-400 font-medium mt-1">
    Eksperimental · Model ECMWF IFS × BNPB InaRISK (Kerentanan)
  </div>

  <!-- Forecast Window & Run -->
  {#if currentRow}
    <div class="bg-slate-800/80 rounded-lg p-2 mt-2 space-y-1 text-[11px] font-mono border border-slate-700/40">
      <div class="text-slate-400">
        Jendela 24 Jam ke Depan: <span class="text-emerald-400 font-semibold">+{currentRow.step} jam</span>
      </div>
      <div class="text-slate-200">
        Mulai: <span class="font-sans font-medium text-white">{formatWib(currentRow.forecast_start)}</span>
      </div>
      <div class="text-slate-200">
        Selesai: <span class="font-sans font-medium text-white">{formatWib(currentRow.forecast_end)}</span>
      </div>
    </div>
  {/if}

  <!-- Opacity & Visibility Controls -->
  <div class="mt-2.5 space-y-1.5 text-xs text-slate-300">
    <div class="flex items-center justify-between">
      <label for="ls-opacity" class="text-[11px] font-medium">Opasitas Lapisan ({Math.round(opacity * 100)}%):</label>
      <button
        type="button"
        onclick={onToggleVisibility}
        class="text-[10px] px-2 py-0.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-white transition-colors cursor-pointer"
      >
        {visible ? 'Sembunyikan' : 'Tampilkan'}
      </button>
    </div>
    <input
      id="ls-opacity"
      type="range"
      min="0.1"
      max="1"
      step="0.05"
      value={opacity}
      oninput={(e) => onChangeOpacity?.(parseFloat(e.currentTarget.value))}
      class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
    />
  </div>

  <!-- Legend Items -->
  <div class="mt-3 space-y-1.5">
    <div class="text-[11px] font-semibold text-slate-200">
      Kategori Potensi (Pemicu Hujan ≥ {rainThreshold} mm/24h):
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-200">
      <span class="w-3.5 h-3.5 rounded-sm bg-[#DC2626] border border-white/20 shrink-0"></span>
      <span class="font-medium text-red-300">Bahaya</span>
      <span class="text-[10px] text-slate-400 ml-auto">Indeks Kerentanan &gt; {hazardMediumMax}</span>
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-200">
      <span class="w-3.5 h-3.5 rounded-sm bg-[#F97316] border border-white/20 shrink-0"></span>
      <span class="font-medium text-orange-300">Siaga</span>
      <span class="text-[10px] text-slate-400 ml-auto">{hazardLowMax} – {hazardMediumMax}</span>
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-200">
      <span class="w-3.5 h-3.5 rounded-sm bg-[#EAB308] border border-white/20 shrink-0"></span>
      <span class="font-medium text-yellow-300">Waspada</span>
      <span class="text-[10px] text-slate-400 ml-auto">Indeks Kerentanan ≤ {hazardLowMax}</span>
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-200">
      <span class="w-3.5 h-3.5 rounded-sm border border-slate-500 bg-transparent shrink-0"></span>
      <span class="font-medium text-slate-300">Tanpa Pemicu</span>
      <span class="text-[10px] text-slate-400 ml-auto">Hujan &lt; {rainThreshold} mm / transparan</span>
    </div>

    <div class="flex items-center gap-2 text-xs text-slate-400">
      <span class="w-3.5 h-3.5 rounded-sm border border-dashed border-slate-600 bg-slate-900/50 shrink-0"></span>
      <span class="font-medium text-slate-400">Data Tidak Tersedia</span>
      <span class="text-[10px] text-slate-500 ml-auto">NoData / luar wilayah</span>
    </div>
  </div>

  {#if isProvisional}
    <div class="mt-2 text-[10px] text-amber-400/90 italic">
      * Batas kelas kerentanan ({hazardLowMax} / {hazardMediumMax}) bersifat provisori.
    </div>
  {/if}

  <!-- Scientific Disclaimer & Limitations -->
  <div class="mt-2.5 p-2 bg-slate-900/90 rounded-lg border border-slate-800 text-[10px] text-slate-400 leading-relaxed space-y-1">
    <div class="font-semibold text-amber-300/90">
      Catatan & Batasan Metodologi
    </div>
    <ul class="list-disc pl-3.5 space-y-0.5">
      <li>Bukan peringatan dini resmi dari instansi berwenang (PVMBG/BNPB/BMKG).</li>
      <li>Status "Tanpa Pemicu" bukan jaminan bebas longsor (gempa, lereng curam, drainase lokal dapat memicu).</li>
      <li>Indeks kerentanan BNPB (0–1) direratakan ke resolusi grid ECMWF (~25 km); bukan probabilitas kejadian.</li>
      <li>Kerentanan bukan bahaya fisik lereng; gabungannya dengan hujan belum divalidasi.</li>
      <li>Ambang pemicu {rainThreshold} mm/24h diadaptasi dari Yuniawan et al. (2022).</li>
    </ul>
  </div>
</div>

<style>
  .landslide-legend-card {
    position: fixed;
    bottom: 24px;
    left: 24px;
    z-index: 40;
    width: min(340px, calc(100vw - 32px));
    max-height: calc(100vh - 120px);
    overflow-y: auto;
    padding: 14px;
    border-radius: 16px;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.15);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(16px);
  }
  @media (max-width: 1200px) {
    .landslide-legend-card { left: 16px; bottom: 150px; max-height: calc(100dvh - 230px); }
  }
</style>
