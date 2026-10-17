<script>
  import { ECMWF_PARAMS } from '../services/ecmwf.js';

  let { params = ECMWF_PARAMS, activeVar = 't2m', onSelectVar } = $props();
</script>

<div class="fixed left-5 top-1/2 -translate-y-1/2 z-40 flex flex-col items-center gap-2.5">
  {#each params as btn}
    {@const isActive = activeVar === btn.id}
    <div class="relative group">
      <button
        type="button"
        onclick={() => onSelectVar?.(btn.id)}
        class="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 border shadow-md relative {
          isActive
            ? 'bg-sky-600 text-white border-sky-600 shadow-sky-600/30 ring-4 ring-sky-500/20 scale-105'
            : 'bg-white hover:bg-slate-50 text-slate-700 hover:text-slate-900 border-slate-200 hover:border-slate-300 hover:scale-105'
        }"
        aria-label={btn.label}
      >
        <span class="font-bold tracking-tighter {btn.short.length > 3 ? 'text-[8px]' : 'text-[10px]'}">{btn.short}</span>
        {#if isActive}
          <span class="absolute top-1 right-1 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-white animate-pulse"></span>
        {/if}
      </button>
      <div
        class="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-2.5 py-1 rounded-lg bg-slate-900 text-xs font-medium text-white whitespace-nowrap shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150"
      >
        {btn.label}{btn.units ? ` (${btn.units})` : ''}
      </div>
    </div>
  {/each}
</div>
