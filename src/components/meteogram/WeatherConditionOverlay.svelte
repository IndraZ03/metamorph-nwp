<script>
  import { weatherIconSvg } from './weatherIcons.js';
  let { icons = [] } = $props();
</script>

{#if icons.length}
  <div class="conditions">
    {#each icons as icon (icon.x)}
      <svg class="wx" style:left={`${icon.x}px`} style:top={`${icon.y}px`} viewBox="0 0 24 24"
        role="img" aria-label={icon.label}>{@html weatherIconSvg(icon.id)}</svg>
    {/each}
  </div>
{/if}

<style>
  .conditions { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
  .wx { position: absolute; width: 22px; height: 22px; transform: translate(-50%, -100%); color: var(--mg-text); }
</style>
