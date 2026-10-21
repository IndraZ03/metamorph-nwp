<script>
  import { onMount, onDestroy } from 'svelte';
  import { CalendarDays, ChevronLeft, ChevronRight, Pause, Play } from 'lucide-svelte';

  let {
    daily = false,
    observation = false,
    steps = [],
    selectedToken = null,
    playing = false,
    loop = false,
    disabled = false,
    modelTitle = '',
    runTime = null,
    onSeek,
    onPlay,
    onPause,
    onPrev,
    onNext,
    onLoop,
  } = $props();

  const WIB = 7 * 3600 * 1000;
  const BULAN_SHORT = [
    '',
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'Mei',
    'Jun',
    'Jul',
    'Agu',
    'Sep',
    'Okt',
    'Nov',
    'Des',
  ];

  let trackEl = $state(null);
  let trackW = $state(640);
  let dragging = $state(false);
  let dragPct = $state(null);
  let dateOpen = $state(false);
  let reducedMotion = $state(false);

  const selected = $derived(steps.find((s) => s.token === selectedToken) || steps[0] || null);
  const t0 = $derived(steps[0]?.t ?? 0);
  const t1 = $derived(steps.length > 1 ? steps[steps.length - 1].t : t0 + 1);
  const span = $derived(Math.max(1, t1 - t0));

  const selPct = $derived(
    selected && span ? ((selected.t - t0) / span) * 100 : 0
  );
  const headPct = $derived(dragging && dragPct != null ? dragPct * 100 : selPct);

  const dates = $derived.by(() => {
    const map = new Map();
    for (const s of steps) {
      const key = wibDateKey(s.t);
      if (!map.has(key)) map.set(key, s);
    }
    return [...map.entries()].map(([key, first]) => ({ key, first, label: wibDateLabel(first.t) }));
  });

  const ticks = $derived.by(() => buildTicks(t0, t1, trackW));

  const hoverStep = $derived.by(() => {
    if (!dragging || dragPct == null || !steps.length) return selected;
    const t = t0 + dragPct * span;
    return nearest(steps, t);
  });

  function wibDate(t) {
    return new Date(t + WIB);
  }

  function wibDateKey(t) {
    const d = wibDate(t);
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
  }

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function wibDateLabel(t) {
    const d = wibDate(t);
    return `${d.getUTCDate()} ${BULAN_SHORT[d.getUTCMonth() + 1]}`;
  }

  function wibTimeLabel(t) {
    const d = wibDate(t);
    return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
  }

  function wibFullLabel(t) {
    const d = wibDate(t);
    return `${d.getUTCDate()} ${BULAN_SHORT[d.getUTCMonth() + 1]} ${d.getUTCFullYear()}, ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())} WIB`;
  }

  function parseTime(isoOrT) {
    if (isoOrT == null || isoOrT === '') return NaN;
    if (typeof isoOrT === 'number') return isoOrT;
    const s = String(isoOrT);
    const n = Date.parse(s);
    if (!Number.isNaN(n)) return n;
    const m = s.match(/^(\d{4})(\d{2})(\d{2})(\d{2})$/);
    if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]);
    return NaN;
  }

  function wibShort(isoOrT) {
    const t = parseTime(isoOrT);
    if (Number.isNaN(t)) return '—';
    const d = wibDate(t);
    return `${d.getUTCDate()} ${BULAN_SHORT[d.getUTCMonth() + 1]} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
  }

  function nearest(rows, t) {
    let best = rows[0];
    let bestAbs = Infinity;
    for (const row of rows) {
      const abs = Math.abs(row.t - t);
      if (abs < bestAbs) {
        best = row;
        bestAbs = abs;
      }
    }
    return best;
  }

  function alignWib(t, interval) {
    const local = t + WIB;
    return Math.floor(local / interval) * interval - WIB;
  }

  function buildTicks(start, end, width) {
    if (!start || !end || end <= start || width < 40) return [];
    const hours = (end - start) / 3600000;
    const pxPerHour = width / hours;
    let majorH = 24;
    if (pxPerHour >= 64) majorH = 1;
    else if (pxPerHour >= 36) majorH = 3;
    else if (pxPerHour >= 18) majorH = 6;
    else if (pxPerHour >= 9) majorH = 12;
    const majorMs = observation && hours <= 4 ? (width / (hours * 6) >= 60 ? 600000 : 1800000) : majorH * 3600000;
    const mediumMs = observation && hours <= 4 ? majorMs : majorH <= 3 ? 3600000 : majorMs / 2;
    const minorMs = observation && hours <= 4 ? 600000 : pxPerHour >= 22 ? 3600000 : mediumMs;
    const out = [];
    const seen = new Set();
    const push = (t, kind) => {
      if (t < start - 1 || t > end + 1) return;
      const k = String(t);
      if (seen.has(k)) return;
      seen.add(k);
      const pct = ((t - start) / (end - start)) * 100;
      const d = wibDate(t);
      const isMidnight = d.getUTCHours() === 0 && d.getUTCMinutes() === 0;
      out.push({
        t,
        kind,
        pct,
        label:
          kind === 'major'
            ? isMidnight
              ? wibDateLabel(t)
              : wibTimeLabel(t)
            : '',
      });
    };
    for (let t = alignWib(start, majorMs); t <= end + majorMs; t += majorMs) push(t, 'major');
    for (let t = alignWib(start, mediumMs); t <= end + mediumMs; t += mediumMs) push(t, 'medium');
    for (let t = alignWib(start, minorMs); t <= end + minorMs; t += minorMs) push(t, 'minor');
    out.sort((a, b) => a.t - b.t || rank(b.kind) - rank(a.kind));
    const majors = out.filter((x) => x.kind === 'major' && x.label);
    let lastX = -999;
    for (const m of majors) {
      const x = (m.pct / 100) * width;
      if (x - lastX < 52) {
        m.label = '';
        continue;
      }
      lastX = x;
    }
    return out;
  }

  function rank(kind) {
    if (kind === 'major') return 3;
    if (kind === 'medium') return 2;
    return 1;
  }

  function pctFromEvent(e) {
    const el = trackEl;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const x = ('clientX' in e ? e.clientX : e.touches?.[0]?.clientX) ?? 0;
    return Math.max(0, Math.min(1, (x - r.left) / r.width));
  }

  function seekPct(pct) {
    if (!steps.length) return;
    const t = t0 + pct * span;
    onSeek?.(nearest(steps, t));
  }

  function onPointerDown(e) {
    if (disabled || !steps.length) return;
    e.preventDefault();
    dragging = true;
    dragPct = pctFromEvent(e);
    onPause?.();
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }

  function onPointerMove(e) {
    if (!dragging) return;
    dragPct = pctFromEvent(e);
    const t = t0 + dragPct * span;
    const step = nearest(steps, t);
    if (step && step.token !== selectedToken) onSeek?.(step);
  }

  function onPointerUp(e) {
    if (!dragging) return;
    const pct = pctFromEvent(e);
    dragging = false;
    dragPct = null;
    seekPct(pct);
  }

  function pickDate(entry) {
    dateOpen = false;
    const day = entry.key;
    const same = steps.filter((s) => wibDateKey(s.t) === day);
    if (!same.length) return;
    const hour = selected ? wibDate(selected.t).getUTCHours() : 12;
    const target = same.reduce((best, s) => {
      const dh = Math.abs(wibDate(s.t).getUTCHours() - hour);
      const bh = Math.abs(wibDate(best.t).getUTCHours() - hour);
      return dh < bh ? s : best;
    }, same[0]);
    onSeek?.(target);
  }

  function onKey(e) {
    if (disabled) return;
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      onPrev?.();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      onNext?.();
    } else if (e.key === ' ') {
      e.preventDefault();
      playing ? onPause?.() : onPlay?.();
    }
  }

  onMount(() => {
    reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) trackW = w;
    });
    if (trackEl) ro.observe(trackEl);
    const onDoc = (e) => {
      if (!dateOpen) return;
      if (!e.target.closest?.('.ft-datewrap')) dateOpen = false;
    };
    document.addEventListener('pointerdown', onDoc);
    return () => {
      ro.disconnect();
      document.removeEventListener('pointerdown', onDoc);
    };
  });

  onDestroy(() => {
    dragging = false;
  });
</script>

<div
  class="ft"
  class:ft-disabled={disabled || !steps.length}
  class:ft-reduced={reducedMotion}
  tabindex="0"
  role="slider"
  aria-label={observation ? 'Timeline satelit' : 'Timeline prakiraan'}
  aria-valuemin={0}
  aria-valuemax={Math.max(0, steps.length - 1)}
  aria-valuenow={Math.max(0, steps.findIndex((s) => s.token === selectedToken))}
  onkeydown={onKey}
>
  <div class="ft-meta">
    <div class="ft-model">{modelTitle || 'NWP'}</div>
    <div class="ft-times">
      {#if daily}
        <span>Agregasi harian · WIB</span>
        <span>Interval {selected?.label || '—'}</span>
      {:else}
        {#if !observation}<span>Run {wibShort(runTime)}</span>{/if}
        <span>{observation ? 'Citra' : 'Valid'} {selected ? wibShort(selected.t) : '—'}{observation ? ' WIB' : ''}</span>
      {/if}
    </div>
  </div>
  <div class="ft-controls">
    <button type="button" class="ft-btn" title="Sebelumnya" aria-label="Sebelumnya" onclick={() => onPrev?.()} disabled={disabled || steps.length < 2}>
      <ChevronLeft size={18} strokeWidth={2.2} />
    </button>
    <button
      type="button"
      class="ft-btn ft-play"
      class:on={playing}
      title={playing ? 'Jeda' : 'Putar'}
      aria-label={playing ? 'Jeda' : 'Putar'}
      onclick={() => (playing ? onPause?.() : onPlay?.())}
      disabled={disabled || steps.length < 2}
    >
      {#if playing}
        <Pause size={16} strokeWidth={2.4} />
      {:else}
        <Play size={16} strokeWidth={2.4} />
      {/if}
    </button>
    <div class="ft-datewrap">
      <button
        type="button"
        class="ft-date"
        title="Pilih tanggal valid"
        onclick={() => (dateOpen = !dateOpen)}
        disabled={disabled || !dates.length}
      >
        <CalendarDays size={14} strokeWidth={2.2} />
        <span>{selected ? wibDateLabel(selected.t) : '—'}</span>
      </button>
      {#if dateOpen}
        <div class="ft-dates" role="listbox">
          {#each dates as d}
            <button
              type="button"
              class="ft-date-item"
              class:on={selected && wibDateKey(selected.t) === d.key}
              onclick={() => pickDate(d)}
            >
              {d.label}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <div class="ft-ruler">
    <div
      class="ft-track"
      bind:this={trackEl}
      role="presentation"
      onpointerdown={onPointerDown}
      onpointermove={onPointerMove}
      onpointerup={onPointerUp}
      onpointercancel={onPointerUp}
    >
      <div class="ft-progress" style="width: {headPct}%"></div>
      {#each ticks as tick}
        <span
          class="ft-tick ft-tick-{tick.kind}"
          style="left: {tick.pct}%"
        ></span>
        {#if tick.label}
          <span class="ft-lab" style="left: {tick.pct}%">{tick.label}</span>
        {/if}
      {/each}
      {#each steps as s}
        <span class="ft-dot" style="left: {((s.t - t0) / span) * 100}%"></span>
      {/each}
      <div class="ft-head" style="left: {headPct}%" class:drag={dragging}>
        <div class="ft-tip">{hoverStep ? (daily ? `${hoverStep.label} WIB` : wibFullLabel(hoverStep.t)) : ''}</div>
        <span class="ft-knob"></span>
      </div>
    </div>
  </div>

  <button type="button" class="ft-btn" title="Berikutnya" aria-label="Berikutnya" onclick={() => onNext?.()} disabled={disabled || steps.length < 2}>
    <ChevronRight size={18} strokeWidth={2.2} />
  </button>
  <button
    type="button"
    class="ft-loop"
    class:on={loop}
    title={loop ? 'Loop nyala' : 'Loop mati'}
    aria-label="Loop"
    aria-pressed={loop}
    onclick={() => onLoop?.(!loop)}
    disabled={disabled || steps.length < 2}
  >
    <span class="ft-switch" class:on={loop} aria-hidden="true">
      <span class="ft-switch-knob"></span>
    </span>
    <span>Loop</span>
  </button>
</div>

<style>
  .ft {
    position: absolute;
    left: 16px;
    right: 16px;
    bottom: calc(var(--meteogram-visible-height, 0px) + 16px);
    z-index: 35;
    display: flex;
    align-items: center;
    gap: 10px;
    height: 72px;
    padding: 8px 12px 10px;
    border-radius: 20px;
    background: rgba(15, 23, 42, 0.35);
    backdrop-filter: blur(24px) saturate(160%);
    -webkit-backdrop-filter: blur(24px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
    color: #e2e8f0;
    outline: none;
    font-family: Inter, system-ui, sans-serif;
  }
  .ft:focus-visible {
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 0 0 2px rgba(79, 140, 255, 0.55);
  }
  .ft-disabled {
    opacity: 0.55;
    pointer-events: none;
  }
  .ft-meta {
    flex-shrink: 0;
    min-width: 0;
    max-width: 210px;
    line-height: 1.2;
    padding-right: 4px;
  }
  .ft-model {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ft-times {
    display: flex;
    flex-direction: column;
    gap: 1px;
    margin-top: 3px;
    font-size: 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: rgba(226, 232, 240, 0.78);
    white-space: nowrap;
  }
  .ft-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
  .ft-btn {
    width: 34px;
    height: 34px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.08);
    color: #f8fafc;
    display: grid;
    place-items: center;
    cursor: pointer;
  }
  .ft-btn:hover {
    background: rgba(255, 255, 255, 0.16);
  }
  .ft-play.on {
    background: #4f8cff;
    border-color: #4f8cff;
    color: #fff;
  }
  .ft-loop {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 34px;
    padding: 0 10px 0 8px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 650;
    cursor: pointer;
    flex-shrink: 0;
  }
  .ft-loop:hover {
    background: rgba(255, 255, 255, 0.16);
  }
  .ft-loop.on {
    color: #fff;
    border-color: rgba(79, 140, 255, 0.55);
    background: rgba(79, 140, 255, 0.22);
  }
  .ft-switch {
    width: 28px;
    height: 16px;
    border-radius: 99px;
    background: rgba(148, 163, 184, 0.45);
    position: relative;
    flex-shrink: 0;
  }
  .ft-switch.on {
    background: #4f8cff;
  }
  .ft-switch-knob {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 12px;
    height: 12px;
    border-radius: 99px;
    background: #fff;
    transition: transform 140ms ease-out;
  }
  .ft-switch.on .ft-switch-knob {
    transform: translateX(12px);
  }
  .ft-reduced .ft-switch-knob {
    transition: none;
  }
  .ft-datewrap {
    position: relative;
  }
  .ft-date {
    height: 34px;
    padding: 0 10px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.08);
    color: #f8fafc;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
  }
  .ft-date:hover {
    background: rgba(255, 255, 255, 0.16);
  }
  .ft-dates {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    min-width: 112px;
    max-height: 220px;
    overflow: auto;
    padding: 6px;
    border-radius: 12px;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.16);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
    display: flex;
    flex-direction: column;
    gap: 2px;
    z-index: 2;
  }
  .ft-date-item {
    text-align: left;
    padding: 6px 8px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: #e2e8f0;
    font-size: 12px;
    cursor: pointer;
  }
  .ft-date-item:hover,
  .ft-date-item.on {
    background: rgba(79, 140, 255, 0.28);
  }
  .ft-ruler {
    flex: 1;
    min-width: 0;
    height: 44px;
  }
  .ft-track {
    position: relative;
    height: 44px;
    cursor: pointer;
    touch-action: none;
    user-select: none;
  }
  .ft-track::before {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: 10px;
    height: 2px;
    background: rgba(226, 232, 240, 0.18);
    pointer-events: none;
  }
  .ft-progress {
    position: absolute;
    left: 0;
    top: 10px;
    height: 2px;
    background: rgba(79, 140, 255, 0.85);
    pointer-events: none;
  }
  .ft-tick {
    position: absolute;
    top: 10px;
    width: 1px;
    background: rgba(226, 232, 240, 0.28);
    transform: translateX(-0.5px);
    pointer-events: none;
  }
  .ft-tick-minor {
    height: 9px;
  }
  .ft-tick-medium {
    height: 16px;
    background: rgba(226, 232, 240, 0.42);
  }
  .ft-tick-major {
    height: 24px;
    background: rgba(248, 250, 252, 0.7);
  }
  .ft-lab {
    position: absolute;
    top: 36px;
    transform: translateX(-50%);
    font-size: 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: rgba(226, 232, 240, 0.78);
    white-space: nowrap;
    pointer-events: none;
  }
  .ft-dot {
    position: absolute;
    top: 8px;
    width: 4px;
    height: 4px;
    border-radius: 99px;
    background: rgba(148, 163, 184, 0.9);
    transform: translateX(-2px);
    pointer-events: none;
  }
  .ft-head {
    position: absolute;
    top: 0;
    transform: translateX(-50%);
    pointer-events: none;
    z-index: 1;
  }
  .ft:not(.ft-reduced) .ft-head {
    transition: left 160ms ease-out;
  }
  .ft-head.drag {
    transition: none;
  }
  .ft-knob {
    display: block;
    width: 14px;
    height: 14px;
    margin-top: 4px;
    border-radius: 99px;
    background: #4f8cff;
    border: 2px solid #fff;
    box-shadow: 0 0 0 4px rgba(79, 140, 255, 0.28), 0 2px 8px rgba(15, 23, 42, 0.35);
  }
  .ft-tip {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translate(-50%, -6px);
    padding: 4px 8px;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #f8fafc;
    font-size: 11px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
  }
  .ft-head.drag .ft-tip,
  .ft-track:hover .ft-head .ft-tip {
    opacity: 1;
  }
  @media (max-width: 720px) {
    .ft {
      height: 64px;
      gap: 6px;
      padding: 6px 8px 8px;
      border-radius: 18px;
    }
    .ft-meta {
      max-width: 92px;
    }
    .ft-times {
      display: none;
    }
    .ft-loop span:last-child {
      display: none;
    }
    .ft-loop {
      padding: 0 8px;
    }
    .ft-date span {
      display: none;
    }
    .ft-lab {
      font-size: 9px;
    }
  }
</style>
