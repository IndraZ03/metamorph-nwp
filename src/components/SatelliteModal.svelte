<script>
  import { onMount, onDestroy } from 'svelte';
  import Modal from './Modal.svelte';
  import { fetchSatelliteCatalog, findLatestValidBaserun } from '../services/bmkg.js';

  let { currentProduct, currentOpacity = 1.0, onSelect, onClose } = $props();

  let alive = true;
  let request = new AbortController();
  onDestroy(() => { alive = false; request.abort(); });

  let loading = $state(true);
  let verifying = $state(false);
  let error = $state(null);
  let sources = $state([]);
  let selectedId = $state(currentProduct?.id || 'himawari9-ir');
  let opacity = $state(currentOpacity);

  let selectedSource = $derived(sources.find((s) => s.id === selectedId));

  function channelLabel(src) {
    if (src.param === 'VS') return 'Himawari-9 Vis';
    if (src.param === 'EH') return 'Himawari-9 EH';
    return src.label || src.param;
  }

  onMount(async () => {
    try {
      loading = true;
      const cat = await fetchSatelliteCatalog();
      if (alive) sources = cat.sources || [];
    } catch (e) {
      if (alive && !request.signal.aborted) error = e.message;
    } finally {
      loading = false;
    }
  });

  async function handleApply() {
    if (!selectedSource) return;
    const controller = request;
    const product = selectedSource;
    try {
      verifying = true;
      const resolved = await findLatestValidBaserun(product, controller.signal);
      if (!alive || controller.signal.aborted || controller !== request) return;
      onSelect({
        product,
        baseruns: resolved.list,
        currentBaserun: resolved.current,
        opacity,
      });
      onClose();
    } catch (e) {
      if (alive && controller === request && !controller.signal.aborted) error = e.message;
    } finally {
      if (controller === request) verifying = false;
    }
  }

  function handleRemove() {
    onSelect(null);
    onClose();
  }
</script>

<Modal title="Satelit" {onClose}>
  {#if loading}
    <p class="hint">Memuat…</p>
  {:else if error}
    <p class="err">{error}</p>
  {:else}
    <p class="label">Kanal</p>
    <div class="picks">
      {#each sources as src}
        <button
          type="button"
          class="pick"
          class:on={selectedId === src.id}
          onclick={() => { request.abort(); request = new AbortController(); verifying = false; selectedId = src.id; }}
        >
          {channelLabel(src)}
        </button>
      {/each}
    </div>

    <label class="op">
      <span>Opasitas</span>
      <input type="range" min="0.2" max="1" step="0.05" bind:value={opacity} class="modern-slider" />
    </label>

    <div class="acts">
      {#if currentProduct}
        <button type="button" class="ghost rose" onclick={handleRemove}>Hapus</button>
      {/if}
      <button type="button" class="ghost" onclick={onClose}>Batal</button>
      <button type="button" class="go" disabled={verifying} onclick={handleApply}>
        {verifying ? '…' : 'Terapkan'}
      </button>
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
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .pick {
    width: 100%;
    padding: 10px 12px;
    text-align: left;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: transparent;
    color: rgba(244, 244, 245, 0.82);
    font-size: 13px;
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
  .go:disabled {
    opacity: 0.5;
  }
</style>
