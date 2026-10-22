<script>
  import { legendCss, legendFor } from '../services/nwp.js';
  import { satelliteLegend } from '../services/satelliteLegend.js';
  import { formatWibShort } from '../services/numericTiles.js';
  import { SPARTAN_CLASSES, spartanDateLabel } from '../services/spartan.js';

  const LANDSLIDE_LEVELS = [
    { color: '#DC2626', label: 'Bahaya' },
    { color: '#F97316', label: 'Siaga' },
    { color: '#EAB308', label: 'Waspada' },
  ];

  // Sama dengan ramp di engine/flood/tiles.py: t*200 mm, rgb(30+150t, 180-130t, 230-30t).
  const FLOOD_RAMP = 'linear-gradient(to right, rgb(30,180,230), rgb(180,50,200))';

  let {
    radarData = null,
    satelliteData = null,
    nwpData = null,
    spartanData = null,
    landslideData = null,
    floodData = null,
    onCloseRadar,
    onCloseSatellite,
    onCloseNwp,
    onCloseSpartan,
    onCloseLandslide,
    onChangeLandslideOpacity,
    onToggleInarisk,
    onCloseFlood,
    onChangeFloodOpacity,
    hazardOrder = null,
    onMoveHazard,
  } = $props();

  function nwpLegend() {
    if (!nwpData?.modelId || !nwpData?.varId) return null;
    return legendFor(nwpData.modelId, nwpData.varId);
  }

  function satTime(br) {
    const t = String(br || '').split('T')[1] || '';
    return t.substring(0, 5) || br;
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
  const activeOrder = $derived((hazardOrder || ['nwp', 'spartan', 'satellite', 'radar', 'landslide', 'flood']).filter(kind => ({ radar: radarData, satellite: satelliteData, nwp: nwpData, spartan: spartanData, landslide: landslideData, flood: floodData })[kind]));
</script>

{#snippet orderButtons(kind, label)}
  {#if activeOrder.length > 1}
    <div class="al-order">
      <button type="button" class="al-x" disabled={activeOrder.indexOf(kind) === activeOrder.length - 1} onclick={() => onMoveHazard?.(kind, 1)} title="Naikkan lapisan" aria-label="Naikkan lapisan {label}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 14l6-6 6 6" /></svg></button>
      <button type="button" class="al-x" disabled={activeOrder.indexOf(kind) === 0} onclick={() => onMoveHazard?.(kind, -1)} title="Turunkan lapisan" aria-label="Turunkan lapisan {label}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 10l6 6 6-6" /></svg></button>
    </div>
  {/if}
{/snippet}

{#snippet landslideRow()}
  {#if landslideData}
    <section class="al-row">
      <header class="al-head">
        <div class="al-meta">
          <span class="al-name">Prakiraan Potensi Tanah Longsor</span>
          <span class="al-sub">
            {#if landslideData.runTime}Run {formatWibShort(landslideData.runTime)}{/if}
            {#if landslideData.validTime}<span class="al-dot">·</span> Valid {formatWibShort(landslideData.validTime)}{/if}
          </span>
        </div>
        <button type="button" class="al-x" class:on={landslideData.inarisk} onclick={() => onToggleInarisk?.()}
          title={landslideData.inarisk ? 'Sembunyikan daerah rentan InaRISK' : 'Tampilkan daerah rentan InaRISK'}
          aria-label="Daerah rentan tanah longsor InaRISK" aria-pressed={landslideData.inarisk ? 'true' : 'false'}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 20h18L12 4z" /></svg>
        </button>
        <div class="al-op">
          <button type="button" class="al-x" title="Opasitas" aria-label="Opasitas lapisan {Math.round((landslideData.opacity ?? 0.6) * 100)} persen">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" /></svg>
          </button>
          <div class="al-op-pop">
            <div class="al-op-label"><span>Opasitas</span><span>{Math.round((landslideData.opacity ?? 0.6) * 100)}%</span></div>
            <input type="range" min="0" max="1" step="0.05" value={landslideData.opacity ?? 0.6}
              oninput={(e) => onChangeLandslideOpacity?.(parseFloat(e.currentTarget.value))} aria-label="Opasitas lapisan" />
          </div>
        </div>
        {#if hazardOrder && hazardOrder.length > 1}
          <div class="al-order">
            <button type="button" class="al-x" disabled={hazardOrder.indexOf('landslide') === hazardOrder.length - 1} onclick={() => onMoveHazard?.('landslide', 1)} title="Naikkan lapisan" aria-label="Naikkan lapisan longsor">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 14l6-6 6 6" /></svg>
            </button>
            <button type="button" class="al-x" disabled={hazardOrder.indexOf('landslide') === 0} onclick={() => onMoveHazard?.('landslide', -1)} title="Turunkan lapisan" aria-label="Turunkan lapisan longsor">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 10l6 6 6-6" /></svg>
            </button>
          </div>
        {/if}
        <button type="button" class="al-x" onclick={onCloseLandslide} title="Tutup Prakiraan Potensi Tanah Longsor" aria-label="Tutup Prakiraan Potensi Tanah Longsor">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
        </button>
      </header>
      <div class="al-bar" title="Potensi tanah longsor">{#each LANDSLIDE_LEVELS as lvl}<i style="background:{lvl.color}" title={lvl.label}></i>{/each}</div>
      <div class="al-scale">{#each LANDSLIDE_LEVELS as lvl}<span>{lvl.label}</span>{/each}</div>
      {#if landslideData.inarisk}
        {@const low = landslideData.vulnerabilityLowMax ?? 0.333}
        {@const med = landslideData.vulnerabilityMediumMax ?? 0.666}
        <div class="al-sub-label">Kerentanan longsor</div>
        <div class="al-bar" title="Indeks kerentanan longsor">{#each LANDSLIDE_LEVELS as lvl}<i style="background:{lvl.color}" title={lvl.label}></i>{/each}</div>
        <div class="al-scale"><span>0</span><span>{low}</span><span>{med}</span><span>1</span></div>
      {/if}
    </section>
  {/if}
{/snippet}

{#snippet floodRow()}
  {#if floodData}
    <section class="al-row">
      <header class="al-head">
        <div class="al-meta">
          <span class="al-name">Potensi Banjir</span>
          <span class="al-sub">
            {#if floodData.runTime}Run {formatWibShort(floodData.runTime)}{/if}
            {#if floodData.validTime}<span class="al-dot">·</span> Valid {formatWibShort(floodData.validTime)}{/if}
          </span>
        </div>
        <button type="button" class="al-x" class:on={floodData.inarisk} onclick={() => onToggleInarisk?.()}
          title={floodData.inarisk ? 'Sembunyikan kerentanan banjir InaRISK' : 'Tampilkan kerentanan banjir InaRISK'}
          aria-label="Kerentanan banjir InaRISK" aria-pressed={floodData.inarisk ? 'true' : 'false'}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 20h18L12 4z" /></svg>
        </button>
        <div class="al-op">
          <button type="button" class="al-x" title="Opasitas" aria-label="Opasitas lapisan {Math.round((floodData.opacity ?? 0.6) * 100)} persen">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" /></svg>
          </button>
          <div class="al-op-pop">
            <div class="al-op-label"><span>Opasitas</span><span>{Math.round((floodData.opacity ?? 0.6) * 100)}%</span></div>
            <input type="range" min="0" max="1" step="0.05" value={floodData.opacity ?? 0.6}
              oninput={(e) => onChangeFloodOpacity?.(parseFloat(e.currentTarget.value))} aria-label="Opasitas lapisan" />
          </div>
        </div>
        {#if hazardOrder && hazardOrder.length > 1}
          <div class="al-order">
            <button type="button" class="al-x" disabled={hazardOrder.indexOf('flood') === hazardOrder.length - 1} onclick={() => onMoveHazard?.('flood', 1)} title="Naikkan lapisan" aria-label="Naikkan lapisan banjir">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 14l6-6 6 6" /></svg>
            </button>
            <button type="button" class="al-x" disabled={hazardOrder.indexOf('flood') === 0} onclick={() => onMoveHazard?.('flood', -1)} title="Turunkan lapisan" aria-label="Turunkan lapisan banjir">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 10l6 6 6-6" /></svg>
            </button>
          </div>
        {/if}
        <button type="button" class="al-x" onclick={onCloseFlood} title="Tutup Potensi Banjir" aria-label="Tutup Potensi Banjir">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
        </button>
      </header>
      <div class="al-bar" style="background:{FLOOD_RAMP}" title="Hujan 24 jam ke depan"></div>
      <div class="al-scale"><span>0 mm</span><span>24 jam</span><span>≥200 mm</span></div>
      {#if floodData.inarisk}
        <div class="al-scale"><span>InaRISK</span><span>Kerentanan</span><span>BNPB</span></div>
      {/if}
    </section>
  {/if}
{/snippet}

{#if radarData || satelliteData || nwpData || spartanData || landslideData || floodData}
  <div class="al" role="region" aria-label="Lapisan aktif">
    {#each [...activeOrder].reverse() as kind (kind)}
    {#if kind === 'landslide'}
      {@render landslideRow()}
    {:else if kind === 'flood'}
      {@render floodRow()}
    {:else if kind === 'radar' && radarData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">Radar {radarData.site.label}</span>
          </div>
          {@render orderButtons('radar', 'radar')}
          <button type="button" class="al-x" onclick={onCloseRadar} title="Tutup radar" aria-label="Tutup radar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        <div class="al-bar" title="Reflektivitas dBZ">
          {#each RADAR_LEVELS as lvl}
            <i style="background:{lvl.color}"></i>
          {/each}
        </div>
        <div class="al-scale"><span>5</span><span>dBZ</span><span>70</span></div>
      </section>
    {:else if kind === 'satellite' && satelliteData}
      {@const satLegend = satelliteLegend(satelliteData.product)}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">{satelliteData.product.label}</span>
            <span class="al-sub">{formatWibShort(satelliteData.currentBaserun)} WIB</span>
          </div>
          {@render orderButtons('satellite', 'satelit')}
          <button type="button" class="al-x" onclick={onCloseSatellite} title="Tutup satelit" aria-label="Tutup satelit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        {#if satLegend}
          <div class="al-bar" title={satLegend.label}>{#each satLegend.stops as stop}<i style:background={stop.color} title={String(stop.value)}></i>{/each}</div>
          <div class="al-scale"><span>{satLegend.stops[0].value}</span><span>{satLegend.label}</span><span>{satLegend.stops.at(-1).value}</span></div>
        {:else}
          <div class="al-sub-label">Legenda rentang belum tersedia dari sumber BMKG.</div>
        {/if}
      </section>
    {:else if kind === 'spartan' && spartanData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">KARHUTLA {spartanData.product.code}</span>
            <span class="al-sub">Run {spartanDateLabel(spartanData.startDate)} · Berlaku {spartanDateLabel(spartanData.endDate)}</span>
          </div>
          {@render orderButtons('spartan', 'KARHUTLA')}
          <button type="button" class="al-x" onclick={onCloseSpartan} title="Hapus KARHUTLA {spartanData.product.code}" aria-label="Hapus KARHUTLA {spartanData.product.code}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        <div class="al-bar" title="Bahaya Kebakaran">
          {#each SPARTAN_CLASSES as cls}
            <i style="background:{cls.color}" title={cls.label}></i>
          {/each}
        </div>
        <div class="al-scale">{#each SPARTAN_CLASSES as cls}<span>{cls.label}</span>{/each}</div>
      </section>
    {:else if kind === 'nwp' && nwpData}
      {@const legend = nwpLegend()}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">{nwpData.title}</span>
            <span class="al-sub">
              {#if nwpData.runTime}Run {formatWibShort(nwpData.runTime)}{/if}
              {#if nwpData.validTime}<span class="al-dot">·</span> Valid {formatWibShort(nwpData.validTime)}{/if}
            </span>
          </div>
          {@render orderButtons('nwp', nwpData.title)}
          <button type="button" class="al-x" onclick={onCloseNwp} title="Tutup {nwpData.title}" aria-label="Tutup {nwpData.title}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        {#if legend}
          <div class="al-bar" style="background:{legendCss(nwpData.modelId, nwpData.varId)}"></div>
          <div class="al-scale">
            <span>{legend.min}{legend.units ? ` ${legend.units}` : ''}</span>
            <span>{legend.label}</span>
            <span>{legend.max}{legend.units ? ` ${legend.units}` : ''}</span>
          </div>
        {/if}
      </section>
    {/if}
    {/each}
  </div>
{/if}

<style>
  .al {
    width: 252px;
    padding: 6px;
    border-radius: 12px;
    background: rgba(14, 16, 20, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.13);
    backdrop-filter: blur(18px) saturate(1.2);
    -webkit-backdrop-filter: blur(18px) saturate(1.2);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.32);
    color: #f4f4f5;
  }
  .al-row + .al-row {
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .al-head {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }
  .al-meta {
    flex: 1;
    min-width: 0;
  }
  .al-name {
    display: block;
    font-size: 12px;
    font-weight: 560;
    letter-spacing: -0.01em;
    line-height: 1.25;
    color: #fafafa;
  }
  .al-sub {
    display: block;
    margin-top: 2px;
    font-size: 10px;
    line-height: 1.35;
    color: rgba(244, 244, 245, 0.58);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .al-dot {
    margin: 0 0.3em;
    opacity: 0.55;
  }
  .al-x.on {
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.16);
  }
  .al-x {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    margin-top: -1px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: rgba(244, 244, 245, 0.45);
    display: grid;
    place-items: center;
    cursor: pointer;
  }
  .al-x:hover {
    color: #fafafa;
    background: rgba(255, 255, 255, 0.08);
  }
  .al-x svg {
    width: 12px;
    height: 12px;
  }
  .al-order {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  .al-order .al-x {
    width: 16px;
    height: 12px;
    margin-top: 0;
  }
  .al-order .al-x:disabled {
    opacity: 0.25;
    cursor: default;
  }
  .al-op {
    position: relative;
    flex-shrink: 0;
  }
  .al-op-pop {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 168px;
    padding: 8px 10px;
    border-radius: 10px;
    background: rgba(14, 16, 20, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.13);
    backdrop-filter: blur(18px);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s;
    z-index: 2;
  }
  .al-op:hover .al-op-pop,
  .al-op:focus-within .al-op-pop {
    opacity: 1;
    pointer-events: auto;
  }
  .al-op-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 10px;
    color: rgba(244, 244, 245, 0.7);
    font-variant-numeric: tabular-nums;
  }
  .al-op-pop input {
    width: 100%;
    accent-color: #2563eb;
    cursor: pointer;
  }
  .al-bar {
    display: flex;
    height: 4px;
    margin-top: 8px;
    overflow: hidden;
    border-radius: 999px;
  }
  .al-bar i {
    flex: 1;
    display: block;
  }
  .al-sub-label {
    margin-top: 8px;
    font-size: 9px;
    letter-spacing: 0.01em;
    color: rgba(244, 244, 245, 0.55);
  }
  .al-scale {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 9px;
    color: rgba(244, 244, 245, 0.45);
    font-variant-numeric: tabular-nums;
  }
</style>
