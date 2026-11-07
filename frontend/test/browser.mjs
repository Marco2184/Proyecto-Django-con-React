import {test,before,after} from 'node:test'
import assert from 'node:assert/strict'
import {spawn,execFileSync} from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {chromium} from 'playwright'
import {dict} from '../src/i18n.js'
import {cents,assertReceiptTotals} from './receipt.mjs'

const frontend=fileURLToPath(new URL('../',import.meta.url)),root=path.dirname(frontend.replace(/[\\/]$/,''))
const children=[];let browser
const env={...process.env,DJANGO_SETTINGS_MODULE:'monolith.test_settings',MONOLITH_BROWSER_TEST:'1',PYTHONDONTWRITEBYTECODE:'1',SECRET_KEY:'ci-only-django-secret-000000000000000000000000000',JWT_SHARED_SECRET:'ci-only-shared-secret-00000000000000000000000',TEST_JWT_SHARED_SECRET:'ci-only-shared-secret-00000000000000000000000',JWT_REFRESH_SECRET:'ci-only-refresh-secret-0000000000000000000000',MONGO_URI:'',PORT:'4000',DJANGO_API_URL:'http://127.0.0.1:8000/api',ALLOWED_ORIGINS:'http://127.0.0.1:3000',COOKIE_SECURE:'false',COOKIE_SAME_SITE:'lax',VITE_API_URL:'/api',VITE_AUTH_API_URL:'/',VITE_CATALOG_API_URL:'/catalog-service/api'}
const base='http://127.0.0.1:3000',password='BrowserFixture!78419'
function start(command,args,cwd){const p=spawn(command,args,{cwd,env,stdio:'ignore',windowsHide:true});children.push(p);return p}
async function waitFor(url){for(let i=0;i<100;i++){if(children.some(p=>p.exitCode!==null))throw Error('Isolated test server exited');try{if((await fetch(url,{signal:AbortSignal.timeout(1000)})).ok)return}catch{}await new Promise(r=>setTimeout(r,100))}throw Error('Local test server did not become ready')}
before(async()=>{
  assert.ok(!fs.existsSync(path.join(root,'.browser-test.sqlite3')),'Remove stale isolated browser DB before rerunning')
  execFileSync(process.execPath,['node_modules/vite/bin/vite.js','build','--configLoader','runner'],{cwd:frontend,env,stdio:'ignore',windowsHide:true})
  const python=process.env.PYTHON||(process.platform==='win32'?path.join(root,'.venv/Scripts/python.exe'):'python')
  start(python,['tests/browser_server.py'],root)
  start(process.execPath,['src/server.js'],path.join(root,'catalog-service'))
  start(process.execPath,['node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port','3000','--strictPort','--configLoader','runner'],frontend)
  await waitFor(base+'/catalog-service/health');await waitFor(base+'/api/productos/')
  browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROME_CHANNEL?{channel:process.env.PLAYWRIGHT_CHROME_CHANNEL}:{})})
}, {timeout:60000})
after(async()=>{
  await browser?.close()
  for(const p of children){if(p.exitCode===null){const ended=new Promise(r=>p.once('exit',r));p.kill();await ended}}
  for(const suffix of ['','-journal','-wal','-shm']){const p=path.join(root,'.browser-test.sqlite3'+suffix);if(fs.existsSync(p))fs.unlinkSync(p)}
})
async function login(page,email){await page.goto(base+'/ingresar');await page.locator('input[type=email]').fill(email);await page.locator('input[type=password]').fill(password);await page.locator('form button[type=submit],form button.btn-neon').click();await page.waitForURL(base+'/');await page.getByRole('navigation').first().waitFor()}
async function noOverflow(page){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),'Page overflows viewport')}
async function authenticated(page,context,route,options={}){
  const token=await page.evaluate(()=>sessionStorage.getItem('jwt_access'))
  assert.ok(token,'Fixture session must exist before authenticated requests')
  return context.request.fetch(base+route,{...options,headers:{Authorization:`Bearer ${token}`,...options.headers}})
}

