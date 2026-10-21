<script>
  import { SPARTAN_PRODUCTS } from '../services/spartan.js';
  let {
    activeModel = null,
    radarActive = false,
    satelliteActive = false,
    drawingActive = false,
    spartanActive = false,
    spartanProduct = 'fwi',
    onSelectSpartan,
    onOpenRadar,
    onOpenSatellite,
    onOpenSpartan,
    onSelectModel,
    onToggleDrawing,
  } = $props();

  let spartanMenuOpen = $state(false);

  const BUTTONS = [
    { id: 'radar', label: 'Radar', icon: 'radar', active: () => radarActive, enabled: true },
    { id: 'satelit', label: 'Satelit', icon: 'satellite', active: () => satelliteActive, enabled: true },
    { id: 'spartan', label: 'KARHUTLA', icon: 'spartan', active: () => spartanActive, enabled: true },
    { id: 'ecmwf', label: 'ECMWF', icon: 'ecmwf', active: () => activeModel === 'ecmwf', enabled: true },
    { id: 'gfs', label: 'GFS', icon: 'gfs', active: () => activeModel === 'gfs', enabled: true },
    { id: 'icon', label: 'ICON', icon: 'icon', active: () => activeModel === 'icon', enabled: true },
    { id: 'cawo', label: 'CAWO', icon: 'cawo', active: () => activeModel === 'cawo', enabled: false },
    { id: 'wrf', label: 'WRF', icon: 'wrf', active: () => activeModel === 'wrf', enabled: false },
    { id: 'wrf-chem', label: 'WRF-Chem', icon: 'chem', active: () => activeModel === 'wrf-chem', enabled: false },
  ];

  function handleClick(btn) {
    if (!btn.enabled) return;
    if (btn.id === 'radar') {
      onOpenRadar();
    } else if (btn.id === 'satelit') {
      onOpenSatellite();
    } else if (btn.id === 'spartan') {
      spartanMenuOpen = !spartanMenuOpen;
    } else {
      onSelectModel?.(btn.id);
    }
  }
</script>

<div class="fixed right-5 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center gap-2.5">
  <div class="relative group">
    <button
      type="button"
      onclick={() => onToggleDrawing?.()}
      class="w-12 h-12 rounded-full flex items-center justify-center border transition-all duration-200 backdrop-blur-md cursor-pointer {
        drawingActive
          ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-lg shadow-blue-500/40 ring-2 ring-blue-400/50 scale-105'
          : 'bg-white/10 hover:bg-white/20 text-white border-white/20 shadow-lg shadow-black/20 hover:border-white/35 hover:scale-105 active:scale-95'
      }"
      aria-label="Drawing"
      aria-expanded={drawingActive}
      aria-controls="drawing-sidebar"
      title="Drawing"
    >
      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 19l7-7 3 3-7 7-3-3z" />
        <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
        <path d="M2 2l7.586 7.586" />
        <circle cx="11" cy="11" r="2" />
      </svg>
    </button>
    <div
      class="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 z-50"
    >
      Drawing
    </div>
  </div>
  {#each BUTTONS as btn}
    {@const isActive = btn.active()}
    <div class="relative group">
      {#if btn.id === 'spartan'}
        <div class="karhutla-flyout" class:open={spartanMenuOpen} inert={!spartanMenuOpen} aria-label="Produk KARHUTLA">
          {#each SPARTAN_PRODUCTS as product}
            <button type="button" aria-pressed={spartanProduct === product.id} title={product.name} onclick={() => onSelectSpartan?.(product)}>{product.code}</button>
          {/each}
        </div>
      {/if}
      <button
        type="button"
        onclick={() => handleClick(btn)}
        class="w-12 h-12 rounded-full flex items-center justify-center border transition-all duration-200 backdrop-blur-md cursor-pointer {
          isActive
            ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-lg shadow-blue-500/40 ring-2 ring-blue-400/50 scale-105'
            : btn.enabled
              ? 'bg-white/10 hover:bg-white/20 text-white border-white/20 shadow-lg shadow-black/20 hover:border-white/35 hover:scale-105 active:scale-95'
              : 'bg-white/5 text-white/30 border-white/10 cursor-not-allowed'
        }"
        aria-label={btn.label}
      >
        {#if btn.icon === 'radar'}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a10 10 0 0 0-10 10" />
            <path d="M12 6a6 6 0 0 0-6 6" />
            <path d="M12 10a2 2 0 0 0-2 2" />
            <line x1="12" y1="12" x2="20" y2="4" />
          </svg>
        {:else if btn.icon === 'satellite'}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M4.93 4.93a10 10 0 0 1 14.14 0" />
            <path d="M7.76 7.76a6 6 0 0 1 8.48 0" />
            <path d="M4.93 19.07a10 10 0 0 0 14.14 0" />
            <path d="M7.76 16.24a6 6 0 0 0 8.48 0" />
          </svg>
        {:else if btn.icon === 'spartan'}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
          </svg>
        {:else if btn.icon === 'ecmwf'}
          <span class="font-bold text-[10px] tracking-tighter">EC</span>
        {:else if btn.icon === 'gfs'}
          <span class="font-bold text-[10px] tracking-tighter">GFS</span>
        {:else if btn.icon === 'icon'}
          <span class="font-bold text-[10px] tracking-tighter">ICO</span>
        {:else if btn.icon === 'cawo'}
          <span class="font-bold text-[10px] tracking-tighter">CAW</span>
        {:else if btn.icon === 'wrf'}
          <span class="font-bold text-[10px] tracking-tighter">WRF</span>
        {:else if btn.icon === 'chem'}
          <span class="font-bold text-[9px] tracking-tighter">CHEM</span>
        {/if}
      </button>

      <!-- Tooltip on Left -->
      {#if btn.id !== 'spartan' || !spartanActive}
      <div
        class="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 flex items-center gap-1.5 z-50"
      >
        <span>{btn.label}</span>
        {#if !btn.enabled}
          <span class="text-[9px] px-1.5 py-0.2 rounded bg-white/10 text-slate-400 font-normal">segera</span>
        {/if}
      </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .karhutla-flyout { position: absolute; right: calc(100% + 12px); top: 50%; display: flex; gap: 5px; padding: 7px; border: 1px solid #64748b; border-radius: 12px; background: #172033ee; transform: translate(18px, -50%) scaleX(.85); transform-origin: right center; opacity: 0; visibility: hidden; pointer-events: none; transition: transform 180ms ease, opacity 180ms ease, visibility 180ms; }
  .karhutla-flyout.open { transform: translate(0, -50%) scaleX(1); opacity: 1; visibility: visible; pointer-events: auto; }
  .karhutla-flyout button { color: #fff; font-size: 11px; padding: 9px 7px; border: 1px solid #64748b; border-radius: 7px; cursor: pointer; }
  .karhutla-flyout button[aria-pressed='true'] { background: #2563eb; border-color: #93c5fd; }
  @media (max-width: 480px) { .karhutla-flyout { gap: 3px; padding: 5px; right: calc(100% + 7px); } .karhutla-flyout button { padding: 9px 4px; font-size: 10px; } }
  @media (prefers-reduced-motion: reduce) { .karhutla-flyout { transition: none; } }
</style>
