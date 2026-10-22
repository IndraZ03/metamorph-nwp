<script>
  import { onMount, untrack } from 'svelte';
  import { buildMeteogramOptions, nearestPoint } from '../services/meteogram/chart.js';
  import MeteogramTooltip from './MeteogramTooltip.svelte';
  import WindBarbStrip from './meteogram/WindBarbStrip.svelte';
  import WeatherConditionOverlay from './meteogram/WeatherConditionOverlay.svelte';

  let { series = null, activeTime = null, onSelectTime } = $props();
  let host;
  let chart;
  let ready = $state(false);
  let chartError = $state(null);
  let hovered = $state(null);
  let cursorX = $state(null);
  let samples = $state([]);
  let icons = $state([]);
  let width = $state(600);
  let frame = 0;
  const points = $derived(series?.points || []);

  function align() {
    if (!chart || !points.length) return;
    width = chart.getWidth();
    let previousSample = -Infinity;
    let previousIcon = -Infinity;
    const nextSamples = [];
    const nextIcons = [];
    for (const point of points) {
      const x = chart.convertToPixel({ xAxisIndex: 0 }, point.t);
      if (!Number.isFinite(x)) continue;
      if (x - previousSample >= 44) { previousSample = x; nextSamples.push({ x, point }); }
      // Icons sit above the temperature curve; no temperature means no icon.
      if (!point.weatherCondition || !Number.isFinite(point.temperatureC)) continue;
      if (x - previousIcon < 36) continue;
      const y = chart.convertToPixel({ xAxisIndex: 0, yAxisIndex: 0 }, [point.t, point.temperatureC]);
      if (!Array.isArray(y) || !Number.isFinite(y[1])) continue;
      previousIcon = x;
      nextIcons.push({ x, y: y[1] - 14, id: point.weatherCondition.id, label: point.weatherCondition.label });
    }
    samples = nextSamples;
    icons = nextIcons;
    const selected = untrack(() => hovered) || nearestPoint(points, activeTime);
    cursorX = selected ? chart.convertToPixel({ xAxisIndex: 0 }, selected.t) : null;
  }
  function pointer(event, commit = false) {
    if (!chart || !points.length) return;
    const coords = [event.offsetX, event.offsetY];
    if (!chart.containPixel({ gridIndex: 0 }, coords)) return;
    const value = chart.convertFromPixel({ xAxisIndex: 0 }, coords[0]);
    const point = nearestPoint(points, value);
    if (!point) return;
    hovered = point;
    cursorX = chart.convertToPixel({ xAxisIndex: 0 }, point.t);
    if (commit) onSelectTime?.(point.t);
  }
  function keyboard(event) {
    if (!points.length) return;
    const current = hovered || nearestPoint(points, activeTime) || points[0];
    let index = points.indexOf(current);
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      index = Math.max(0, Math.min(points.length - 1, index + (event.key === 'ArrowRight' ? 1 : -1)));
      hovered = points[index]; align();
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); onSelectTime?.(current.t);
    }
  }
  $effect(() => {
    const data = points, available = ready;
    if (available) untrack(() => {
      chart.setOption(buildMeteogramOptions(data), { notMerge: true });
      chart.resize(); align();
    });
  });
  $effect(() => {
    const time = activeTime, available = ready, data = points;
    if (available) untrack(() => {
      hovered = nearestPoint(data, time) || data[0] || null;
      cursorX = hovered ? chart.convertToPixel({ xAxisIndex: 0 }, hovered.t) : null;
    });
  });
  onMount(() => {
    let alive = true;
    let observer;
    let move, click;
    async function init() {
      try {
        const [core, charts, components, renderers] = await Promise.all([
          import('echarts/core'), import('echarts/charts'), import('echarts/components'), import('echarts/renderers'),
        ]);
        if (!alive) return;
        core.use([charts.LineChart, charts.CustomChart, components.GridComponent,
          components.LegendComponent, renderers.CanvasRenderer]);
        chart = core.init(host, null, { renderer: 'canvas', useDirtyRect: true });
        move = event => pointer(event);
        click = event => pointer(event, true);
        chart.getZr().on('mousemove', move);
        chart.getZr().on('click', click);
        observer = new ResizeObserver(() => {
          if (frame) cancelAnimationFrame(frame);
          frame = requestAnimationFrame(() => { frame = 0; if (alive) { chart.resize(); align(); } });
        });
        observer.observe(host);
        ready = true;
      } catch (error) { if (alive) chartError = error.message || 'Grafik gagal dimuat'; }
    }
    init();
    return () => {
      alive = false; cancelAnimationFrame(frame); observer?.disconnect();
      if (chart) {
        chart.getZr().off('mousemove', move); chart.getZr().off('click', click); chart.dispose(); chart = null;
      }
    };
  });
</script>

<div class="chart" tabindex="0" role="slider" aria-label="Grafik meteogram. Panah kiri/kanan jelajahi waktu; Enter pilih waktu peta."
  aria-valuemin={0} aria-valuemax={Math.max(0, points.length - 1)}
  aria-valuenow={Math.max(0, points.indexOf(hovered))} aria-valuetext={hovered?.validTime || 'Tidak tersedia'} onkeydown={keyboard}>
  {#if chartError}<p role="alert">{chartError}. Nilai numerik tetap ada pada tooltip.</p>{/if}
  <div class="plot">
    <div bind:this={host} class="canvas"></div>
    <WeatherConditionOverlay {icons}/>
    {#if Number.isFinite(cursorX)}<div class="crosshair" style:left={`${cursorX}px`}></div>{/if}
    {#if hovered}<MeteogramTooltip point={hovered} modelTitle={series?.modelTitle} x={cursorX}/>{/if}
  </div>
  <WindBarbStrip {samples} {width}/>
</div>
<style>
  .chart { display: flex; flex-direction: column; width: 100%; height: 100%; min-width: 0; min-height: 0; }
  .chart:focus-visible { outline: 2px solid var(--mg-text); outline-offset: -2px; }
  .plot { position: relative; flex: 1; min-height: 0; width: 100%; }
  .canvas { position: absolute; inset: 0; }
  .crosshair { position: absolute; top: 52px; bottom: 44px; border-left: 1px dashed var(--mg-muted); pointer-events: none; }
  p { padding: 0 16px; }
</style>
