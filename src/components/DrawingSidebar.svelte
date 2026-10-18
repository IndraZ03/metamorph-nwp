<script>
  import {
    addLayer,
    canRedo,
    canUndo,
    clearAll,
    drawing,
    duplicateFeature,
    exportGeoJSON,
    findFeature,
    importGeoJSON,
    patchStyle,
    persist,
    redo,
    removeFeature,
    removeLayer,
    selectFeature,
    setActiveLayer,
    setActiveTool,
    setFeatureLocked,
    setFeatureVisible,
    setLayerLocked,
    setLayerVisible,
    setSidebarOpen,
    setIconId,
    setUnits,
    setWxId,
    undo,
    updateFeature,
  } from '../services/drawing/store.svelte.js';
  import { STYLE_PRESETS, TOOL_GROUPS, TOOLS } from '../services/drawing/tools.js';
  import { ICON_ATLAS, WX_ATLAS } from '../services/drawing/icons.js';
  import { formatDMS, formatLatLon } from '../services/drawing/geo.js';
  import {
    bearingsInputValue,
    parseBearingsInput,
    parseRadiiInput,
    radiiInputValue,
    rebuildRings,
  } from '../services/drawing/geometry.js';
  import { downloadText } from '../services/drawing/persist.js';
  import { parseGeoJSON } from '../services/userLayers.js';

  let { onSync, onCancelDraft, onFinishDraft, onAdoptTool, onExportPng } = $props();

  let confirmClear = $state(false);
  let importErr = $state('');
  let fileEl = $state(null);

  const selected = $derived(drawing.selectedId ? findFeature(drawing.selectedId) : null);
  const feat = $derived(selected?.feature || null);
  const style = $derived(feat?.properties?.style || {});

  function toolsIn(group) {
    return TOOLS.filter((t) => t.group === group);
  }

  function pickTool(id) {
    if (onAdoptTool) onAdoptTool(id);
    else {
      onCancelDraft?.();
      setActiveTool(id);
      onSync?.();
    }
  }

  function close() {
    onCancelDraft?.();
    setActiveTool('select');
    setSidebarOpen(false);
    onSync?.();
  }

  function onUndo() {
    onCancelDraft?.();
    undo();
    onSync?.();
  }

  function onRedo() {
    onCancelDraft?.();
    redo();
    onSync?.();
  }

  async function onSave() {
    try {
      await persist();
    } catch (err) {
      drawing.error = err.message;
    }
  }

  function onExport() {
    const fc = exportGeoJSON();
    downloadText(`drawings-${Date.now()}.geojson`, JSON.stringify(fc, null, 2));
  }

  function onImportFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    file.text().then((text) => {
      try {
        importGeoJSON(parseGeoJSON(text));
        importErr = '';
        onSync?.();
      } catch (err) {
        importErr = err.message;
      }
    });
  }

  function doClear() {
    if (!confirmClear) {
      confirmClear = true;
      return;
    }
    confirmClear = false;
    onCancelDraft?.();
    clearAll();
    onSync?.();
  }

  function patchProp(key, value) {
    if (!feat) return;
    updateFeature(feat.id, { properties: { [key]: value } }, { history: false });
    onSync?.();
  }

  function patchSt(key, value) {
    if (!feat) return;
    patchStyle(feat.id, { [key]: value }, { history: false });
    onSync?.();
  }

  function applyPreset(name) {
    if (!feat) return;
    patchStyle(feat.id, STYLE_PRESETS[name]);
    onSync?.();
  }

  function pickIcon(id) {
    setIconId(id);
    if (feat?.properties.tool === 'icon') {
      updateFeature(feat.id, { properties: { iconId: id, marker: id } }, { history: false });
      onSync?.();
    }
  }

  function pickWx(id) {
    setWxId(id);
    if (feat?.properties.tool === 'wx') {
      updateFeature(feat.id, { properties: { wxId: id, marker: id } }, { history: false });
      onSync?.();
    }
  }

  function applyRingsRadii(text) {
    if (!feat || feat.properties.tool !== 'rings') return;
    const radiiM = parseRadiiInput(text, drawing.units);
    if (!radiiM.length) return;
    const next = rebuildRings(feat, { radiiM }, drawing.units);
    if (!next) return;
    updateFeature(feat.id, { geometry: next.geometry, properties: next.properties }, { history: true });
    onSync?.();
  }

  function applyRingsBearings(text) {
    if (!feat || feat.properties.tool !== 'rings') return;
    const labelBearings = parseBearingsInput(text);
    const next = rebuildRings(feat, { labelBearings }, drawing.units);
    if (!next) return;
    updateFeature(feat.id, { geometry: next.geometry, properties: next.properties }, { history: true });
    onSync?.();
  }

  function copyCoords() {
    if (!feat?.geometry || feat.geometry.type !== 'Point') return;
    const [lon, lat] = feat.geometry.coordinates;
    const text = feat.properties.dms || formatDMS(lon, lat) || formatLatLon(lon, lat);
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(() => {});
  }

  const ptCoord = $derived(
    feat?.geometry?.type === 'Point' ? feat.geometry.coordinates : null
  );

  const saveLabel = $derived(
    drawing.saveStatus === 'saving'
      ? 'Saving'
      : drawing.saveStatus === 'saved'
        ? 'Saved'
        : drawing.saveStatus === 'error'
          ? 'Error'
          : drawing.saveStatus === 'unsaved'
            ? 'Unsaved'
            : 'Save'
  );
