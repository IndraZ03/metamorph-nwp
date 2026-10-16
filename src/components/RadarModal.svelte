<script>
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import { fetchRadarCatalog, fetchRadarManifest } from '../services/bmkg.js';

  let { currentStation, currentOpacity = 0.8, onSelect, onClose } = $props();

  let loading = $state(true);
  let error = $state(null);
  let catalog = $state(null);
  let sites = $state([]);
  let selectedCode = $state(currentStation?.code || 'BAL');
  let opacity = $state(currentOpacity);

  let selectedSite = $derived(sites.find(s => s.code === selectedCode));

  onMount(async () => {
    try {
      loading = true;
      catalog = await fetchRadarCatalog();
      sites = (catalog.sites || []).filter(s => s.bounds && s.bounds.overlayTLC);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  async function handleApply() {
    if (!selectedSite) return;
    try {
      loading = true;
      const manifest = await fetchRadarManifest(selectedSite.code, catalog?.product || 'CMAX', catalog?.base);
      onSelect({
        site: selectedSite,
        product: catalog?.product || 'CMAX',
        base: catalog?.base,
        legends: catalog?.legends,
        manifest,
        opacity,
      });
      onClose();
    } catch (e) {
      error = `Gagal memuat manifest radar: ${e.message}`;
      loading = false;
    }
  }

  function handleRemove() {
    onSelect(null);
    onClose();
  }
</script>

<Modal
  title="Data Radar Cuaca BMKG"
  subtitle="Komposit CMAX reflektivitas (dBZ) per situs stasiun"
  {onClose}
>
  {#snippet icon()}
    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2a10 10 0 0 0-10 10" />
      <path d="M12 6a6 6 0 0 0-6 6" />
      <path d="M12 10a2 2 0 0 0-2 2" />
      <line x1="12" y1="12" x2="20" y2="4" />
      <circle cx="12" cy="12" r="1" />
    </svg>
  {/snippet}

  {#if loading}
    <div class="py-10 flex flex-col items-center justify-center gap-3 text-slate-500">
      <div class="w-8 h-8 border-2 border-sky-600 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-xs">Memuat katalog stasiun radar BMKG...</span>
    </div>
  {:else if error}
    <div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
      <svg class="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div>{error}</div>
    </div>
  {:else}
    <!-- Station Selector Grid -->
    <div class="space-y-2">
      <div class="text-xs font-semibold text-slate-700 uppercase tracking-wider">Pilih Situs Radar</div>
      <div class="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
        {#each sites as site}
          <button
            type="button"
            onclick={() => selectedCode = site.code}
            class="p-2.5 rounded-xl border text-left transition-all flex flex-col gap-0.5 {selectedCode === site.code ? 'bg-sky-50 border-sky-500 text-sky-900 shadow-sm' : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'}"
          >
            <div class="flex items-center justify-between w-full">
              <span class="font-semibold text-xs">{site.label}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded font-mono font-medium {selectedCode === site.code ? 'bg-sky-200/80 text-sky-800' : 'bg-slate-100 text-slate-600'}">{site.code}</span>
            </div>
            <span class="text-[10px] text-slate-500 truncate">{site.Stasiun || 'Stasiun Meteorologi'}</span>
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

    {#if selectedSite}
      <div class="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-1">
        <div class="flex justify-between">
          <span class="text-slate-500">Koordinat</span>
          <span class="font-mono font-medium">{selectedSite.lat?.toFixed(4)}, {selectedSite.lon?.toFixed(4)}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Produk</span>
          <span class="font-mono text-sky-700 font-semibold">CMAX (Resolusi 10 Menit)</span>
        </div>
      </div>
    {/if}

    <!-- Actions -->
    <div class="flex items-center justify-between pt-2">
      {#if currentStation}
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
          onclick={handleApply}
          class="px-5 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-600/20 transition-all flex items-center gap-1.5"
        >
          <span>Terapkan</span>
        </button>
      </div>
    </div>
  {/if}
</Modal>
