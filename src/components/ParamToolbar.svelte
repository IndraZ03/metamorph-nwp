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
        class="w-12 h-12 rounded-full flex items-center justify-center border {
          isActive
            ? 'bg-sky-600 text-white border-sky-600'
            : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
        }"
        aria-label={btn.label}
      >
        <span class="font-bold tracking-tighter {btn.short.length > 3 ? 'text-[8px]' : 'text-[10px]'}">{btn.short}</span>
      </button>
      <div
        class="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-2.5 py-1 rounded-lg bg-slate-900 text-xs font-medium text-white whitespace-nowrap shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150"
      >
        {btn.label}{btn.units ? ` (${btn.units})` : ''}
      </div>
    </div>
  {/each}
</div>
