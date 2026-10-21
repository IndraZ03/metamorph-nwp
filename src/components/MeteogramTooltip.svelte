<script>
  import { formatWib } from '../services/numericTiles.js';
  let { point = null, modelTitle = '' } = $props();
  const fields = [ ['Suhu', 'temperatureC', '°C'], ['Titik embun', 'dewPointC', '°C'], ['Hujan', 'precipitationMm', 'mm'], ['Angin', 'windSpeedMs', 'm/s'], ['Arah FROM', 'windDirectionDeg', '°'], ['Awan', 'totalCloudCoverPct', '%'], ['Kelembapan', 'relativeHumidityPct', '%'], ['Tekanan', 'pressureHpa', 'hPa'], ['CAPE', 'capeJkg', 'J/kg'], ['VMAX (interval belum diketahui)', 'maximumWindMs', 'm/s'] ];
</script>
{#if point}
  <div class="readout" aria-live="polite">
    <strong>{formatWib(point.validTime)}</strong> <span>{modelTitle}</span>
    <dl>{#each fields as [label, key, unit]}<div><dt>{label}</dt><dd>{Number.isFinite(point[key]) ? `${point[key].toFixed(1)} ${unit}` : 'Tidak tersedia'}</dd></div>{/each}</dl>
    <p>Hujan: {point.precipitationStartTime ? `${formatWib(point.precipitationStartTime)} – ${formatWib(point.validTime)} (${point.precipitationIntervalHours} jam)` : 'Interval tidak tersedia'}</p>
    <p>Kondisi tidak tersedia</p>
  </div>
{/if}
<style>
  .readout { font-size:11px; color:var(--mg-text); padding:8px 16px; border-top:1px solid var(--mg-border); font-variant-numeric:tabular-nums; }
  span,dt,p { color:var(--mg-muted); } dl { display:flex; flex-wrap:wrap; gap:8px 20px; margin:8px 0; } dl div { display:flex; gap:8px; } dd { margin:0; } p { margin:4px 0; }
</style>
