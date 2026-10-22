import test from 'node:test';
import assert from 'node:assert/strict';
import { satelliteLegend } from './satelliteLegend.js';

test('official EH and Visible palettes remain distinct', () => {
  const eh = satelliteLegend({ id: 'himawari9-ir' });
  const vs = satelliteLegend({ id: 'himawari9-vs' });
  assert.equal(eh.stops[0].value, -100);
  assert.equal(eh.stops.at(-1).value, 60);
  assert.equal(eh.stops[0].color, 'rgb(233,63,51)');
  assert.equal(vs.stops[0].value, 1);
  assert.equal(vs.stops.at(-1).value, 0.05);
  assert.equal(satelliteLegend({ id: 'unknown' }), null);
});
