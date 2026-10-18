<script>
  import { legendCss, legendFor } from '../services/nwp.js';
  import { formatWibShort } from '../services/numericTiles.js';
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
    onChangeSatelliteBaserun,
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

{#if radarData || satelliteData || nwpData || spartanData}
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
            <span class="al-sub">{satelliteData.currentBaserun}</span>
          </div>
          <button type="button" class="al-x" onclick={onCloseSatellite} title="Tutup satelit" aria-label="Tutup satelit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </header>
        {#if satelliteData.baseruns?.length}
          <div class="al-frames">
            {#each satelliteData.baseruns.slice(0, 6) as br}
              <button
                type="button"
                class="al-frame"
                class:on={satelliteData.currentBaserun === br}
                onclick={() => onChangeSatelliteBaserun(br)}
              >
                {satTime(br)}
              </button>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    {#if spartanData}
      <section class="al-row">
        <header class="al-head">
          <div class="al-meta">
            <span class="al-name">SPARTAN {spartanData.product.code}</span>
            <span class="al-sub">{spartanRangeLabel(spartanData.startDate, spartanData.endDate)}</span>
          </div>
          <button type="button" class="al-x" onclick={onCloseSpartan} aria-label="Tutup SPARTAN">×</button>
        </header>
        <div class="al-bar" title="Bahaya Kebakaran">
          {#each SPARTAN_CLASSES as cls}
            <i style="background:{cls.color}" title={cls.label}></i>
          {/each}
        </div>
        <div class="al-scale"><span>Rendah</span><span>Bahaya Kebakaran</span><span>Ekstrem</span></div>
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
  .al-frames {
    display: flex;
    gap: 4px;
    margin-top: 8px;
    overflow-x: auto;
  }
  .al-frame {
    flex: 1;
    min-width: 0;
    padding: 3px 0;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    background: transparent;
    color: rgba(244, 244, 245, 0.7);
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    cursor: pointer;
  }
  .al-frame:hover {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.22);
  }
  .al-frame.on {
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.22);
  }
</style>
