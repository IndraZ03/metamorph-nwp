<script>
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import { fetchSatelliteCatalog, findLatestValidBaserun } from '../services/bmkg.js';

  let { currentProduct, currentOpacity = 1.0, onSelect, onClose } = $props();

  let loading = $state(true);
  let verifying = $state(false);
  let error = $state(null);
  let sources = $state([]);
  let selectedId = $state(currentProduct?.id || 'himawari9-ir');
  let opacity = $state(currentOpacity);

  let selectedSource = $derived(sources.find(s => s.id === selectedId));

  onMount(async () => {
    try {
      loading = true;
      const cat = await fetchSatelliteCatalog();
      sources = cat.sources || [];
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  async function handleApply() {
    if (!selectedSource) return;
    try {
      verifying = true;
      // Dynamically verify latest baserun with 200 OK
      const resolved = await findLatestValidBaserun(selectedSource);
      onSelect({
        product: selectedSource,
        baseruns: resolved.list,
        currentBaserun: resolved.current,
        opacity,
      });
      onClose();
    } catch (e) {
      error = `Gagal memverifikasi data satelit: ${e.message}`;
    } finally {
      verifying = false;
    }
  }

  function handleRemove() {
    onSelect(null);
    onClose();
  }
</script>

<Modal
  title="Data Satelit Cuaca Himawari-9"
  subtitle="Observasi resolusi tinggi BMKG tiap 10 menit"
  {onClose}
>
  {#snippet icon()}
    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M4.93 4.93a10 10 0 0 1 14.14 0" />
      <path d="M7.76 7.76a6 6 0 0 1 8.48 0" />
      <path d="M4.93 19.07a10 10 0 0 0 14.14 0" />
      <path d="M7.76 16.24a6 6 0 0 0 8.48 0" />
    </svg>
  {/snippet}

  {#if loading}
    <div class="py-10 flex flex-col items-center justify-center gap-3 text-slate-500">
      <div class="w-8 h-8 border-2 border-sky-600 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-xs">Memuat katalog produk satelit BMKG...</span>
    </div>
  {:else if error}
    <div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
      <svg class="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div>{error}</div>
    </div>
  {:else}
    <!-- Product Selection Cards -->
    <div class="space-y-2">
      <div class="text-xs font-semibold text-slate-700 uppercase tracking-wider">Pilih Kanal Produk</div>
      <div class="grid grid-cols-1 gap-2.5">
        {#each sources as src}
          <button
            type="button"
            onclick={() => selectedId = src.id}
            class="p-3.5 rounded-xl border text-left transition-all flex items-start justify-between {selectedId === src.id ? 'bg-sky-50 border-sky-500 text-slate-900 shadow-sm' : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'}"
          >
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-sm text-slate-900">{src.label}</span>
                <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold {src.param === 'VS' ? 'bg-amber-100 text-amber-800' : 'bg-indigo-100 text-indigo-800'}">
                  {src.param}
                </span>
              </div>
              <p class="text-xs text-slate-500">
                {#if src.param === 'VS'}
                  Kanal Tampak (Visible / Siang Hari) · Resolusi Tinggi (Malam hari hitam/transparan)
                {:else if src.param === 'EH'}
                  Enhanced Infrared (Suhu Puncak Awan / Aktif 24 Jam)
                {:else}
                  {src.attribution}
                {/if}
              </p>
              <div class="flex items-center gap-3 text-[11px] text-slate-400 pt-1">
                <span>Zoom {src.min_zoom}–{src.max_zoom}</span>
                <span>•</span>
                <span>Interval {src.step_minutes} menit</span>
                <span>•</span>
                <span>6 Jam Terakhir</span>
              </div>
            </div>

            <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center mt-1 {selectedId === src.id ? 'border-sky-600 bg-sky-600' : 'border-slate-300'}">
              {#if selectedId === src.id}
                <div class="w-2 h-2 rounded-full bg-white"></div>
              {/if}
            </div>
          </button>
        {/each}
      </div>
    </div>

    <!-- Opacity Slider -->
    <div class="space-y-1.5 pt-2 border-t border-slate-200">
      <div class="flex justify-between text-xs">
        <span class="text-slate-700 font-medium">Opasitas Lapisan</span>
        <span class="font-mono text-sky-600 font-semibold">{Math.round(opacity * 100)}%</span>
      </div>
      <input
        type="range"
        min="0.2"
        max="1"
        step="0.05"
        bind:value={opacity}
        class="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
      />
    </div>

    <!-- Actions -->
    <div class="flex items-center justify-between pt-2">
      {#if currentProduct}
        <button
          type="button"
          onclick={handleRemove}
          class="px-3.5 py-2 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200 transition-colors"
        >
          Hapus Layer
        </button>
      {:else}
        <div></div>
      {/if}

      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={onClose}
          class="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          Batal
        </button>
        <button
          type="button"
          disabled={verifying}
          onclick={handleApply}
          class="px-5 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 disabled:opacity-60 text-white shadow-md shadow-sky-600/20 transition-all flex items-center gap-1.5"
        >
          {#if verifying}
            <div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <span>Memverifikasi...</span>
          {:else}
            <span>Terapkan</span>
          {/if}
        </button>
      </div>
    </div>
  {/if}
</Modal>
