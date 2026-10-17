<script>
  import { legendCss, legendFor } from '../services/nwp.js';
  import { SPARTAN_CLASSES, spartanRangeLabel } from '../services/spartan.js';

  let {
    radarData = null,
    satelliteData = null,
    nwpData = null,
    spartanData = null,
    onCloseRadar,
    onCloseSatellite,
    onCloseNwp,
    onCloseSpartan,
    onChangeRadarFrame,
    onChangeSatelliteBaserun,
  } = $props();

  function nwpLegend() {
    if (!nwpData?.modelId || !nwpData?.varId) return null;
    return legendFor(nwpData.modelId, nwpData.varId);
  }

  const RADAR_LEVELS = [
    { dbz: 5, color: '#07fef6' },
    { dbz: 10, color: '#0096ff' },
    { dbz: 15, color: '#0002fe' },
    { dbz: 20, color: '#01fe03' },
    { dbz: 25, color: '#00c703' },
    { dbz: 30, color: '#009902' },
    { dbz: 35, color: '#fffe00' },
    { dbz: 40, color: '#ffc801' },
    { dbz: 45, color: '#ff7707' },
    { dbz: 50, color: '#fb0103' },
    { dbz: 55, color: '#c90002' },
    { dbz: 60, color: '#980001' },
    { dbz: 65, color: '#ff00ff' },
    { dbz: 70, color: '#9800fe' },
  ];
</script>

<div class="fixed bottom-6 left-6 z-40 flex flex-col gap-3 max-w-sm">
  <!-- Active Layers Panel -->
  {#if radarData || satelliteData || nwpData || spartanData}
    <div class="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-xl space-y-3">
      <div class="flex items-center justify-between text-xs font-bold text-slate-700 uppercase tracking-wider">
        <span>Lapisan Aktif</span>
      </div>

      <!-- Radar Active Item -->
      {#if radarData}
        <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span class="text-xs font-semibold text-slate-900">Radar {radarData.site.label}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-sky-100 font-mono text-sky-800 font-bold">CMAX</span>
            </div>
            <button
              onclick={onCloseRadar}
              class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-600 hover:bg-slate-200 transition-colors"
              title="Hapus Radar"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="text-[11px] text-slate-600 font-mono flex items-center justify-between">
            <span>Frame:</span>
            <span class="text-slate-900 font-semibold">{radarData.currentFile || radarData.manifest?.latest?.file}</span>
          </div>

          <!-- Radar Reflectivity Scale Bar -->
          <div class="space-y-1 pt-1">
            <div class="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>5 dBZ</span>
              <span class="font-sans font-medium text-slate-700">Reflektivitas (dBZ)</span>
              <span>70 dBZ</span>
            </div>
            <div class="h-2 rounded flex overflow-hidden border border-slate-300">
              {#each RADAR_LEVELS as lvl}
                <div class="flex-1 h-full" style="background-color: {lvl.color};" title="{lvl.dbz} dBZ"></div>
              {/each}
            </div>
          </div>
        </div>
      {/if}

      <!-- Satellite Active Item -->
      {#if satelliteData}
        <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-sky-500"></span>
              <span class="text-xs font-semibold text-slate-900">{satelliteData.product.label}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-indigo-100 font-mono text-indigo-800 font-bold">TMS</span>
            </div>
            <button
              onclick={onCloseSatellite}
              class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-600 hover:bg-slate-200 transition-colors"
              title="Hapus Satelit"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="text-[11px] text-slate-600 font-mono flex items-center justify-between">
            <span>Waktu UTC:</span>
            <span class="text-slate-900 font-semibold">{satelliteData.currentBaserun}</span>
          </div>

          <!-- Time Step Selector -->
          {#if satelliteData.baseruns?.length}
            <div class="space-y-1 pt-1">
              <div class="text-[10px] text-slate-500 font-medium">Pilih frame waktu:</div>
              <div class="flex gap-1 overflow-x-auto pb-1 max-w-full">
                {#each satelliteData.baseruns.slice(0, 6) as br}
                  {@const timeStr = br.split('T')[1].substring(0, 5)}
                  <button
                    onclick={() => onChangeSatelliteBaserun(br)}
                    class="px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap transition-colors {satelliteData.currentBaserun === br ? 'bg-sky-600 text-white font-bold shadow-sm' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'}"
                  >
                    {timeStr}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}

      <!-- SPARTAN Active Item -->
      {#if spartanData}
        <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-orange-500"></span>
              <span class="text-xs font-semibold text-slate-900">SPARTAN {spartanData.product.code}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-orange-100 font-mono text-orange-800 font-bold">TMS</span>
            </div>
            <button
              onclick={onCloseSpartan}
              class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-600 hover:bg-slate-200 transition-colors"
              title="Hapus SPARTAN"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="text-[11px] text-slate-600 font-mono flex items-center justify-between">
            <span>Rentang:</span>
            <span class="text-slate-900 font-semibold">{spartanRangeLabel(spartanData.startDate, spartanData.endDate)}</span>
          </div>

          <!-- SPARTAN Hazard Scale Bar -->
          <div class="space-y-1 pt-1">
            <div class="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>Rendah</span>
              <span class="font-sans font-medium text-slate-700">Bahaya Kebakaran</span>
              <span>Ekstrem</span>
            </div>
            <div class="h-2 rounded flex overflow-hidden border border-slate-300">
              {#each SPARTAN_CLASSES as cls}
                <div class="flex-1 h-full" style="background-color: {cls.color};" title={cls.label}></div>
              {/each}
            </div>
            <div class="flex justify-between text-[9px] text-slate-400 font-mono">
              {#each SPARTAN_CLASSES as cls}
                <span>{cls.label}</span>
              {/each}
            </div>
          </div>
        </div>
      {/if}

      {#if nwpData}
        {@const legend = nwpLegend()}
        <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-amber-500"></span>
              <span class="text-xs font-semibold text-slate-900">{nwpData.title}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-amber-100 font-mono text-amber-800 font-bold">{nwpData.badge}</span>
            </div>
            <button
              onclick={onCloseNwp}
              class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-600 hover:bg-slate-200 transition-colors"
              title="Hapus {nwpData.title}"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="text-[11px] text-slate-600 font-mono flex flex-col gap-0.5">
            <div class="flex items-center justify-between">
              <span>Run:</span>
              <span class="text-slate-900 font-semibold">{nwpData.runTime}</span>
            </div>
            <div class="flex items-center justify-between">
              <span>Valid:</span>
              <span class="text-slate-900 font-semibold">{nwpData.validTime}</span>
            </div>
          </div>

          {#if legend}
            <div class="space-y-1 pt-1">
              <div class="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>{legend.min}{legend.units ? ` ${legend.units}` : ''}</span>
                <span class="font-sans font-medium text-slate-700">{legend.label}</span>
                <span>{legend.max}{legend.units ? ` ${legend.units}` : ''}</span>
              </div>
              <div
                class="h-2 rounded overflow-hidden border border-slate-300"
                style="background: {legendCss(nwpData.modelId, nwpData.varId)};"
              ></div>
              {#if legend.ticks}
                <div class="flex justify-between text-[9px] text-slate-400 font-mono">
                  {#each legend.ticks as tick}
                    <span>{tick}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>
