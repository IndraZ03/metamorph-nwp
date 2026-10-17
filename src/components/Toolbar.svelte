<script>
  let {
    activeModel = null,
    radarActive = false,
    satelliteActive = false,
    onOpenRadar,
    onOpenSatellite,
    onSelectModel,
  } = $props();

  const BUTTONS = [
    { id: 'radar', label: 'Radar', icon: 'radar', active: () => radarActive, enabled: true },
    { id: 'satelit', label: 'Satelit', icon: 'satellite', active: () => satelliteActive, enabled: true },
    { id: 'ecmwf', label: 'ECMWF', icon: 'ecmwf', active: () => activeModel === 'ecmwf', enabled: true },
    { id: 'arome', label: 'AROME', icon: 'arome', active: () => activeModel === 'arome', enabled: false },
    { id: 'accessr', label: 'ACCESS-R', icon: 'accessr', active: () => activeModel === 'accessr', enabled: false },
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
    } else {
      onSelectModel?.(btn.id);
    }
  }
</script>

<div class="fixed right-5 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center gap-2.5">
  {#each BUTTONS as btn}
    {@const isActive = btn.active()}
    <div class="relative group">
      <button
        type="button"
        onclick={() => handleClick(btn)}
        class="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 border shadow-md relative {
          isActive
            ? 'bg-sky-600 text-white border-sky-600 shadow-sky-600/30 ring-4 ring-sky-500/20 scale-105'
            : btn.enabled
              ? 'bg-white hover:bg-slate-50 text-slate-700 hover:text-slate-900 border-slate-200 hover:border-slate-300 hover:scale-105'
              : 'bg-slate-100 text-slate-400 border-slate-200/80 opacity-70 cursor-not-allowed'
        }"
        aria-label={btn.label}
      >
        <!-- Icon Rendering -->
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
        {:else if btn.icon === 'ecmwf'}
          <span class="font-bold text-[10px] tracking-tighter">EC</span>
        {:else if btn.icon === 'arome'}
          <span class="font-bold text-[10px] tracking-tighter">ARO</span>
        {:else if btn.icon === 'accessr'}
          <span class="font-bold text-[10px] tracking-tighter">ACC</span>
        {:else if btn.icon === 'cawo'}
          <span class="font-bold text-[10px] tracking-tighter">CAW</span>
        {:else if btn.icon === 'wrf'}
          <span class="font-bold text-[10px] tracking-tighter">WRF</span>
        {:else if btn.icon === 'chem'}
          <span class="font-bold text-[9px] tracking-tighter">CHEM</span>
        {/if}

        {#if isActive}
          <span class="absolute top-1 right-1 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-white animate-pulse"></span>
        {/if}
      </button>

      <!-- Tooltip on Left -->
      <div
        class="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-2.5 py-1 rounded-lg bg-slate-900 text-xs font-medium text-white whitespace-nowrap shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 flex items-center gap-1.5"
      >
        <span>{btn.label}</span>
        {#if !btn.enabled}
          <span class="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-300 font-normal">segera</span>
        {/if}
      </div>
    </div>
  {/each}
</div>
