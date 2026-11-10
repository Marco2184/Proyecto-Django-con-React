import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';

test('dos solicitudes simultáneas comparten una consulta', async () => {
  let llamadas = 0;

  const fetchImpl = async () => {
    llamadas++;

    await new Promise(resolve => setTimeout(resolve, 100));

    return new Response(
      JSON.stringify([{ id: 1, nombre: 'PC' }]),
      {
        status: 200,
        headers: { 'content-type': 'application/json' }
      }
    );
  };

  const app = createApp({
    fetchImpl,
    cacheTtlMs: 5000,
    allowedOrigins: 'http://localhost:3000'
  });

  const server = app.listen(0);

  try {
    await new Promise(resolve => server.once('listening', resolve));

    const port = server.address().port;
    const url = `http://127.0.0.1:${port}/api/categorias/`;

    const respuestas = await Promise.all([
      fetch(url),
      fetch(url),
      fetch(url)
    ]);

    assert.ok(respuestas.every(r => r.status === 200));

    assert.equal(
      llamadas,
      1,
      'Las solicitudes idénticas deberían compartir una sola consulta'
    );
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});
