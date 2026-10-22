<script>
  import { formatWib } from '../services/numericTiles.js';
  let { point = null, modelTitle = '', x = null } = $props();
  const fields = [ ['Suhu', 'temperatureC', '°C'], ['Titik embun', 'dewPointC', '°C'], ['Hujan', 'precipitationMm', 'mm'], ['Angin', 'windSpeedMs', 'm/s'], ['Arah FROM', 'windDirectionDeg', '°'], ['Awan', 'totalCloudCoverPct', '%'], ['Kelembapan', 'relativeHumidityPct', '%'], ['Tekanan', 'pressureHpa', 'hPa'], ['CAPE', 'capeJkg', 'J/kg'] ];
</script>

{#if point}
  <div class="tip" style:left={`${Number.isFinite(x) ? x : 0}px`}>
    <strong>{formatWib(point.validTime)} WIB</strong> <span>{modelTitle}</span>
    <p>{point.weatherCondition?.label || 'Kondisi tidak tersedia'}</p>
    <dl>{#each fields as [label, key, unit]}<div><dt>{label}</dt><dd>{Number.isFinite(point[key]) ? `${point[key].toFixed(1)} ${unit}` : '–'}</dd></div>{/each}</dl>
  </div>
{/if}

<style>
  .tip { position: absolute; top: 56px; z-index: 2; transform: translateX(12px); max-width: 240px; padding: 6px 8px;
    background: #1c232b; border: 1px solid var(--mg-border); border-radius: 4px; font-size: 11px;
    color: var(--mg-text); pointer-events: none; font-variant-numeric: tabular-nums; }
  span, dt, p { color: var(--mg-muted); } p { margin: 2px 0; }
  dl { display: flex; flex-wrap: wrap; gap: 2px 10px; margin: 4px 0 0; } dl div { display: flex; gap: 4px; } dd { margin: 0; }
</style>
