<script>
  import { ECMWF_PARAMS } from '../services/ecmwf.js';

  let {
    params = ECMWF_PARAMS,
    activeVar = 't2m',
    readyIds = [],
    onSelectVar,
    windActive = false,
    windSpeed = 1.0,
    windStatus = { state: 'ready', mode: 'unavailable', message: 'Data U/V belum dimuat' },
    onToggleWind,
    onChangeWindSpeed,
  } = $props();

  function isReady(id) {
    return !readyIds.length || readyIds.includes(id);
  }
</script>

<div class="fixed left-5 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center gap-2.5">
  <div class="relative group flex flex-col items-center">
    <div
      class="flex flex-col items-center gap-1.5 px-2 py-1.5 rounded-lg border backdrop-blur-md {
        windActive
          ? 'bg-[#2563EB]/20 border-[#2563EB]/50'
          : 'bg-white/10 border-white/20'
      }"
    >
      <span class="text-[9px] font-semibold leading-tight text-center text-white/90 whitespace-nowrap">Animasi Angin</span>
      <button
        type="button"
        role="switch"
        aria-checked={windActive}
        onclick={onToggleWind}
        class="relative w-10 h-5 rounded-full transition-colors duration-200 flex items-center px-0.5 border cursor-pointer {
          windActive
            ? 'bg-[#2563EB] border-[#2563EB]'
            : 'bg-black/35 border-white/20'
        }"
        aria-label="Animasi Angin"
      >
        <span
          class="block w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 {
            windActive ? 'translate-x-[18px]' : 'translate-x-0'
          }"
        ></span>
      </button>
    </div>

    <div
      class="absolute left-full top-1/2 -translate-y-1/2 ml-3 w-44 px-3 py-2 rounded-lg bg-slate-900/90 backdrop-blur-md border border-white/15 text-white shadow-xl transition-opacity duration-150 pointer-events-none group-hover:pointer-events-auto opacity-0 group-hover:opacity-100 z-50"
    >
      <div class="flex items-center justify-between text-[11px] text-slate-300 mb-1.5">
        <span>Kecepatan</span>
        <span class="font-mono font-semibold text-blue-400">{windSpeed.toFixed(1)}x</span>
      </div>
      <input
        type="range"
        min="0.3"
        max="2.5"
        step="0.1"
        value={windSpeed}
        oninput={(e) => onChangeWindSpeed?.(parseFloat(e.target.value))}
        class="modern-slider"
      />
    </div>
  </div>

  <!-- Parameter Buttons (Temperature, RH, Rain, etc) -->
  {#each params as btn}
    {@const isActive = activeVar === btn.id}
    {@const ready = isReady(btn.id)}
    <div class="relative group">
      <button
        type="button"
        onclick={() => ready && onSelectVar?.(btn.id)}
        disabled={!ready}
        class="w-12 h-12 rounded-full flex items-center justify-center border transition-all duration-200 backdrop-blur-md {
          isActive
            ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-lg shadow-blue-500/40 ring-2 ring-blue-400/50 scale-105 cursor-pointer'
            : ready
              ? 'bg-white/10 hover:bg-white/20 text-white border-white/20 shadow-lg shadow-black/20 hover:border-white/35 hover:scale-105 active:scale-95 cursor-pointer'
              : 'bg-white/5 text-white/35 border-white/10 cursor-not-allowed'
        }"
        aria-label={btn.label}
      >
        <span class="font-bold tracking-tighter {btn.short.length > 3 ? 'text-[8px]' : 'text-[10px]'}">{btn.short}</span>
      </button>
      <div
        class="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 z-50"
      >
        {btn.label}{btn.units ? ` (${btn.units})` : ''}{ready ? '' : ' — tile belum tersedia'}
      </div>
    </div>
  {/each}
</div>
