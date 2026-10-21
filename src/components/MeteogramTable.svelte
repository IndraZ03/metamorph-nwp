<script>
  import { formatWib } from '../services/numericTiles.js';
  let { points = [], onSelectTime } = $props();
  const fields = [['Suhu °C','temperatureC'],['Titik embun °C','dewPointC'],['Hujan mm','precipitationMm'],['Angin m/s','windSpeedMs'],['FROM °','windDirectionDeg'],['RH %','relativeHumidityPct'],['Tekanan hPa','pressureHpa'],['Awan %','totalCloudCoverPct'],['CAPE J/kg','capeJkg'],['VMAX m/s','maximumWindMs']];
</script>
<div class="table-wrap" role="region" aria-label="Tabel meteogram, geser horizontal untuk parameter lain">
  <table><caption>Prakiraan model, bukan observasi. VMAX: interval sumber belum diketahui. Kondisi tidak tersedia.</caption><thead><tr><th>Waktu WIB</th>{#each fields as [label]}<th>{label}</th>{/each}<th>Interval hujan WIB</th></tr></thead>
    <tbody>{#each points as p}<tr><th><button type="button" onclick={() => onSelectTime?.(p.t)}>{formatWib(p.validTime)}</button></th>{#each fields as [, key]}<td>{Number.isFinite(p[key]) ? p[key].toFixed(1) : 'Tidak tersedia'}</td>{/each}<td>{p.precipitationStartTime ? `${formatWib(p.precipitationStartTime)} – ${formatWib(p.validTime)} (${p.precipitationIntervalHours} jam)` : 'Tidak tersedia'}</td></tr>{/each}</tbody>
  </table>
</div>
<style>
  .table-wrap { overflow:auto; max-height:300px; margin:8px 16px; font-size:11px; } table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; } th,td { padding:8px; border-bottom:1px solid var(--mg-border); text-align:right; white-space:nowrap; } th:first-child { text-align:left; } caption { text-align:left; color:var(--mg-muted); padding:8px; } button { color:inherit; text-decoration:underline; } button:focus-visible { outline:2px solid var(--mg-text); }
</style>
