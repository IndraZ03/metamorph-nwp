<script>
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import { fetchRadarCatalog, fetchRadarManifest } from '../services/bmkg.js';

  let { currentStation, currentOpacity = 0.8, onSelect, onClose } = $props();

  let loading = $state(true);
  let error = $state(null);
  let catalog = $state(null);
  let sites = $state([]);
  let selectedCode = $state(currentStation?.code || 'BAL');
  let opacity = $state(currentOpacity);

  let selectedSite = $derived(sites.find((s) => s.code === selectedCode));

  onMount(async () => {
    try {
      loading = true;
      catalog = await fetchRadarCatalog();
      sites = (catalog.sites || []).filter((s) => s.bounds && s.bounds.overlayTLC);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  async function handleApply() {
    if (!selectedSite) return;
    try {
      loading = true;
      const manifest = await fetchRadarManifest(selectedSite.code, catalog?.product || 'CMAX', catalog?.base);
      onSelect({
        site: selectedSite,
        product: catalog?.product || 'CMAX',
        base: catalog?.base,
        legends: catalog?.legends,
        manifest,
        opacity,
      });
      onClose();
    } catch (e) {
      error = e.message;
      loading = false;
    }
  }

  function handleRemove() {
    onSelect(null);
    onClose();
  }
</script>

<Modal title="Radar" {onClose}>
  {#if loading}
    <p class="hint">Memuat…</p>
  {:else if error}
    <p class="err">{error}</p>
  {:else}
    <p class="label">Situs</p>
    <div class="picks">
      {#each sites as site}
        <button
          type="button"
          class="pick"
          class:on={selectedCode === site.code}
          onclick={() => (selectedCode = site.code)}
        >
          <span>{site.label}</span>
          <span class="code">{site.code}</span>
        </button>
      {/each}
    </div>

    <label class="op">
      <span>Opasitas</span>
      <input type="range" min="0.2" max="1" step="0.05" bind:value={opacity} class="modern-slider" />
    </label>

    <div class="acts">
      {#if currentStation}
        <button type="button" class="ghost rose" onclick={handleRemove}>Hapus</button>
      {/if}
      <button type="button" class="ghost" onclick={onClose}>Batal</button>
      <button type="button" class="go" onclick={handleApply}>Terapkan</button>
    </div>
  {/if}
</Modal>

<style>
  .hint,
  .err {
    margin: 8px 0 0;
    font-size: 12px;
    color: rgba(244, 244, 245, 0.55);
  }
  .err {
    color: #fb7185;
  }
  .label {
    margin: 0 0 8px;
    font-size: 11px;
    color: rgba(244, 244, 245, 0.5);
  }
  .picks {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    max-height: 240px;
    overflow-y: auto;
  }
  .pick {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    padding: 8px 10px;
    text-align: left;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: transparent;
    color: rgba(244, 244, 245, 0.82);
    font-size: 12px;
    font-weight: 520;
    letter-spacing: -0.01em;
    cursor: pointer;
  }
  .pick:hover {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.2);
  }
  .pick.on {
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.22);
  }
  .code {
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    color: rgba(244, 244, 245, 0.45);
  }
  .pick.on .code {
    color: rgba(244, 244, 245, 0.7);
  }
  .op {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    font-size: 11px;
    color: rgba(244, 244, 245, 0.5);
  }
  .op input {
    flex: 1;
  }
  .acts {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 16px;
  }
  .ghost,
  .go {
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
  }
  .ghost {
    border: 0;
    background: transparent;
    color: rgba(244, 244, 245, 0.6);
  }
  .ghost:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.08);
  }
  .ghost.rose {
    color: #fb7185;
    margin-right: auto;
  }
  .go {
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
  }
  .go:hover {
    background: rgba(255, 255, 255, 0.18);
  }
</style>
