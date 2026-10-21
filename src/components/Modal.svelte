<script>
  let { title, onClose, children } = $props();

  function onKeydown(e) {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div class="gl-scrim" role="dialog" aria-modal="true" aria-label={title}>
  <div class="gl">
    <header class="gl-head">
      <h3>{title}</h3>
      <button type="button" class="gl-x" onclick={onClose} title="Tutup" aria-label="Tutup">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </header>
    <div class="gl-body">
      {@render children()}
    </div>
  </div>
</div>

<style>
  .gl-scrim {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background: rgba(6, 8, 12, 0.46);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  .gl {
    width: 100%;
    max-width: 360px;
    max-height: 82vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 16px;
    background: rgba(14, 16, 20, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.13);
    backdrop-filter: blur(22px) saturate(1.2);
    -webkit-backdrop-filter: blur(22px) saturate(1.2);
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.42);
    color: #f4f4f5;
  }
  .gl-head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 14px 0 16px;
  }
  .gl-head h3 {
    flex: 1;
    margin: 0;
    font-size: 14px;
    font-weight: 560;
    letter-spacing: -0.02em;
    color: #fafafa;
  }
  .gl-x {
    width: 28px;
    height: 28px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: rgba(244, 244, 245, 0.45);
    display: grid;
    place-items: center;
    cursor: pointer;
  }
  .gl-x:hover {
    color: #fafafa;
    background: rgba(255, 255, 255, 0.08);
  }
  .gl-x svg {
    width: 14px;
    height: 14px;
  }
  .gl-body {
    padding: 14px 16px 16px;
    overflow-y: auto;
  }
</style>
