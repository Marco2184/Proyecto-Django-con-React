import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';

async function fixture(fn) {
  const server = createApp({backendUrl:'http://localhost:8000/api',
    fetchImpl: async url => {fn(url); return new Response('{"count":1,"results":[]}', {headers:{'content-type':'application/json'}});} }).listen(0,'127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  return {base:`http://127.0.0.1:${server.address().port}`, close:() => new Promise(resolve=>server.close(resolve))};
}
test('health devuelve estado operativo',async()=>{
  const f=await fixture(()=>{});try {const r=await fetch(f.base+'/health');assert.equal(r.status,200);assert.equal((await r.json()).status,'ok');} finally {await f.close()}
});
test('busqueda conserva parametros y apunta a Django',async()=>{
  let seen;const f=await fixture(url=>seen=url);try {
    const r=await fetch(f.base+'/api/productos/buscar/?q=halo');
    assert.equal(r.status,200);assert.equal(seen.pathname,'/api/productos/buscar/');assert.equal(seen.searchParams.get('q'),'halo');
  }finally {await f.close()}
});
test('no permite ID de producto no numerico',async()=>{
  const f=await fixture(()=>{});try {const r=await fetch(f.base+'/api/productos/abc/');assert.equal(r.status,400);}finally {await f.close()}
});
