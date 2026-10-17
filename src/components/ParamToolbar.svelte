<script>
  import { ECMWF_PARAMS } from '../services/ecmwf.js';

  let {
    params = ECMWF_PARAMS,
    activeVar = 't2m',
    onSelectVar,
    windActive = false,
    windSpeed = 1.0,
    windStatus = { state: 'ready', mode: 'demo', message: 'Simulasi — bukan data model' },
    onToggleWind,
    onChangeWindSpeed,
  } = $props();
</script>

<div class="fixed left-5 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center gap-2.5">
  <!-- Wind Animation Modern Slider & Button (Placed directly above Temperature) -->
  <div class="relative group flex flex-col items-center">
    <!-- Main Wind Control Pill -->
    <div
      class="flex flex-col items-center gap-1.5 p-1 rounded-3xl transition-all duration-300 border backdrop-blur-md {
        windActive
          ? 'bg-[#2563EB]/20 border-[#2563EB]/60 shadow-lg shadow-blue-500/30 ring-1 ring-[#2563EB]/40'
          : 'bg-white/10 hover:bg-white/15 border-white/20 shadow-lg shadow-black/20 hover:border-white/35'
      }"
    >
      <!-- Modern Slider Switch -->
      <button
        type="button"
        onclick={onToggleWind}
        class="relative w-11 h-6 rounded-full transition-colors duration-300 flex items-center px-0.5 border cursor-pointer {
          windActive
            ? 'bg-[#2563EB] border-[#2563EB] shadow-md shadow-blue-500/50'
            : 'bg-black/30 border-white/20'
        }"
        aria-label="Toggle Animasi Angin"
        title="Aktifkan / Nonaktifkan Animasi Angin"
      >
        <!-- Sliding Knob -->
        <div
          class="w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-300 flex items-center justify-center {
            windActive ? 'translate-x-5' : 'translate-x-0'
          }"
        >
          <svg class="w-3 h-3 text-[#2563EB]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" />
            <path d="M9.6 4.6A2 2 0 1 1 11 8H2" />
            <path d="M12.6 19.4A2 2 0 1 0 14 16H2" />
          </svg>
        </div>
      </button>

      <!-- Wind Icon Button -->
      <button
        type="button"
        onclick={onToggleWind}
        class="w-11 h-11 rounded-full flex flex-col items-center justify-center border transition-all duration-200 cursor-pointer {
          windActive
            ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-lg shadow-blue-500/50 ring-2 ring-blue-400/50 scale-105'
            : 'bg-white/10 hover:bg-white/20 text-white/80 border-white/20 hover:text-white hover:scale-105 active:scale-95'
        }"
        aria-label="Animasi Angin"
      >
        <svg
          class="w-5 h-5 transition-transform duration-300 {windActive ? 'text-white drop-shadow-[0_0_6px_rgba(255,255,255,0.7)]' : 'text-slate-200'}"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" />
          <path d="M9.6 4.6A2 2 0 1 1 11 8H2" />
          <path d="M12.6 19.4A2 2 0 1 0 14 16H2" />
        </svg>
        <span class="text-[8px] font-bold tracking-tight mt-0.5 uppercase {windActive ? 'text-white' : 'text-slate-300'}">Wind</span>
      </button>
    </div>

    {#if windActive}
      <div class="absolute left-full top-0 ml-3 w-60 rounded-lg bg-slate-900/95 border border-white/20 px-3 py-2 text-xs text-white pointer-events-none group-hover:opacity-0 group-focus-within:opacity-0" role="status">
        {windStatus.mode === 'model' ? 'Angin: data model NWP' : 'Simulasi — bukan data model'}
        {#if windStatus.state === 'loading'}
          <span class="block text-slate-300">Memuat U/V model...</span>
        {/if}
      </div>
    {/if}

    <!-- Flyout Modern Speed Slider & Status Panel (Hover / Interactive) -->
    <div
      class="absolute left-full top-0 ml-3 w-60 p-3.5 rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-white/15 text-white shadow-2xl transition-all duration-200 pointer-events-none group-hover:pointer-events-auto opacity-0 group-hover:opacity-100 z-50 flex flex-col gap-2.5"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <svg class="w-4 h-4 text-[#2563EB]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" />
            <path d="M9.6 4.6A2 2 0 1 1 11 8H2" />
            <path d="M12.6 19.4A2 2 0 1 0 14 16H2" />
          </svg>
          <span class="text-xs font-semibold text-white">Animasi Angin</span>
        </div>
        <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold font-mono tracking-wider {
          windActive
            ? 'bg-[#2563EB] text-white shadow-sm shadow-blue-500/50'
            : 'bg-white/10 text-slate-400'
        }">
          {windActive ? 'AKTIF' : 'OFF'}
        </span>
      </div>

      {#if windActive}
        <div class="rounded-lg bg-black/40 border border-white/10 px-2.5 py-1.5 text-[11px] text-slate-200" role="status">
          <span class="font-medium {windStatus.mode === 'model' ? 'text-emerald-400' : 'text-amber-300'}">
            {windStatus.mode === 'model' ? 'Data Model NWP' : 'Simulasi — bukan data model'}
          </span>
          <span class="block text-[10px] text-slate-400 mt-0.5">
            {windStatus.mode === 'model' ? 'U/V numerik aktif' : 'Data U/V model belum ada di server'}
          </span>
          {#if windStatus.state === 'loading'}
            <span class="block text-[10px] text-blue-300 animate-pulse mt-0.5">Memuat tile U/V model...</span>
          {/if}
        </div>
      {/if}

      <!-- Modern Speed Slider Track -->
      <div class="space-y-1.5 pt-1 border-t border-white/10">
        <div class="flex items-center justify-between text-[11px] text-slate-300">
          <span>Kecepatan Aliran:</span>
          <span class="font-mono font-bold text-blue-400">{windSpeed.toFixed(1)}x</span>
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
        <div class="flex justify-between text-[9px] text-slate-400 font-mono">
          <span>0.3x</span>
          <span>1.0x</span>
          <span>2.5x</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Parameter Buttons (Temperature, RH, Rain, etc) -->
  {#each params as btn}
    {@const isActive = activeVar === btn.id}
    <div class="relative group">
      <button
        type="button"
        onclick={() => onSelectVar?.(btn.id)}
        class="w-12 h-12 rounded-full flex items-center justify-center border transition-all duration-200 backdrop-blur-md cursor-pointer {
          isActive
            ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-lg shadow-blue-500/40 ring-2 ring-blue-400/50 scale-105'
            : 'bg-white/10 hover:bg-white/20 text-white border-white/20 shadow-lg shadow-black/20 hover:border-white/35 hover:scale-105 active:scale-95'
        }"
        aria-label={btn.label}
      >
        <span class="font-bold tracking-tighter {btn.short.length > 3 ? 'text-[8px]' : 'text-[10px]'}">{btn.short}</span>
      </button>
      <div
        class="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 z-50"
      >
        {btn.label}{btn.units ? ` (${btn.units})` : ''}
      </div>
    </div>
  {/each}
</div>
