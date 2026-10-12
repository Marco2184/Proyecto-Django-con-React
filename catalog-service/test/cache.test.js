import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';

test('cache evita llamadas repetidas al upstream y conserva consulta', async () => {
  let calls = 0;
  const app = createApp({ cacheTtlMs: 10000, fetchImpl: async url => {
    calls++;
    assert.equal(url.searchParams.get('q'), 'zelda');
    return new Response(JSON.stringify({ results: [{ id: 10 }] }), { headers: { 'content-type': 'application/json' } });
  }});
  const server = app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/api/productos/buscar/?q=zelda`;
    const first = await fetch(url);
    assert.equal(first.headers.get('x-catalog-cache'), 'MISS');
    assert.equal((await first.json()).results[0].id, 10);
    const second = await fetch(url);
    assert.equal(second.headers.get('x-catalog-cache'), 'HIT');
    assert.equal(calls, 1);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