test('automatic registration, pending verification and persistent wishlist',async()=>{
  const context=await browser.newContext(),page=await context.newPage()
  await page.goto(base+'/registro')
  const inputs=page.locator('form input');await inputs.nth(0).fill('New Browser User');await inputs.nth(1).fill(`browser-${Date.now()}@example.invalid`);await inputs.nth(3).fill(password);await inputs.nth(4).fill(password)
  await page.locator('form button').click();await page.waitForURL(base+'/')
  await page.getByText('Tu correo está pendiente de verificación.',{exact:false}).first().waitFor()
  const heart=page.getByRole('button',{name:'Guardar en mi lista de deseos'}).first();await heart.click();await page.getByRole('button',{name:'Quitar de mi lista de deseos'}).first().waitFor()
  await page.getByRole('link',{name:'Mi lista de deseos'}).click();await page.getByRole('heading',{name:'Mi lista de deseos',exact:true}).waitFor()
  await page.reload();await page.getByRole('heading',{name:'Monolith Test Game',exact:true}).waitFor()
  const token=await page.evaluate(()=>sessionStorage.getItem('jwt_access'))
  const r=await context.request.post(base+'/api/cart/checkout/',{data:{},headers:{Authorization:`Bearer ${token}`}});assert.equal(r.status(),403)
  const stored=await page.evaluate(()=>Object.entries(localStorage));assert.ok(!stored.some(([key,value])=>/password|refresh/i.test(key)))
  const cookies=await context.cookies();assert.ok(cookies.find(c=>c.name==='monolith_refresh')?.httpOnly)
  await context.close()
})

test('product details without reviews, wishlist and keyboard/mobile layouts',async()=>{
  const context=await browser.newContext(),page=await context.newPage();await login(page,'browser-buyer@example.invalid')
  assert.equal((await authenticated(page,context,'/api/wishlist/1/',{method:'DELETE'})).status(),204)
  const reviewRequests=[]
  page.on('request',request=>{if(/\/reviews(?:\/|$)/.test(new URL(request.url()).pathname))reviewRequests.push(request.url())})
  await page.goto(base+'/producto/1');await page.locator('.detail-grid').waitFor()
  assert.equal(await page.locator('.review-panel').count(),0)
  assert.equal(reviewRequests.length,0)
  for(const width of [390,768,1365]){await page.setViewportSize({width,height:900});await noOverflow(page);await page.locator('a.skip-link').focus();await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>document.activeElement!==document.body))}
  await page.goto(base+'/deseos');await page.getByText('Tu lista de deseos está vacía.',{exact:true}).waitFor()
  await context.close()
})

