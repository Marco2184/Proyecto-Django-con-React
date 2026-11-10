import test from 'node:test';
import assert from 'node:assert/strict';
import { createCoalescedFetch } from '../src/singleFlight.js';

test('comparte una consulta simultanea', async () => {
  const sharedFetch = createCoalescedFetch();
  let llamadas = 0;

  const fetcher = async () => {
    llamadas++;
    await new Promise(resolve => setTimeout(resolve, 50));

    return new Response(
      JSON.stringify({ resultado: 'correcto' }),
      { status: 200 }
    );
  };

  const respuestas = await Promise.all([
    sharedFetch('categorias', fetcher),
    sharedFetch('categorias', fetcher),
    sharedFetch('categorias', fetcher)
  ]);

  assert.equal(llamadas, 1);

  for (const respuesta of respuestas) {
    assert.deepEqual(await respuesta.json(), {
      resultado: 'correcto'
    });
  }
});

test('permite reintentar despues de un error', async () => {
  const sharedFetch = createCoalescedFetch();
  let intentos = 0;

  const fetcher = async () => {
    intentos++;

    if (intentos === 1) {
      throw new Error('Django temporalmente no disponible');
    }

    return new Response('OK', { status: 200 });
  };

  await assert.rejects(
    sharedFetch('plataformas', fetcher)
  );

  const respuesta = await sharedFetch('plataformas', fetcher);

  assert.equal(respuesta.status, 200);
  assert.equal(await respuesta.text(), 'OK');
  assert.equal(intentos, 2);
});

test('mantiene separadas las claves de consulta', async () => {
  const sharedFetch = createCoalescedFetch();
  let llamadas = 0;

  const fetcher = async () => {
    llamadas++;
    return new Response('OK');
  };

  await Promise.all([
    sharedFetch('categorias:es', fetcher),
    sharedFetch('categorias:en', fetcher)
  ]);

  assert.equal(llamadas, 2);
});
