<script>
  let { data, loading = false, error = null } = $props();

  function locLine(loc) {
    if (!loc) return '';
    const parts = [loc.kecamatan, loc.kabupaten_kota, loc.provinsi].filter(
      (p) => p && p !== '–' && p !== '-'
    );
    return parts.join(', ') || loc.display_name || '';
  }
</script>

<div class="nwp-pop">
  {#if error}
    <div class="nwp-pop-err">{error}</div>
  {:else if data}
    <div class="nwp-pop-kicker">{data.modelTitle || 'NWP'}</div>
    <div class="nwp-pop-title">{locLine(data.lokasi) || 'Titik peta'}</div>
    <div class="nwp-pop-meta">
      {data.lat?.toFixed(4)}, {data.lon?.toFixed(4)}
    </div>
    {#if data.tanggal}
      <div class="nwp-pop-meta">{data.tanggal}</div>
    {/if}
    {#if data.runTime}
      <div class="nwp-pop-meta">Run {data.runTime} · valid {data.validTime}</div>
    {/if}
    {#if loading && !Object.keys(data.nilai || {}).length}
      <div class="nwp-pop-muted">Membaca nilai…</div>
    {:else}
      <dl class="nwp-pop-vals">
        {#each Object.values(data.nilai || {}) as row}
          <div class="nwp-pop-row" class:active={row.id === data.varId}>
            <dt>{row.name}</dt>
            <dd>{row.display}</dd>
          </div>
        {/each}
      </dl>
    {/if}
  {:else if loading}
    <div class="nwp-pop-muted">Membaca nilai…</div>
  {/if}
</div>

<style>
  .nwp-pop {
    min-width: 220px;
    max-width: 280px;
    padding-right: 14px;
    font-family: Inter, system-ui, sans-serif;
  }
  .nwp-pop-kicker {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #0369a1;
    margin-bottom: 2px;
  }
  .nwp-pop-title {
    font-size: 13px;
    font-weight: 650;
    color: #0f172a;
    line-height: 1.3;
  }
  .nwp-pop-meta {
    font-size: 11px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: #64748b;
    margin-top: 2px;
  }
  .nwp-pop-vals {
    margin: 8px 0 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .nwp-pop-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 12px;
  }
  .nwp-pop-row dt {
    color: #475569;
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
  .nwp-pop-muted,
  .nwp-pop-err {
    font-size: 12px;
    color: #64748b;
  }
  .nwp-pop-err {
    color: #be123c;
  }
</style>