</script>

<aside
  id="drawing-sidebar"
  class="dw"
  class:on={drawing.sidebarOpen}
  aria-hidden={!drawing.sidebarOpen}
>
  <header class="dw-head">
    <div>
      <h2>Drawing Tools</h2>
      <p>Forecast annotation</p>
    </div>
    <button type="button" class="ico" onclick={close} aria-label="Tutup drawing">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
    </button>
  </header>

  <div class="dw-body">
    {#each TOOL_GROUPS as group}
      <section class="sec">
        <h3>{group.label}</h3>
        <div class="grid">
          {#each toolsIn(group.id) as t}
            <button
              type="button"
              class="tool"
              class:on={drawing.activeTool === t.id}
              title={t.tip}
              aria-pressed={drawing.activeTool === t.id}
              onclick={() => pickTool(t.id)}
            >
              {t.label}
            </button>
          {/each}
        </div>
      </section>
    {/each}

    {#if drawing.activeTool === 'icon' || feat?.properties.tool === 'icon'}
      <section class="sec">
        <h3>Icon</h3>
        <div class="grid">
          {#each ICON_ATLAS as ic}
            <button
              type="button"
              class="tool"
              class:on={(feat?.properties.iconId || drawing.iconId) === ic.id}
              title={ic.label}
              onclick={() => pickIcon(ic.id)}
            >{ic.label}</button>
          {/each}
        </div>
      </section>
    {/if}

    {#if drawing.activeTool === 'wx' || feat?.properties.tool === 'wx'}
      <section class="sec">
        <h3>Wx</h3>
        <p class="hint">Simbol analisis. Bukan observasi.</p>
        <div class="grid">
          {#each WX_ATLAS as wx}
            <button
              type="button"
              class="tool"
              class:on={(feat?.properties.wxId || drawing.wxId) === wx.id}
              title={wx.label}
              onclick={() => pickWx(wx.id)}
            >{wx.label}</button>
          {/each}
        </div>
      </section>
    {/if}

    {#if drawing.draftHint}
      <p class="hint">{drawing.draftHint}</p>
      {#if drawing.activeTool === 'polyline' || drawing.activeTool === 'polygon' || drawing.activeTool === 'area'}
        <div class="actions draft-act">
          <button
            type="button"
            class="mini"
            disabled={!drawing.draftReady}
            onclick={() => onFinishDraft?.()}
          >Selesai</button>
          <button type="button" class="mini rose" onclick={() => onCancelDraft?.()}>Batal</button>
        </div>
      {/if}
    {/if}

    <section class="sec rowish">
      <h3>Units</h3>
      <div class="seg">
        <button type="button" class:on={drawing.units === 'km'} onclick={() => setUnits('km')}>km</button>
        <button type="button" class:on={drawing.units === 'nm'} onclick={() => setUnits('nm')}>NM</button>
      </div>
    </section>

    {#if feat}
      <section class="sec inspect">
        <h3>Inspector</h3>
        <label>
          Nama
          <input
            type="text"
            maxlength="80"
            value={feat.properties.name}
            oninput={(e) => patchProp('name', e.currentTarget.value)}
          />
        </label>
        <label>
          Label
          <input
            type="text"
            maxlength="120"
            value={feat.properties.label || ''}
            oninput={(e) => patchProp('label', e.currentTarget.value)}
          />
        </label>
        {#if feat.properties.tool === 'rings'}
          <label>
            Radius ({drawing.units === 'nm' ? 'NM' : 'km'})
            <input
              type="text"
              maxlength="80"
              value={radiiInputValue(feat.properties.radiiM, drawing.units)}
              onchange={(e) => applyRingsRadii(e.currentTarget.value)}
            />
          </label>
          <label>
            Bearing label (°T)
            <input
              type="text"
              maxlength="80"
              value={bearingsInputValue(feat.properties.labelBearings)}
              onchange={(e) => applyRingsBearings(e.currentTarget.value)}
            />
          </label>
          <p class="hint">Label jarak di tiap bearing. Pisah koma. True north.</p>
        {/if}
        {#if feat.properties.tool === 'numbered'}
          <label>
            Nomor
            <input
              type="number"
              min="1"
              step="1"
              value={feat.properties.number || 1}
              oninput={(e) => {
                const n = Math.max(1, Number(e.currentTarget.value) || 1);
                updateFeature(feat.id, { properties: { number: n, label: String(n) } }, { history: false });
                onSync?.();
              }}
            />
          </label>
        {/if}
        {#if ptCoord}
          <p class="hint">{formatLatLon(ptCoord[0], ptCoord[1])}</p>
          {#if feat.properties.tool === 'coord' || feat.properties.dms}
            <p class="hint">{feat.properties.dms || formatDMS(ptCoord[0], ptCoord[1])}</p>
          {/if}
          <button type="button" class="mini" onclick={copyCoords}>Copy koordinat</button>
        {/if}
        <div class="pair">
          <label>
            Stroke
            <input type="color" value={style.stroke || '#38bdf8'} oninput={(e) => patchSt('stroke', e.currentTarget.value)} />
          </label>
          <label>
            Fill
            <input type="color" value={style.fill || '#38bdf8'} oninput={(e) => patchSt('fill', e.currentTarget.value)} />
          </label>
        </div>
        <label>
          Lebar {style.strokeWidth ?? 2}
          <input
            type="range"
            min="1"
            max="8"
            step="0.5"
            value={style.strokeWidth ?? 2}
            oninput={(e) => patchSt('strokeWidth', Number(e.currentTarget.value))}
          />
        </label>
        <label>
          Fill opacity
          <input
            type="range"
            min="0"
            max="0.6"
            step="0.02"
            value={style.fillOpacity ?? 0.22}
            oninput={(e) => patchSt('fillOpacity', Number(e.currentTarget.value))}
          />
        </label>
        <label class="chk">
          <input
            type="checkbox"
            checked={!!style.dashed}
            onchange={(e) => patchSt('dashed', e.currentTarget.checked ? 1 : 0)}
          />
          Dashed
        </label>
        <div class="presets">
          {#each Object.keys(STYLE_PRESETS) as name}
            <button type="button" class="mini" onclick={() => applyPreset(name)}>{name}</button>
          {/each}
        </div>
        <div class="actions">
          <button type="button" class="mini" onclick={() => { duplicateFeature(feat.id); onSync?.(); }}>Duplikat</button>
          <button type="button" class="mini" onclick={() => { setFeatureLocked(feat.id, !feat.properties.locked); onSync?.(); }}>
            {feat.properties.locked ? 'Unlock' : 'Lock'}
          </button>
          <button type="button" class="mini rose" onclick={() => { removeFeature(feat.id); onSync?.(); }}>Hapus</button>
        </div>
      </section>
    {/if}

    <section class="sec">
      <div class="sec-head">
        <h3>Layers</h3>
        <button type="button" class="mini" onclick={() => addLayer()}>+ Grup</button>
      </div>
      {#each drawing.layers as layer (layer.id)}
        <div class="lrow" class:on={drawing.activeLayerId === layer.id}>
          <button type="button" class="name" onclick={() => setActiveLayer(layer.id)}>{layer.name}</button>
          <button
            type="button"
            class="ico"
            aria-label={layer.visible ? 'Sembunyikan' : 'Tampilkan'}
            onclick={() => { setLayerVisible(layer.id, !layer.visible); onSync?.(); }}
          >
            {layer.visible ? '◉' : '○'}
          </button>
          <button
            type="button"
            class="ico"
            aria-label={layer.locked ? 'Unlock' : 'Lock'}
            onclick={() => setLayerLocked(layer.id, !layer.locked)}
          >
            {layer.locked ? 'L' : '·'}
          </button>
          <button type="button" class="ico rose" aria-label="Hapus grup" onclick={() => { removeLayer(layer.id); onSync?.(); }}>×</button>
        </div>
        {#each layer.features as f (f.id)}
          <div class="frow" class:on={drawing.selectedId === f.id}>
            <button
              type="button"
              class="name"
              onclick={() => { selectFeature(f.id); setActiveTool('select'); onSync?.(); }}
            >{f.properties.name}</button>
            <button
              type="button"
              class="ico"
              aria-label={f.properties.visible === false ? 'Tampilkan' : 'Sembunyikan'}
              onclick={() => {
                setFeatureVisible(f.id, f.properties.visible === false);
                onSync?.();
              }}
            >{f.properties.visible === false ? '○' : '●'}</button>
          </div>
        {/each}
      {/each}
    </section>

    {#if importErr}
      <p class="err">{importErr}</p>
    {/if}
    {#if drawing.error}
      <p class="err">{drawing.error}</p>
    {/if}
  </div>

  <footer class="dw-foot">
    <button type="button" class="mini" disabled={!canUndo()} onclick={onUndo}>Undo</button>
    <button type="button" class="mini" disabled={!canRedo()} onclick={onRedo}>Redo</button>
    <button type="button" class="mini rose" onclick={doClear}>{confirmClear ? 'Yakin?' : 'Clear'}</button>
    <button type="button" class="mini" onclick={onSave}>{saveLabel}</button>
    <button type="button" class="mini" onclick={onExport}>GeoJSON</button>
    <button type="button" class="mini" onclick={() => fileEl?.click()}>Import</button>
    <button type="button" class="mini" onclick={() => onExportPng?.()}>PNG</button>
    <input bind:this={fileEl} type="file" accept=".geojson,.json" class="hidden" onchange={onImportFile} />
  </footer>
</aside>

<style>
  .dw {
    position: fixed;
    top: 16px;
    right: 76px;
    z-index: 45;
    width: 320px;
    max-height: calc(100vh - 32px);
    display: flex;
    flex-direction: column;
    border-radius: 12px;
    background: rgba(14, 16, 20, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.13);
    color: #f4f4f5;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.38);
    transform: translateX(12px);
    opacity: 0;
    pointer-events: none;
    transition: transform 180ms ease, opacity 180ms ease;
  }
  .dw.on {
    transform: none;
    opacity: 1;
    pointer-events: auto;
  }
  @media (prefers-reduced-motion: reduce) {
    .dw {
      transition: none;
    }
  }
  .dw-head {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 12px 12px 8px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .dw-head h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  .dw-head p {
    margin: 2px 0 0;
    font-size: 10px;
    color: rgba(244, 244, 245, 0.5);
  }
  .dw-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px 12px;
  }
  .sec {
    margin-top: 10px;
  }
  .sec h3,
  .sec-head h3 {
    margin: 0 0 6px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(244, 244, 245, 0.48);
  }
  .sec-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
  }
  .tool,
  .mini,
  .seg button {
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: transparent;
    color: rgba(244, 244, 245, 0.82);
    border-radius: 6px;
    font-size: 10px;
    cursor: pointer;
  }
  .tool {
    height: 28px;
  }
  .tool:hover,
  .mini:hover,
  .seg button:hover {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.28);
    background: rgba(255, 255, 255, 0.06);
  }
  .tool.on,
  .seg button.on {
    color: #fff;
    background: rgba(37, 99, 235, 0.55);
    border-color: rgba(96, 165, 250, 0.55);
  }
  .hint {
    margin: 8px 0 0;
    font-size: 11px;
    color: #7dd3fc;
  }
  .rowish {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .rowish h3 {
    margin: 0;
  }
  .seg {
    display: flex;
    gap: 4px;
  }
  .seg button {
    padding: 4px 8px;
  }
  .inspect label {
    display: block;
    margin-top: 6px;
    font-size: 10px;
    color: rgba(244, 244, 245, 0.55);
  }
  .inspect input[type='text'] {
    display: block;
    width: 100%;
    margin-top: 3px;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.06);
    color: #fafafa;
    font-size: 12px;
  }
  .inspect input[type='range'] {
    width: 100%;
  }
  .pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .chk {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .presets,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
  }
  .mini {
    padding: 4px 7px;
  }
  .mini:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .mini.rose,
  .ico.rose {
    color: #fb7185;
  }
  .lrow,
  .frow {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding: 4px 6px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: #e4e4e7;
    font-size: 12px;
    text-align: left;
    cursor: pointer;
  }
  .lrow.on,
  .frow.on {
    background: rgba(255, 255, 255, 0.08);
  }
  .lrow .name {
    flex: 1;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    cursor: pointer;
    font-size: 12px;
  }
  .frow {
    padding-left: 14px;
    font-size: 11px;
    color: rgba(244, 244, 245, 0.72);
  }
  .frow .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: inherit;
  }
  .ico {
    width: 22px;
    height: 22px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: rgba(244, 244, 245, 0.5);
    display: grid;
    place-items: center;
    cursor: pointer;
  }
  .ico:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.08);
  }
  .ico svg {
    width: 13px;
    height: 13px;
  }
  .err {
    margin: 8px 0 0;
    font-size: 11px;
    color: #fb7185;
  }
  .dw-foot {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 8px 10px 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .hidden {
    display: none;
  }
  @media (max-width: 720px) {
    .dw {
      top: auto;
      right: 0;
      bottom: 0;
      left: 0;
      width: 100%;
      max-height: 52vh;
      border-radius: 14px 14px 0 0;
      transform: translateY(12px);
    }
    .dw.on {
      transform: none;
    }
  }
</style>
