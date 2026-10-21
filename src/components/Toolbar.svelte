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
    { id: 'gfs', label: 'GFS', icon: 'gfs', active: () => activeModel === 'gfs', enabled: true },
    { id: 'icon', label: 'ICON', icon: 'icon', active: () => activeModel === 'icon', enabled: true },
    { id: 'landslide', label: 'Potensi Tanah Longsor', icon: 'landslide', active: () => activeModel === 'landslide', enabled: true },
    { id: 'flood', label: 'Indonesia Flood Potential', icon: 'flood', active: () => activeModel === 'flood', enabled: true },
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
        {:else if btn.icon === 'ecmwf'}
          <span class="font-bold text-[10px] tracking-tighter">EC</span>
        {:else if btn.icon === 'gfs'}
          <span class="font-bold text-[10px] tracking-tighter">GFS</span>
        {:else if btn.icon === 'icon'}
          <span class="font-bold text-[10px] tracking-tighter">ICO</span>
        {:else if btn.icon === 'landslide'}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 20 10 4l5 10 3-4 4 10Z"/><path d="m13 6 3 3m1-5 3 3m-2 11 3 2"/></svg>
        {:else if btn.icon === 'flood'}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12q3-3 5 0t5 0t5 0t5 0M2 18q3-3 5 0t5 0t5 0t5 0M8 9V4h8v5"/></svg>
        {:else if btn.icon === 'cawo'}
          <span class="font-bold text-[10px] tracking-tighter">CAW</span>
        {:else if btn.icon === 'wrf'}
          <span class="font-bold text-[10px] tracking-tighter">WRF</span>
        {:else if btn.icon === 'chem'}
          <span class="font-bold text-[9px] tracking-tighter">CHEM</span>
        {/if}
      </button>

      <!-- Tooltip on Left -->
      <div
        class="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 flex items-center gap-1.5 z-50"
      >
        <span>{btn.label}</span>
        {#if !btn.enabled}
          <span class="text-[9px] px-1.5 py-0.2 rounded bg-white/10 text-slate-400 font-normal">segera</span>
        {/if}
      </div>
    </div>
  {/each}
</div>
