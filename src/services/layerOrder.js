export const DEFAULT_LAYER_ORDER = ['nwp', 'spartan', 'satellite', 'radar', 'landslide', 'flood'];

export function moveActiveLayer(order, active, kind, direction) {
  const visible = order.filter(id => active.includes(id));
  const index = visible.indexOf(kind);
  const neighbor = visible[index + direction];
  if (index < 0 || !neighbor) return order;
  const next = [...order];
  const from = next.indexOf(kind), to = next.indexOf(neighbor);
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}

export function applyLayerOrder(map, order, before, inariskOwner) {
  const groups = {
    radar: ['radar-layer'], satellite: ['satellite-layer'], spartan: ['spartan-layer'],
    nwp: ['nwp-layer', 'nwp-layer-b', 'nwp-sea-mask', 'nwp-sea-mask-b'],
    landslide: ['landslide-layer', 'landslide-sea-mask'], flood: ['flood-layer'],
  };
  for (const kind of order) {
    const ids = [...(kind === inariskOwner ? ['inarisk-layer'] : []), ...(groups[kind] || [])];
    for (const id of ids) if (map.getLayer(id)) map.moveLayer(id, before);
  }
}
