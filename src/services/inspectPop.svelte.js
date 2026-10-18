/** Shared inspect popup state — Svelte 5 runes, live across MapLibre mount(). */
export const inspectPop = $state({
  loading: false,
  data: null,
  error: null,
});
