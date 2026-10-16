<script>
  let { title, icon, subtitle, onClose, children } = $props();

  function onKeydown(e) {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div
  class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in"
  role="dialog"
  aria-modal="true"
>
  <div
    class="w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-scale-in"
  >
    <!-- Header -->
    <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
      <div class="flex items-center gap-3">
        {#if icon}
          <div class="w-9 h-9 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center border border-sky-200">
            {@render icon()}
          </div>
        {/if}
        <div>
          <h3 class="text-base font-semibold text-slate-900 tracking-tight">{title}</h3>
          {#if subtitle}
            <p class="text-xs text-slate-500">{subtitle}</p>
          {/if}
        </div>
      </div>
      <button
        onclick={onClose}
        class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
        title="Tutup (Esc)"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Body -->
    <div class="p-5 overflow-y-auto space-y-4">
      {@render children()}
    </div>
  </div>
</div>

<style>
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes scaleIn {
    from { opacity: 0; transform: scale(0.96); }
    to { opacity: 1; transform: scale(1); }
  }
  .animate-fade-in {
    animation: fadeIn 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .animate-scale-in {
    animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
</style>
