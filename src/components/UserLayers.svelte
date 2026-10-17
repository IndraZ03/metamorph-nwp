<script>
  import Modal from './Modal.svelte';
  import { parseUserFile, USER_LAYER_COLORS } from '../services/userLayers.js';

  let {
    layers = [],
    onAdd,
    onToggle,
    onFit,
    onRemove,
    onClearAll,
    onRename,
  } = $props();

  let showPanel = $state(false);
  let nameInput = $state('');
  let colorInput = $state('auto'); // 'auto' or a hex color
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
      error = 'Gagal menambahkan overlay ke peta.';
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
        error = `${file.name}: ${e.message}`;
      }
    }
  }

  function handlePaste() {
    if (!pasteText.trim()) {
      error = 'Tempel dulu isi GeoJSON / GPX-nya.';
      return;
    }
    try {
      const parsed = parseUserFile(pasteText);
      addParsed(parsed, 'Overlay tempel');
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

<!-- Top-right button -->
<div class="fixed right-5 top-5 z-40">
  <div class="relative group">
    <button
      type="button"
      onclick={() => (showPanel = true)}
      class="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 border shadow-lg shadow-black/20 backdrop-blur-md bg-white/10 hover:bg-white/20 text-white border-white/20 hover:border-white/35 hover:scale-105 active:scale-95 cursor-pointer"
      aria-label="Overlay Saya (GeoJSON & GPX)"
    >
      <!-- layers + plus icon -->
      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3L2 8l10 5 10-5-10-5z" />
        <path d="M2 13l10 5 10-5" />
        <path d="M12 18v-6" />
        <path d="M18 6v6" />
      </svg>
      {#if layers.length > 0}
        <span class="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-[#2563EB] text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-white/40 shadow-sm shadow-blue-500/50">
          {layers.length}
        </span>
      {/if}
    </button>
    <div
      class="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md text-xs font-medium text-white whitespace-nowrap shadow-2xl border border-white/10 opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150"
    >
      Overlay Saya (GeoJSON & GPX)
    </div>
  </div>
</div>

{#if showPanel}
  <Modal
    title="Overlay Saya"
    subtitle="Tambah layer GeoJSON & track GPX ke peta"
    onClose={() => (showPanel = false)}
  >
    {#snippet icon()}
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3L2 8l10 5 10-5-10-5z" />
        <path d="M2 13l10 5 10-5" />
      </svg>
    {/snippet}

    <!-- Add overlay -->
    <div class="space-y-3">
      <div class="text-xs font-bold text-slate-700 uppercase tracking-wider">Tambah Overlay</div>

      <!-- Dropzone / file picker -->
      <button
        type="button"
        onclick={() => fileInput?.click()}
        ondragenter={(e) => { e.preventDefault(); dragOver = true; }}
        ondragover={(e) => { e.preventDefault(); dragOver = true; }}
        ondragleave={() => (dragOver = false)}
        ondrop={handleDrop}
        class="w-full rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors {dragOver
          ? 'border-sky-500 bg-sky-50'
          : 'border-slate-300 bg-slate-50 hover:border-slate-400'}"
      >
        <div class="text-sm font-medium text-slate-700">Seret file ke sini atau klik untuk pilih</div>
        <div class="text-xs text-slate-500 mt-1">.geojson · .json · .gpx · .xml — boleh banyak file sekaligus</div>
      </button>
      <input
        bind:this={fileInput}
        type="file"
        accept=".geojson,.json,.gpx,.xml"
        multiple
        class="hidden"
        onchange={(e) => { handleFiles(e.target.files); e.target.value = ''; }}
      />

      <!-- Name + color -->
      <div class="flex gap-2">
        <input
          type="text"
          bind:value={nameInput}
          placeholder="Nama overlay (opsional — default nama file)"
          class="flex-1 min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500"
        />
      </div>
      <div class="flex items-center gap-1.5 flex-wrap">
        <button
          type="button"
          onclick={() => (colorInput = 'auto')}
          class="h-7 px-2 rounded-lg border text-xs font-medium {colorInput === 'auto'
            ? 'border-sky-600 bg-sky-50 text-sky-700'
            : 'border-slate-300 text-slate-600'}"
        >
          Otomatis
        </button>
        {#each USER_LAYER_COLORS as c}
          <button
            type="button"
            onclick={() => (colorInput = c)}
            class="w-7 h-7 rounded-full border-2 {colorInput === c ? 'border-slate-900 scale-110' : 'border-white shadow'}"
            style="background:{c}"
            title={c}
            aria-label="Warna {c}"
          ></button>
        {/each}
      </div>

      <!-- Paste -->
      <textarea
        bind:value={pasteText}
        rows="4"
        placeholder="Tempel GeoJSON atau GPX di sini…"
        class="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-mono text-slate-800 outline-none focus:border-sky-500"
      ></textarea>
      <button
        type="button"
        onclick={handlePaste}
        class="w-full rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-medium py-2 transition-colors"
      >
        Tambah dari Teks
      </button>

      {#if error}
        <div class="rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">{error}</div>
      {/if}
      <p class="text-[11px] text-slate-400">Overlay hanya tersimpan di sesi ini (tidak diunggah ke server).</p>
    </div>

    <!-- Layer list -->
    <div class="space-y-2 pt-1">
      <div class="flex items-center justify-between">
        <div class="text-xs font-bold text-slate-700 uppercase tracking-wider">Overlay Ditambahkan ({layers.length})</div>
        {#if layers.length > 0}
          <button
            type="button"
            onclick={onClearAll}
            class="text-xs font-medium text-rose-600 hover:text-rose-700"
          >
            Hapus semua
          </button>
        {/if}
      </div>

      {#if layers.length === 0}
        <div class="rounded-xl bg-slate-50 border border-slate-200 px-4 py-4 text-center text-xs text-slate-500">
          Belum ada overlay. Tambahkan file GeoJSON atau track GPX di atas.
        </div>
      {/if}

      {#each layers as layer (layer.id)}
        <div class="flex items-center gap-2 rounded-xl bg-slate-50 border border-slate-200 px-3 py-2">
          <span class="w-3 h-3 rounded-full shrink-0 ring-2 ring-white shadow" style="background:{layer.color}"></span>
          {#if renamingId === layer.id}
            <input
              type="text"
              bind:value={renameText}
              autofocus
              maxlength="80"
              onkeydown={(e) => {
                if (e.key === 'Enter') saveRename();
                if (e.key === 'Escape') cancelRename();
              }}
              class="flex-1 min-w-0 rounded-lg border border-sky-500 px-2 py-1 text-sm text-slate-800 outline-none"
              aria-label="Nama baru overlay"
            />
            <button
              type="button"
              onclick={saveRename}
              class="w-7 h-7 rounded-lg flex items-center justify-center text-emerald-600 hover:bg-emerald-100"
              title="Simpan nama (Enter)"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </button>
            <button
              type="button"
              onclick={cancelRename}
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-200"
              title="Batal (Esc)"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          {:else}
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-slate-800 truncate">{layer.name}</div>
              <div class="text-[11px] text-slate-500">
                {layer.kind === 'gpx' ? 'GPX' : 'GeoJSON'} · {layer.count} fitur
                {#if layer.counts}
                  · {layer.counts.LineString} garis · {layer.counts.Polygon} poligon · {layer.counts.Point} titik
                {/if}
              </div>
            </div>
            <button
              type="button"
              onclick={() => startRename(layer)}
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-sky-600 hover:bg-sky-100"
              title="Ganti nama"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
            </button>
            <button
              type="button"
              onclick={() => onToggle?.(layer.id)}
              class="w-7 h-7 rounded-lg flex items-center justify-center {layer.visible
                ? 'text-sky-600 hover:bg-sky-100'
                : 'text-slate-400 hover:bg-slate-200'}"
              title={layer.visible ? 'Sembunyikan' : 'Tampilkan'}
            >
              {#if layer.visible}
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              {:else}
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 3l18 18" />
                  <path d="M10.6 5.1A10.6 10.6 0 0 1 22 12c-1.5 2.9-4.4 5.3-7.8 6.3" />
                  <path d="M6.6 6.6A10 10 0 0 0 2 12c1.5 2.9 4.4 5.3 7.8 6.3" />
                  <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
                </svg>
              {/if}
            </button>
            <button
              type="button"
              onclick={() => onFit?.(layer.id)}
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-500 hover:text-sky-600 hover:bg-sky-100"
              title="Zoom ke overlay"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="7" />
                <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                <path d="M12 12h.01" />
              </svg>
            </button>
            <button
              type="button"
              onclick={() => onRemove?.(layer.id)}
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-rose-600 hover:bg-rose-100"
              title="Hapus overlay"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              </svg>
            </button>
          {/if}
        </div>
      {/each}
    </div>
  </Modal>
{/if}
