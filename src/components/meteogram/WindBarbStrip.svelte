<script>
  let { samples = [], width = 600 } = $props();
  function barb(speed) {
    let knots = Math.round(speed * 1.943844 / 5) * 5;
    let y = -18, path = 'M0 0V-18', flags = [];
    while (knots >= 50) { flags.push(`0,${y} 7,${y + 3} 0,${y + 6}`); y += 7; knots -= 50; }
    while (knots >= 10) { path += `M0 ${y}l7 -3`; y += 4; knots -= 10; }
    if (knots >= 5) path += `M0 ${y}l4 -2`;
    return { path, flags };
  }
</script>
{#if samples.some(s => Number.isFinite(s.point.windDirectionDeg))}
  <div class="strip"><span>Angin FROM · ½ garis 5 kt · garis 10 kt · bendera 50 kt</span>
    <svg viewBox={`0 0 ${width} 42`} width="100%" height="42" role="img" aria-label="Wind barbs sejajar waktu grafik; angka lengkap pada tabel">
      {#each samples as s}{#if Number.isFinite(s.point.windSpeedMs) && Number.isFinite(s.point.windDirectionDeg)}
        {@const b = barb(s.point.windSpeedMs)}<g transform={`translate(${s.x},28) rotate(${s.point.windDirectionDeg})`}><path d={b.path} fill="none" stroke="currentColor" stroke-width="1.2"/>{#each b.flags as flag}<polygon points={flag} fill="currentColor"/>{/each}</g>
      {/if}{/each}
    </svg>
  </div>
{/if}
<style>.strip { color:var(--mg-muted); font-size:10px; border-top:1px solid var(--mg-border); } span { padding-left:16px; }</style>
