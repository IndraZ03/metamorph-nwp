<script>
  import Modal from './Modal.svelte';
  import LayerControl from './LayerControl.svelte';
  import { parseUserFile, USER_LAYER_COLORS } from '../services/userLayers.js';

  let {
    layers = [],
    drawGroups = [],
    onAdd,
    onToggle,
    onFit,
    onRemove,
    onClearAll,
    onRename,
    onToggleDraw,
    radarData = null,
    satelliteData = null,
    nwpData = null,
    spartanData = null,
    onCloseRadar,
    onCloseSatellite,
    onCloseNwp,
    onCloseSpartan,
  } = $props();

  let showPanel = $state(false);
  let nameInput = $state('');
  let colorInput = $state('auto');
  let pasteText = $state('');
  let error = $state('');
  let dragOver = $state(false);
  let fileInput = $state(null);
  let renamingId = $state(null);
  let renameText = $state('');

  function startRename(layer) {
    renamingId = layer.id;
    renameText = layer.name;
  }

  function saveRename() {
    const name = renameText.trim().slice(0, 80);
    if (name && renamingId) onRename?.(renamingId, name);
    renamingId = null;
  }

  function cancelRename() {
    renamingId = null;
  }

  function baseName(fileName) {
    return fileName.replace(/\.(geojson|json|gpx|xml)$/i, '') || 'Overlay';
  }

  function addParsed(parsed, fallbackName) {
    const name = (nameInput.trim() || fallbackName || 'Overlay').slice(0, 80);
    const color = colorInput === 'auto' ? null : colorInput;
    const ok = onAdd?.({ name, kind: parsed.kind, geojson: parsed.geojson, color });
    if (ok === false) {
      error = 'Gagal menambah.';
      return;
    }
    error = '';
    nameInput = '';
    pasteText = '';
  }

  async function handleFiles(fileList) {
    for (const file of [...fileList]) {
      try {
        const text = await file.text();
        const parsed = parseUserFile(text, file.name);
        addParsed(parsed, baseName(file.name));
      } catch (e) {
        error = e.message;
      }
    }
  }

  function handlePaste() {
    if (!pasteText.trim()) {
      error = 'Tempel dulu.';
      return;
    }
    try {
      const parsed = parseUserFile(pasteText);
      addParsed(parsed, 'Overlay');
    } catch (e) {
      error = e.message;
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
  }
</script>

<div class="fixed right-5 top-5 z-40 flex items-start gap-2">
  <LayerControl
    {radarData}
    {satelliteData}
    {nwpData}
    {spartanData}
    {onCloseRadar}
    {onCloseSatellite}
    {onCloseNwp}
    {onCloseSpartan}
  />
  <div class="relative group shrink-0">
    <button
      type="button"
      onclick={() => (showPanel = true)}
      class="w-12 h-12 rounded-full flex items-center justify-center border backdrop-blur-md bg-white/10 hover:bg-white/20 text-white border-white/20 hover:border-white/35 cursor-pointer"
      aria-label="Overlay"
    >
      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3L2 8l10 5 10-5-10-5z" />
        <path d="M2 13l10 5 10-5" />
        <path d="M12 18v-6" />
        <path d="M18 6v6" />
      </svg>
      {#if layers.length > 0}
        <span class="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-white/90 text-slate-900 text-[10px] font-semibold flex items-center justify-center">
          {layers.length}
        </span>
      {/if}
    </button>
    <div
      class="absolute top-full right-0 mt-2 px-2.5 py-1 rounded-md bg-slate-900/85 backdrop-blur-md text-[11px] text-white/90 whitespace-nowrap border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100"
    >
      Overlay
    </div>
  </div>
</div>

{#if showPanel}
  <Modal title="Overlay" onClose={() => (showPanel = false)}>
    <button
      type="button"
      onclick={() => fileInput?.click()}
      ondragenter={(e) => {
        e.preventDefault();
        dragOver = true;
      }}
      ondragover={(e) => {
        e.preventDefault();
        dragOver = true;
      }}
      ondragleave={() => (dragOver = false)}
      ondrop={handleDrop}
      class="drop"
      class:over={dragOver}
    >
      GeoJSON / GPX
    </button>
    <input
      bind:this={fileInput}
      type="file"
      accept=".geojson,.json,.gpx,.xml"
      multiple
      class="hidden"
      onchange={(e) => {
        handleFiles(e.target.files);
        e.target.value = '';
      }}
    />

    <input type="text" bind:value={nameInput} placeholder="Nama" class="field" />

    <div class="swatches">
      <button type="button" class="auto" class:on={colorInput === 'auto'} onclick={() => (colorInput = 'auto')}>
        Auto
      </button>
      {#each USER_LAYER_COLORS as c}
        <button
          type="button"
          class="dot"
          class:on={colorInput === c}
          style="background:{c}"
          onclick={() => (colorInput = c)}
          aria-label={c}
        ></button>
      {/each}
    </div>

    <p class="label">Tempel</p>
    <textarea bind:value={pasteText} rows="3" placeholder="GeoJSON / GPX" class="field mono"></textarea>
    <button type="button" class="go full" onclick={handlePaste}>Tambah</button>

    {#if error}
      <p class="err">{error}</p>
    {/if}

    {#if drawGroups.length}
      <div class="list-head">
        <span>User Drawings</span>
      </div>
      {#each drawGroups as group (group.id)}
        <div class="row">
          <span class="chip" style="background:#38bdf8"></span>
          <span class="name">{group.name}</span>
          <span class="meta">{group.features?.length || 0}</span>
          <button
            type="button"
            class="ico"
            onclick={() => onToggleDraw?.(group.id)}
            aria-label={group.visible ? 'Sembunyikan drawing' : 'Tampilkan drawing'}
          >
            {#if group.visible}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3l18 18" /><path d="M10.6 5.1A10.6 10.6 0 0 1 22 12c-1.5 2.9-4.4 5.3-7.8 6.3" /></svg>
            {/if}
          </button>
        </div>
      {/each}
    {/if}

    {#if layers.length}
      <div class="list-head">
        <span>Lapisan</span>
        <button type="button" class="ghost rose" onclick={onClearAll}>Hapus semua</button>
      </div>
      {#each layers as layer (layer.id)}
        <div class="row">
          <span class="chip" style="background:{layer.color}"></span>
          {#if renamingId === layer.id}
            <input
              type="text"
              bind:value={renameText}
              autofocus
              maxlength="80"
              class="field grow"
              onkeydown={(e) => {
                if (e.key === 'Enter') saveRename();
                if (e.key === 'Escape') cancelRename();
              }}
            />
            <button type="button" class="ico" onclick={saveRename} aria-label="Simpan">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5" /></svg>
            </button>
            <button type="button" class="ico" onclick={cancelRename} aria-label="Batal">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          {:else}
            <span class="name">{layer.name}</span>
            <button type="button" class="ico" onclick={() => startRename(layer)} aria-label="Ganti nama">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
            </button>
            <button
              type="button"
              class="ico"
              onclick={() => onToggle?.(layer.id)}
              aria-label={layer.visible ? 'Sembunyikan' : 'Tampilkan'}
            >
              {#if layer.visible}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
              {:else}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3l18 18" /><path d="M10.6 5.1A10.6 10.6 0 0 1 22 12c-1.5 2.9-4.4 5.3-7.8 6.3" /></svg>
              {/if}
            </button>
            <button type="button" class="ico" onclick={() => onFit?.(layer.id)} aria-label="Zoom">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="7" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
            </button>
            <button type="button" class="ico rose" onclick={() => onRemove?.(layer.id)} aria-label="Hapus">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          {/if}
        </div>
      {/each}
    {/if}
  </Modal>
{/if}

<style>
  .drop {
    width: 100%;
    padding: 18px 12px;
    border-radius: 10px;
    border: 1px dashed rgba(255, 255, 255, 0.18);
    background: transparent;
    color: rgba(244, 244, 245, 0.7);
    font-size: 13px;
    letter-spacing: -0.01em;
    cursor: pointer;
  }
  .drop:hover,
  .drop.over {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.35);
    background: rgba(255, 255, 255, 0.06);
  }
  .label {
    margin: 12px 0 6px;
    font-size: 11px;
    color: rgba(244, 244, 245, 0.5);
  }
  .field {
    display: block;
    width: 100%;
    margin-top: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.06);
    color: #fafafa;
    font-size: 12px;
    outline: none;
  }
  .field::placeholder {
    color: rgba(244, 244, 245, 0.38);
  }
  .field.mono {
    font-family: ui-monospace, monospace;
    resize: vertical;
  }
  .field.grow {
    flex: 1;
    min-width: 0;
    margin-top: 0;
  }
  .swatches {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .auto {
    height: 22px;
    padding: 0 8px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: transparent;
    color: rgba(244, 244, 245, 0.65);
    font-size: 11px;
    cursor: pointer;
  }
  .auto.on {
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.22);
  }
  .dot {
    width: 18px;
    height: 18px;
    border-radius: 999px;
    border: 2px solid transparent;
    cursor: pointer;
  }
  .dot.on {
    border-color: #fff;
  }
  .go {
    margin-top: 8px;
    padding: 7px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
    font-size: 12px;
    cursor: pointer;
  }
  .go.full {
    width: 100%;
  }
  .go:hover {
    background: rgba(255, 255, 255, 0.18);
  }
  .err {
    margin: 8px 0 0;
    font-size: 12px;
    color: #fb7185;
  }
  .list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
    font-size: 11px;
    color: rgba(244, 244, 245, 0.5);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    padding: 7px 8px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .chip {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    flex-shrink: 0;
  }
  .name {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    color: #fafafa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    font-size: 10px;
    color: rgba(244, 244, 245, 0.45);
    font-variant-numeric: tabular-nums;
  }
  .ico,
  .ghost {
    border: 0;
    background: transparent;
    color: rgba(244, 244, 245, 0.5);
    cursor: pointer;
    font-size: 12px;
  }
  .ico {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    display: grid;
    place-items: center;
  }
  .ico svg {
    width: 13px;
    height: 13px;
  }
  .ico:hover,
  .ghost:hover {
    color: #fff;
  }
  .ico.rose,
  .ghost.rose {
    color: #fb7185;
  }
</style>
