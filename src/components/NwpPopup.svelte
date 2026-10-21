<script>
  import {
    Cloud,
    CloudRain,
    Droplet,
    Droplets,
    Gauge,
    Thermometer,
    Wind,
    Zap,
  } from 'lucide-svelte';
  import { formatWibShort } from '../services/numericTiles.js';
  import { inspectPop } from '../services/inspectPop.svelte.js';

  let { onMeteogram } = $props();
  let data = $derived(inspectPop.data);
  let loading = $derived(inspectPop.loading);
  let error = $derived(inspectPop.error);

  const ICONS = {
    t2m: Thermometer,
    temperature: Thermometer,
    t_2m: Thermometer,
    d2m: Droplet,
    dew_point: Droplet,
    td_2m: Droplet,
    wind10m: Wind,
    wind: Wind,
    wind_10m: Wind,
    rh: Droplets,
    relhum_2m: Droplets,
    tp: CloudRain,
    rain: CloudRain,
    tot_prec: CloudRain,
    msl: Gauge,
    pressure: Gauge,
    pmsl: Gauge,
    cape: Zap,
    cape_ml: Zap,
    tcc: Cloud,
    clouds: Cloud,
    clct: Cloud,
  };

  function locLine(loc) {
    if (!loc) return '';
    const parts = [loc.kecamatan, loc.kabupaten_kota, loc.provinsi].filter(
      (p) => p && p !== '–' && p !== '-'
    );
    return parts.join(', ') || loc.display_name || '';
  }

  function iconFor(id) {
    return ICONS[id] || Thermometer;
  }
</script>

<div class="nwp-pop">
  {#if error}
    <div class="nwp-pop-err">{error}</div>
  {:else if data}
    <div class="nwp-pop-head">
      <span class="nwp-pop-kicker">{data.modelTitle || 'NWP'}</span>
      <span class="nwp-pop-title">{locLine(data.lokasi) || 'Titik peta'}</span>
      <span class="nwp-pop-coord">{data.lat?.toFixed(3)}, {data.lon?.toFixed(3)}</span>
    </div>
    {#if data.runTime || data.validTime}
      <div class="nwp-pop-times">
        <span><em>Run</em> {formatWibShort(data.runTime)}</span>
        <span><em>Valid</em> {formatWibShort(data.validTime)}</span>
      </div>
    {/if}
    {#if loading && !Object.keys(data.nilai || {}).length}
      <div class="nwp-pop-muted">Membaca nilai…</div>
    {:else}
      <dl class="nwp-pop-vals">
        {#each Object.values(data.nilai || {}) as row (row.id)}
          {@const Icon = iconFor(row.id)}
          <div class="nwp-pop-row" class:active={row.id === data.varId} title={row.name}>
            <dt>
              <Icon size={13} strokeWidth={2.2} />
              <span>{row.short || row.name}</span>
            </dt>
            <dd>{row.display}</dd>
          </div>
        {/each}
      </dl>
    {/if}
    {#if onMeteogram}
      <button class="nwp-pop-meteogram" type="button" onclick={() => onMeteogram(data)}>
        Meteogram
      </button>
    {/if}
  {:else if loading}
    <div class="nwp-pop-muted">Membaca nilai…</div>
  {/if}
</div>

<style>
  .nwp-pop {
    min-width: 196px;
    max-width: 228px;
    padding-right: 10px;
    font-family: Inter, system-ui, sans-serif;
  }
  .nwp-pop-head {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding-right: 8px;
  }
  .nwp-pop-kicker {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #0369a1;
  }
  .nwp-pop-title {
    font-size: 12px;
    font-weight: 650;
    color: #0f172a;
    line-height: 1.25;
  }
  .nwp-pop-coord {
    font-size: 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: #94a3b8;
  }
  .nwp-pop-times {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    margin-top: 6px;
    padding: 4px 6px;
    border-radius: 7px;
    background: #f1f5f9;
    font-size: 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: #0f172a;
    line-height: 1.25;
  }
  .nwp-pop-times em {
    display: block;
    font-style: normal;
    font-family: Inter, system-ui, sans-serif;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748b;
  }
  .nwp-pop-vals {
    margin: 7px 0 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nwp-pop-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    line-height: 1;
    padding: 2px 0;
  }
  .nwp-pop-row dt {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: #475569;
    font-weight: 600;
  }
  .nwp-pop-row dt :global(svg) {
    flex-shrink: 0;
    color: #64748b;
  }
  .nwp-pop-row dd {
    margin: 0;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-weight: 600;
    color: #0f172a;
    white-space: nowrap;
  }
  .nwp-pop-row.active dt,
  .nwp-pop-row.active dd {
    color: #0369a1;
  }
  .nwp-pop-row.active dt :global(svg) {
    color: #0369a1;
  }
  .nwp-pop-muted,
  .nwp-pop-err {
    font-size: 12px;
    color: #64748b;
    margin-top: 6px;
  }
  .nwp-pop-err {
    color: #be123c;
  }
  .nwp-pop-meteogram {
    display: block;
    width: 100%;
    margin-top: 9px;
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    background: #f1f5f9;
    color: #0f172a;
    font-size: 11px;
    font-weight: 650;
    cursor: pointer;
  }
  .nwp-pop-meteogram:hover { background: #e2e8f0; }
  .nwp-pop-meteogram:focus-visible { outline: 2px solid #0369a1; outline-offset: 2px; }
</style>
