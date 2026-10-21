<script>
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import {
    SPARTAN_PRODUCTS,
    SPARTAN_CLASSES,
    SPARTAN_MAX_RANGE_DAYS,
    formatSpartanDate,
    parseSpartanDate,
    addDays,
    spartanRangeLabel,
    verifySpartan,
    findLatestValidSpartanStart,
  } from '../services/spartan.js';

  let {
    currentProduct = null,
    currentStart = null,
    currentRangeDays = SPARTAN_MAX_RANGE_DAYS,
    currentOpacity = 0.9,
    onSelect,
    onClose,
  } = $props();

  let loading = $state(!currentStart);
  let verifying = $state(false);
  let error = $state(null);
  let selectedId = $state(currentProduct?.id || 'fwi');
  let startInput = $state('');
  let rangeDays = $state(currentRangeDays);
  let opacity = $state(currentOpacity);

  let selectedProduct = $derived(SPARTAN_PRODUCTS.find((p) => p.id === selectedId));

  let endLabel = $derived.by(() => {
    if (!startInput) return '—';
    try {
      const start = new Date(
        +startInput.slice(0, 4),
        +startInput.slice(5, 7) - 1,
        +startInput.slice(8, 10)
      );
      const startStr = formatSpartanDate(start);
      const endStr = formatSpartanDate(addDays(start, rangeDays));
      return spartanRangeLabel(startStr, endStr);
    } catch {
      return '—';
    }
  });

  function toInputValue(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  onMount(async () => {
    if (currentStart) {
      startInput = toInputValue(parseSpartanDate(currentStart));
      return;
    }
    try {
      const latest = await findLatestValidSpartanStart('dmc');
      startInput = toInputValue(latest);
    } catch (e) {
      error = `Gagal mencari data SPARTAN terbaru: ${e.message}`;
    } finally {
      loading = false;
    }
  });

  async function handleApply() {
    if (!selectedProduct || !startInput) return;
    try {
      verifying = true;
      error = null;
      const start = new Date(
        +startInput.slice(0, 4),
        +startInput.slice(5, 7) - 1,
        +startInput.slice(8, 10)
      );
      const startStr = formatSpartanDate(start);
      const endStr = formatSpartanDate(addDays(start, rangeDays));
      const ok = await verifySpartan({
        product: selectedProduct.id,
        start: startStr,
        end: endStr,
      });
      if (!ok) {
        error =
          'Data SPARTAN belum tersedia untuk tanggal tersebut. Coba tanggal mulai lebih awal (data terbit dengan lag ±1 hari).';
        return;
      }
      onSelect({
        product: selectedProduct,
        startDate: startStr,
        endDate: endStr,
        rangeDays,
        opacity,
      });
      onClose();
    } catch (e) {
      error = `Gagal memverifikasi data SPARTAN: ${e.message}`;
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
  title="SPARTAN — Bahaya Kebakaran Hutan & Lahan"
  subtitle="Indeks cuaca kebakaran BMKG (FWI System), agregasi sampai 7 hari ke depan"
  {onClose}
>
  {#snippet icon()}
    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </svg>
  {/snippet}

  {#if loading}
    <div class="py-10 flex flex-col items-center justify-center gap-3 text-slate-500">
      <div class="w-8 h-8 border-2 border-sky-600 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-xs">Mencari data SPARTAN terbaru...</span>
    </div>
  {:else}
    <!-- Product Selection Cards -->
    <div class="space-y-2">
      <div class="text-xs font-semibold text-slate-700 uppercase tracking-wider">Pilih Produk</div>
      <div class="grid grid-cols-1 gap-2.5">
        {#each SPARTAN_PRODUCTS as prod}
          <button
            type="button"
            onclick={() => (selectedId = prod.id)}
            class="p-3.5 rounded-xl border text-left transition-all flex items-start justify-between {selectedId === prod.id ? 'bg-sky-50 border-sky-500 text-slate-900 shadow-sm' : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'}"
          >
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-sm text-slate-900">{prod.name}</span>
                <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-orange-100 text-orange-800">
                  {prod.code}
                </span>
              </div>
              <p class="text-xs text-slate-500">{prod.desc}</p>
            </div>

            <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center mt-1 shrink-0 ml-2 {selectedId === prod.id ? 'border-sky-600 bg-sky-600' : 'border-slate-300'}">
              {#if selectedId === prod.id}
                <div class="w-2 h-2 rounded-full bg-white"></div>
              {/if}
            </div>
          </button>
        {/each}
      </div>
    </div>

    <!-- Start Date -->
    <div class="space-y-1.5 pt-2 border-t border-slate-200">
      <label class="block text-xs font-medium text-slate-700" for="spartan-start">
        Tanggal Mulai
      </label>
      <input
        id="spartan-start"
        type="date"
        bind:value={startInput}
        class="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
      />
      <p class="text-[11px] text-slate-400">
        Data SPARTAN terbit dengan lag ±1 hari — tanggal mulai otomatis memakai data terbaru yang tersedia.
      </p>
    </div>

    <!-- Range Slider -->
    <div class="space-y-1.5 pt-2 border-t border-slate-200">
      <div class="flex justify-between text-xs">
        <span class="text-slate-700 font-medium">Rentang (hari ke depan)</span>
        <span class="font-mono text-sky-600 font-semibold">{rangeDays} hari · {endLabel}</span>
      </div>
      <input
        type="range"
        min="1"
        max={SPARTAN_MAX_RANGE_DAYS}
        step="1"
        bind:value={rangeDays}
        class="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
      />
      <p class="text-[11px] text-slate-400">
        Tile menampilkan agregasi produk selama rentang tanggal (maksimal 7 hari).
      </p>
    </div>

    <!-- Legend Preview -->
    <div class="space-y-1.5 pt-2 border-t border-slate-200">
      <div class="text-xs font-medium text-slate-700">Legenda Bahaya</div>
      <div class="flex gap-1.5">
        {#each SPARTAN_CLASSES as cls}
          <div class="flex-1 rounded-lg border border-slate-200 overflow-hidden">
            <div class="h-2.5" style="background-color: {cls.color};"></div>
            <div class="text-center text-[10px] font-medium text-slate-700 py-1 bg-white">{cls.label}</div>
          </div>
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

    {#if error}
      <div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
        <svg class="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <div>{error}</div>
      </div>
    {/if}

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
          disabled={verifying || !startInput}
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