test('existing admin panel plus analytics, inventory and promotions',async()=>{
  const context=await browser.newContext(),page=await context.newPage();await login(page,'browser-admin@example.invalid')
  await page.goto(base+'/admin');await page.getByRole('heading',{name:'Análisis de ventas',exact:true}).waitFor()
  await page.locator('svg.sales-chart').waitFor()
  for(const label of ['Productos','Pedidos','Usuarios','Movimientos de inventario','Promociones y cupones']){await page.locator('.admin-tabs').getByRole('button',{name:label,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.admin-loading'));assert.equal(await page.locator('.admin-page .alert-error').count(),0)}
  for(const width of [390,768,1365]){await page.setViewportSize({width,height:900});await noOverflow(page)}
  await page.getByRole('button',{name:'Cambiar idioma'}).click();await page.getByRole('heading',{name:'Promotions and coupons'}).waitFor()
  await context.close()
})

test('price drop notification and verified checkout use live backend amounts',async()=>{
  const context=await browser.newContext(),page=await context.newPage();await login(page,'browser-buyer@example.invalid')
  const me=await authenticated(page,context,'/api/auth/me/');assert.equal(me.status(),200);assert.equal((await me.json()).email_verificado,true)
  assert.equal((await authenticated(page,context,'/api/cart/clear/',{method:'POST',data:{}})).status(),200)
  assert.equal((await authenticated(page,context,'/api/wishlist/1/',{method:'DELETE'})).status(),204)
  const beforePrice=await authenticated(page,context,'/api/productos/1/');assert.equal(beforePrice.status(),200)
  const originalProduct=await beforePrice.json()
  const oldCents=cents(originalProduct.precio);assert.ok(oldCents>1,'The isolated game needs a positive price that can be reduced')
  const reducedPrice=(Math.max(1,Math.floor(oldCents*.95))/100).toFixed(2)
  // Re-fetch the UI so the heart reflects the fixture cleanup, not stale state.
  await page.reload()
  await page.getByRole('button',{name:dict.es.saveWish}).first().click();await page.getByRole('button',{name:dict.es.removeWish}).first().waitFor()
  await page.getByRole('link',{name:dict.es.wishlist}).click();await page.getByRole('heading',{name:'Monolith Test Game',exact:true}).waitFor()
  const loginResponse=await fetch(base+'/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:'browser-admin@example.invalid',password})})
  assert.equal(loginResponse.status,200);const admin=(await loginResponse.json()).access
  const changed=await fetch(base+'/api/admin/products/1/',{method:'PATCH',headers:{'content-type':'application/json',Authorization:`Bearer ${admin}`},body:JSON.stringify({precio:reducedPrice})});assert.equal(changed.status,200)
  const updatedProduct=await changed.json();assert.ok(cents(updatedProduct.precio)<oldCents)
  await page.getByRole('button',{name:dict.es.refreshStatus,exact:true}).click();await page.getByRole('button',{name:dict.es.markRead}).waitFor()
  await page.getByRole('button',{name:dict.es.refreshStatus,exact:true}).click();assert.equal(await page.getByRole('button',{name:dict.es.markRead}).count(),1)
  const notices=await authenticated(page,context,'/api/wishlist/');assert.equal(notices.status(),200)
  const notifications=(await notices.json()).notifications
  assert.equal(notifications.length,1);assert.equal(notifications[0].precio_anterior,originalProduct.precio);assert.equal(notifications[0].precio_actual,updatedProduct.precio)
  const added=page.waitForResponse(r=>r.url().endsWith('/api/cart/add/')&&r.request().method()==='POST')
  await page.getByRole('button',{name:dict.es.addCart,exact:true}).click()
  assert.equal((await added).status(),200)
  const coupon=await authenticated(page,context,'/api/cart/aplicar-cupon/',{method:'POST',data:{codigo:'MONOLITH10'}});assert.equal(coupon.status(),200,JSON.stringify(await coupon.json()))
  const calculatedCart=await coupon.json();assert.equal(calculatedCart.cantidad_items,1)
  assert.equal(cents(calculatedCart.subtotal),cents(updatedProduct.precio));assert.ok(cents(calculatedCart.descuento)>0)
  assert.equal(cents(calculatedCart.total),cents(calculatedCart.subtotal)-cents(calculatedCart.descuento))
  // Reproduce the Docker prerequisite: checkout has already saved an address.
  let addresses=await authenticated(page,context,'/api/profile/addresses/');assert.equal(addresses.status(),200)
  let saved=await addresses.json();saved=Array.isArray(saved)?saved:saved.results
  if(!saved.length){const created=await authenticated(page,context,'/api/profile/addresses/',{method:'POST',data:{calle:'Dirección guardada de prueba',ciudad:'Lima',departamento:'Lima',codigo_postal:'15001',predeterminada:true}});assert.equal(created.status(),201)}
  const addressLoaded=page.waitForResponse(r=>r.url().endsWith('/api/profile/addresses/')&&r.request().method()==='GET')
  const cartLoaded=page.waitForResponse(r=>r.url().endsWith('/api/cart/')&&r.request().method()==='GET')
  await page.goto(base+'/checkout')
  assert.equal((await addressLoaded).status(),200);assert.equal((await cartLoaded).status(),200)
  await page.getByRole('heading',{name:dict.es.shippingAddress,exact:true}).waitFor()
  assert.equal(await page.getByRole('radio',{name:dict.es.useSavedAddress,exact:true}).isChecked(),true)
  assert.equal(await page.getByLabel(dict.es.street,{exact:true}).count(),0,'Saved-address mode correctly hides new-address inputs')
  await page.getByRole('radio',{name:dict.es.newAddress,exact:true}).check()
  await page.getByLabel(dict.es.street,{exact:true}).fill('Calle temporal 123');await page.getByLabel(dict.es.city,{exact:true}).fill('Lima');await page.getByLabel(dict.es.postalCode,{exact:true}).fill('15001')
  const inventoryBefore=await(await authenticated(page,context,'/api/productos/1/')).json()
  const response=page.waitForResponse(r=>r.url().endsWith('/api/cart/checkout/')&&r.request().method()==='POST')
  await page.getByRole('button',{name:dict.es.payAndConfirm,exact:true}).click()
  const receipt=await response;assert.equal(receipt.status(),201)
  const purchase=await receipt.json(),sent=receipt.request(),sentHeaders=sent.headers()
  assert.equal(purchase.pedido.monto_total,calculatedCart.total);assert.equal(purchase.pedido.descuento,calculatedCart.descuento)
  const after=await(await authenticated(page,context,'/api/productos/1/')).json();assert.equal(after.stock,inventoryBefore.stock-calculatedCart.cantidad_items)
  const replay=await authenticated(page,context,'/api/cart/checkout/',{method:'POST',data:JSON.parse(sent.postData()),headers:{'Idempotency-Key':sentHeaders['idempotency-key']}})
  assert.equal(replay.status(),200);assert.equal((await replay.json()).pedido.id,purchase.pedido.id)
  assert.equal((await(await authenticated(page,context,'/api/productos/1/')).json()).stock,after.stock,'Replay must not deduct stock twice')
  const invoice=await authenticated(page,context,`/api/profile/orders/${purchase.pedido.id}/receipt/`);assert.equal(invoice.status(),200)
  assertReceiptTotals(await invoice.body(),{subtotal:calculatedCart.subtotal,discount:calculatedCart.descuento,total:calculatedCart.total})
  const movementResponse=await fetch(base+'/api/admin/inventory/?producto_id=1',{headers:{Authorization:`Bearer ${admin}`}});assert.equal(movementResponse.status,200)
  const saleMovements=(await movementResponse.json()).results.filter(m=>m.pedido===purchase.pedido.id&&m.tipo==='venta')
  assert.equal(saleMovements.length,1);assert.equal(saleMovements[0].cantidad,-calculatedCart.cantidad_items)
  await page.waitForURL(/\/pedidos\/\d+\/confirmado/)
  for(const width of [390,768,1365]){await page.setViewportSize({width,height:900});await noOverflow(page)}
  await context.close()
})

test('slow wishlist shows loading and recovers from a controlled network error',async()=>{
  const context=await browser.newContext(),page=await context.newPage();await login(page,'browser-buyer@example.invalid')
  const setup=await authenticated(page,context,'/api/wishlist/1/',{method:'PUT'});assert.ok([200,201].includes(setup.status()))
  await page.route('**/api/wishlist/sync/**',async route=>{await new Promise(r=>setTimeout(r,700));await route.continue()})
  await page.goto(base+'/deseos');await page.locator('.panel-page [role=status]').first().waitFor()
  await page.getByRole('heading',{name:'Monolith Test Game',exact:true}).waitFor()
  await page.unroute('**/api/wishlist/sync/**')
  await page.route('**/api/wishlist/sync/**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Servicio temporalmente no disponible.'})}))
  await page.getByRole('button',{name:dict.es.refreshStatus,exact:true}).click();await page.getByRole('alert').first().waitFor()
  await page.unroute('**/api/wishlist/sync/**');await page.getByRole('button',{name:dict.es.refreshStatus,exact:true}).click()
  await page.waitForFunction(()=>!document.querySelector('[role=alert]'))
  await context.close()
})
