<script>
  import { legendCss, legendFor } from '../services/nwp.js';
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
    onCloseFlood,
    onChangeFloodOpacity,
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
</script>

{#if radarData || satelliteData || nwpData || spartanData || landslideData || floodData}
  <div class="al" role="region" aria-label="Lapisan aktif">
    {#if radarData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">Radar {radarData.site.label}</span>
            <span class="al-sub">{radarData.currentFile || radarData.manifest?.latest?.file || 'CMAX'}</span>
          </div>
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
    {/if}

    {#if satelliteData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">{satelliteData.product.label}</span>
            <span class="al-sub">{formatWibShort(satelliteData.currentBaserun)} WIB</span>
          </div>
          <button type="button" class="al-x" onclick={onCloseSatellite} title="Tutup satelit" aria-label="Tutup satelit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
  
      </section>
    {/if}

    {#if spartanData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">KARHUTLA {spartanData.product.code}</span>
            <span class="al-sub">Run {spartanDateLabel(spartanData.startDate)} · Berlaku {spartanDateLabel(spartanData.endDate)}</span>
          </div>
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
    {/if}

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
          <div class="al-op">
            <button
              type="button"
              class="al-x"
              aria-label="Opasitas lapisan {Math.round((landslideData.opacity ?? 0.6) * 100)} persen"
              title="Opasitas"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" />
              </svg>
            </button>
            <div class="al-op-pop">
              <div class="al-op-label">
                <span>Opasitas</span>
                <span>{Math.round((landslideData.opacity ?? 0.6) * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.05"
                value={landslideData.opacity ?? 0.6}
                oninput={(e) => onChangeLandslideOpacity?.(parseFloat(e.currentTarget.value))}
                aria-label="Opasitas lapisan"
              />
            </div>
          </div>
          <button type="button" class="al-x" onclick={onCloseLandslide} title="Tutup Prakiraan Potensi Tanah Longsor" aria-label="Tutup Prakiraan Potensi Tanah Longsor">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        <div class="al-bar" title="Potensi tanah longsor">
          {#each LANDSLIDE_LEVELS as lvl}
            <i style="background:{lvl.color}" title={lvl.label}></i>
          {/each}
        </div>
        <div class="al-scale">{#each LANDSLIDE_LEVELS as lvl}<span>{lvl.label}</span>{/each}</div>
      </section>
    {/if}

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
          <div class="al-op">
            <button
              type="button"
              class="al-x"
              aria-label="Opasitas lapisan {Math.round((floodData.opacity ?? 0.6) * 100)} persen"
              title="Opasitas"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" />
              </svg>
            </button>
            <div class="al-op-pop">
              <div class="al-op-label">
                <span>Opasitas</span>
                <span>{Math.round((floodData.opacity ?? 0.6) * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.05"
                value={floodData.opacity ?? 0.6}
                oninput={(e) => onChangeFloodOpacity?.(parseFloat(e.currentTarget.value))}
                aria-label="Opasitas lapisan"
              />
            </div>
          </div>
          <button type="button" class="al-x" onclick={onCloseFlood} title="Tutup Potensi Banjir" aria-label="Tutup Potensi Banjir">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        <div class="al-bar" style="background:{FLOOD_RAMP}" title="Hujan 24 jam ke depan"></div>
        <div class="al-scale"><span>0 mm</span><span>24 jam</span><span>≥200 mm</span></div>
      </section>
    {/if}

    {#if nwpData}
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
  .al-scale {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 9px;
    color: rgba(244, 244, 245, 0.45);
    font-variant-numeric: tabular-nums;
  }
</style>
