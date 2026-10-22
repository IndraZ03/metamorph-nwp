import test from 'node:test';
import assert from 'node:assert/strict';
import { moveActiveLayer, applyLayerOrder } from './layerOrder.js';

test('movement swaps active neighbors and preserves hidden positions', () => {
  const order = ['nwp', 'radar', 'satellite', 'flood'];
  assert.deepEqual(moveActiveLayer(order, ['nwp', 'satellite'], 'nwp', 1), ['satellite', 'radar', 'nwp', 'flood']);
  assert.equal(moveActiveLayer(order, ['nwp'], 'nwp', 1), order);
  assert.equal(moveActiveLayer(order, [], 'nwp', -1), order);
});

test('groups both NWP slots and masks below label anchor, ignores absent layers', () => {
  const stack = ['nwp-layer', 'radar-layer', 'nwp-layer-b', 'nwp-sea-mask', 'labels'];
  const map = {
    getLayer: id => stack.includes(id),
    moveLayer(id, before) { stack.splice(stack.indexOf(id), 1); stack.splice(stack.indexOf(before), 0, id); },
  };
  applyLayerOrder(map, ['radar', 'nwp', 'flood'], 'labels');
  assert.deepEqual(stack, ['radar-layer', 'nwp-layer', 'nwp-layer-b', 'nwp-sea-mask', 'labels']);
});

test('InaRISK stays directly below owning hazard', () => {
  const calls = [];
  const map = { getLayer: () => true, moveLayer: id => calls.push(id) };
  applyLayerOrder(map, ['flood', 'radar', 'landslide'], 'labels', 'flood');
  assert.deepEqual(calls, ['inarisk-layer', 'flood-layer', 'radar-layer', 'landslide-layer', 'landslide-sea-mask']);
});
