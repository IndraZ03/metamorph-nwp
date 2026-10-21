<script>
  let { rows = [], selected = null, onchange, runTime = '', notice = '' } = $props();
  const format = (time) => time ? new Date(time).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', dateStyle: 'medium', timeStyle: 'short' }) + ' WIB' : '—';
</script>

{#if rows.length}
  <section class="forecast-control" aria-label="Timeline prakiraan bersama">
    <div>Run: {format(runTime)}</div>
    {#if notice}<div role="status">{notice}</div>{/if}
    <label for="forecast-step">Waktu prakiraan {selected !== null ? `+${selected} jam` : ''}</label>
    <select id="forecast-step" value={selected ?? ''} onchange={(event) => onchange(Number(event.target.value))}>
      {#each rows as row}
        <option value={row.step}>+{row.step} jam · {format(row.validTime || row.forecast_start)}{row.ready === false ? ' · Tidak tersedia' : ''}</option>
      {/each}
    </select>
  </section>
{/if}

<style>
  .forecast-control { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 42; width: min(420px, calc(100vw - 32px)); padding: 12px; border: 1px solid #ffffff30; border-radius: 14px; background: #0f172ae8; color: white; font-size: 11px; backdrop-filter: blur(14px); }
  label { display: block; margin: 5px 0; font-weight: 600; }
  select { width: 100%; background: #1e293b; color: white; border: 1px solid #64748b; border-radius: 6px; padding: 7px; }
  @media (max-width: 700px) { .forecast-control { bottom: 8px; } }
</style>
