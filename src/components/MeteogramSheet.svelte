<script>
  import { onMount } from 'svelte';
  import { formatWibShort } from '../services/numericTiles.js';
  import MeteogramChart from './MeteogramChart.svelte';

  let { series = null, loading = false, error = null, activeTime = null,
    onClose, onRetry, onSelectTime } = $props();
  let sheet;
  let handle;
  let height = $state(0);
  let viewport = $state(800);
  let dragging = $state(false);
  let originY = 0, originHeight = 0, pendingHeight = 0, frame = 0;
  let returnFocus;

  // Content ends at the wind barb strip, so the sheet never needs a tall state.
  const resting = $derived(Math.min(360, Math.max(240, viewport - 210)));

  function paint(value) {
    height = Math.round(value);
    // Sheet and sibling timeline receive exactly the same frame's height.
    sheet?.parentElement?.style.setProperty('--meteogram-visible-height', `${height}px`);
  }
  function close() {
    cancelAnimationFrame(frame);
    paint(0);
    onClose?.();
  }
  function down(event) {
    if (event.button !== 0) return;
    dragging = true;
    originY = event.clientY;
    originHeight = height;
    pendingHeight = height;
    handle.setPointerCapture(event.pointerId);
  }
  function move(event) {
    if (!dragging) return;
    pendingHeight = Math.max(0, Math.min(resting, originHeight + originY - event.clientY));
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; paint(pendingHeight); });
  }
  function up(event) {
    if (!dragging) return;
    cancelAnimationFrame(frame); frame = 0;
    paint(pendingHeight);
    dragging = false;
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
    if (height < resting * 0.6) close();
    else paint(resting);
  }
  function cancel() { dragging = false; paint(resting); }
  function locationLabel(location) {
    return [location?.kecamatan, location?.kabupaten_kota, location?.provinsi].filter(Boolean).join(', ')
      || location?.display_name || 'Titik peta';
  }
  onMount(() => {
    returnFocus = document.activeElement;
    const resize = () => {
      viewport = window.visualViewport?.height || window.innerHeight;
      paint(Math.min(360, Math.max(240, viewport - 210)));
    };
    const escape = event => {
      if (event.key !== 'Escape' || event.defaultPrevented
        || document.querySelector('[aria-modal="true"]')) return;
      event.preventDefault(); close();
    };
    resize(); handle?.focus({ preventScroll: true });
    window.addEventListener('resize', resize);
    window.visualViewport?.addEventListener('resize', resize);
    window.addEventListener('keydown', escape);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      window.visualViewport?.removeEventListener('resize', resize);
      window.removeEventListener('keydown', escape);
      sheet?.parentElement?.style.removeProperty('--meteogram-visible-height');
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
    };
  });
</script>

<aside bind:this={sheet} class="mg-sheet" style:height={`${height}px`} aria-label="Meteogram prakiraan model">
  <header>
    <button bind:this={handle} class="handle" type="button" aria-label="Geser ke bawah untuk menutup meteogram"
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={cancel}
      onlostpointercapture={() => { if (dragging) cancel(); }}>
      <span class="grip"></span><span>Meteogram · {series?.modelTitle || 'NWP'}</span>
    </button>
    <button type="button" onclick={close} aria-label="Tutup meteogram">Tutup</button>
  </header>
  <div class="metadata">
    {locationLabel(series?.location)}
    {#if series} · {series.latitude.toFixed(3)}, {series.longitude.toFixed(3)} · Run {formatWibShort(series.runTime)} WIB{/if}
  </div>
  <div class="content" aria-busy={loading}>
    {#if loading}<p role="status">Memuat seri prakiraan…</p>
    {:else if error}<p role="alert">{error} <button type="button" onclick={onRetry}>Coba lagi</button></p>
    {:else if !series?.points?.length}<p>Data meteogram tidak tersedia untuk titik ini.</p>
    {:else}
      {#if series.errors?.length}<p class="notice">Sebagian permintaan gagal ({series.errors.length}). <button type="button" onclick={onRetry}>Coba lagi</button></p>{/if}
      <MeteogramChart {series} {activeTime} {onSelectTime}/>
    {/if}
  </div>
</aside>

<style>
  .mg-sheet { --mg-bg:#13171c; --mg-text:#e5e7eb; --mg-muted:#a1adbd; --mg-border:#343d47; position:absolute; bottom:0; left:0; right:0; z-index:46; display:flex; flex-direction:column; min-width:0; background:var(--mg-bg); color:var(--mg-text); border-top:1px solid var(--mg-border); border-radius:10px 10px 0 0; padding-bottom:env(safe-area-inset-bottom,0px); font:12px/1.4 Inter,system-ui,sans-serif; box-sizing:border-box; }
  header { display:flex; align-items:center; gap:8px; padding:4px 12px; border-bottom:1px solid var(--mg-border); }
  button { color:inherit; padding:7px 9px; border:1px solid var(--mg-border); border-radius:4px; cursor:pointer; white-space:nowrap; }
  button:focus-visible { outline:2px solid var(--mg-text); outline-offset:2px; }
  .handle { display:flex; align-items:center; flex:1; gap:10px; border:0; min-width:0; touch-action:none; cursor:ns-resize; text-align:left; }
  .grip { width:28px; height:3px; background:var(--mg-muted); border-radius:3px; flex-shrink:0; }
  .metadata { padding:6px 16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--mg-muted); }
  .content { display:flex; flex-direction:column; flex:1; min-height:0; overflow:auto; } .content > p { padding:0 16px; }
  .notice { font-size:11px; color:var(--mg-muted); }
  @media(max-width:480px) { header { gap:3px; padding:3px 8px; } .grip { display:none; } button { padding:7px 6px; } }
</style>
