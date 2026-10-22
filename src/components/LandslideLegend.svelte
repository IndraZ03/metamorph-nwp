<script>
  let {
    opacity = 0.6,
    onChangeOpacity,
    onClose,
  } = $props();

  const LEVELS = [
    { color: '#DC2626', label: 'Bahaya' },
    { color: '#F97316', label: 'Siaga' },
    { color: '#EAB308', label: 'Waspada' },
  ];
</script>

<div class="ls" role="region" aria-label="Prakiraan potensi tanah longsor">
  <header class="ls-head">
    <span class="ls-name">Prakiraan Potensi Tanah Longsor</span>
    <div class="ls-actions">
      <div class="ls-op">
        <button
          type="button"
          class="ls-op-btn"
          aria-label="Opasitas lapisan {Math.round(opacity * 100)} persen"
          title="Opasitas"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" />
          </svg>
        </button>
        <div class="ls-op-pop">
          <div class="ls-op-label">
            <span>Opasitas</span>
            <span>{Math.round(opacity * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="1"
            step="0.05"
            value={opacity}
            oninput={(e) => onChangeOpacity?.(parseFloat(e.currentTarget.value))}
            aria-label="Opasitas lapisan"
          />
        </div>
      </div>
      <button type="button" class="ls-x" onclick={onClose} title="Tutup layer longsor" aria-label="Tutup">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
      </button>
    </div>
  </header>
  <div class="ls-bar">
    {#each LEVELS as lvl}
      <i style="background:{lvl.color}"></i>
    {/each}
  </div>
  <div class="ls-scale">
    {#each LEVELS as lvl}
      <span>{lvl.label}</span>
    {/each}
  </div>
</div>

<style>
  .ls {
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 40;
    width: 252px;
    padding: 8px 8px 7px;
    border-radius: 12px;
    background: rgba(14, 16, 20, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.13);
    backdrop-filter: blur(18px) saturate(1.2);
    -webkit-backdrop-filter: blur(18px) saturate(1.2);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.32);
    color: #f4f4f5;
  }
  .ls-head {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }
  .ls-name {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    font-weight: 560;
    letter-spacing: -0.01em;
    line-height: 1.3;
    color: #fafafa;
  }
  .ls-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    margin-top: -2px;
  }
  .ls-op {
    position: relative;
  }
  .ls-op-btn,
  .ls-x {
    width: 22px;
    height: 22px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: rgba(244, 244, 245, 0.45);
    display: grid;
    place-items: center;
    cursor: pointer;
  }
  .ls-op-btn:hover,
  .ls-x:hover {
    color: #fafafa;
    background: rgba(255, 255, 255, 0.08);
  }
  .ls-op-btn svg,
  .ls-x svg {
    width: 13px;
    height: 13px;
  }
  .ls-op-pop {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 168px;
    padding: 8px 10px;
    border-radius: 10px;
    background: rgba(14, 16, 20, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.13);
    backdrop-filter: blur(18px);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s;
  }
  .ls-op:hover .ls-op-pop,
  .ls-op:focus-within .ls-op-pop {
    opacity: 1;
    pointer-events: auto;
  }
  .ls-op-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 10px;
    color: rgba(244, 244, 245, 0.7);
    font-variant-numeric: tabular-nums;
  }
  .ls-op-pop input {
    width: 100%;
    accent-color: #2563eb;
    cursor: pointer;
  }
  .ls-bar {
    display: flex;
    height: 4px;
    margin-top: 8px;
    overflow: hidden;
    border-radius: 999px;
  }
  .ls-bar i {
    flex: 1;
    display: block;
  }
  .ls-scale {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 9px;
    color: rgba(244, 244, 245, 0.45);
  }
</style>
