/** Docker-only verification. No production environment files are loaded. */
import assert from 'node:assert/strict'
import {randomUUID,createHash} from 'node:crypto'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {cents,assertReceiptTotals} from '../frontend/test/receipt.mjs'

const root=fileURLToPath(new URL('../',import.meta.url))
const compose=['compose','-p','monolith-verification','-f','compose.verify.yaml']
const base='http://127.0.0.1:13001'
const fixturePassword='BrowserFixture!78419' // Disposable test users only.
const httpOnly=process.argv.includes('--http-only')
const browserOnly=process.argv.includes('--browser-only')
const patternIndex=process.argv.indexOf('--test-name-pattern')
const browserPattern=patternIndex<0?null:process.argv[patternIndex+1]
if(patternIndex>=0)assert.ok(browserPattern,'Provide a browser test name pattern')
const archiveDir=path.join(root,'..','ZIP_conservados')
const archives=new Map()
if(fs.existsSync(archiveDir))for(const name of fs.readdirSync(archiveDir).filter(n=>n.toLowerCase().endsWith('.zip'))){const p=path.join(archiveDir,name);archives.set(p,createHash('sha256').update(fs.readFileSync(p)).digest('hex'))}
let started=false,phase='Docker engine access'

function command(args,{capture=false}={}){
  const result=spawnSync('docker',args,{cwd:root,windowsHide:true,encoding:'utf8',stdio:capture?'pipe':'inherit',maxBuffer:20*1024*1024})
  if(result.error)throw result.error
  if(result.status!==0){if(capture)console.error(result.stderr||'Docker command failed');throw Error(`Docker command failed during ${phase}`)}
  return result.stdout||''
}
const dc=(args,options)=>command([...compose,...args],options)
function pass(label,condition){assert.ok(condition,label);console.log(`PASS: ${label}`)}
async function request(route,{method='GET',data,token,cookie}={}){
  const headers={Origin:base}
  if(data!==undefined)headers['content-type']='application/json'
  if(token)headers.Authorization=`Bearer ${token}`
  if(cookie)headers.Cookie=cookie
  const r=await fetch(base+route,{method,headers,body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(35000)})
  const text=await r.text();let json;try{json=JSON.parse(text)}catch{}
  return {status:r.status,headers:r.headers,text,data:json}
}
async function login(email){
  const r=await request('/auth/login',{method:'POST',data:{email,password:fixturePassword}})
  pass('Node -> Django login '+email,r.status===200&&!!r.data.access)
  return {token:r.data.access,cookie:r.headers.get('set-cookie')?.split(';')[0],user:r.data.user}
}
function logs(){
  const text=dc(['logs','--no-color','--tail','200','django','node','frontend','postgres-test','mongo'],{capture:true})
  const failures=text.split(/\r?\n/).filter(l=>/Traceback|Internal Server Error|\bERROR\b|API failure|Unhandled/i.test(l))
  if(failures.length){
    for(const line of failures)console.error(line.replace(/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[TOKEN]').replace(/postgres(?:ql)?:\/\/\S+/gi,'[DATABASE URL]'))
    throw Error('Review the Docker service errors printed above')
  }
  console.log('PASS: no unexpected errors in the last 200 log lines per service')
  if(/Firebase no configurado/.test(text))console.log('NOTE: Firebase is not configured; Node/Django authentication is used.')
}

try{
  if(!httpOnly){
    command(['info','--format','Docker engine {{.ServerVersion}}'])
    phase='isolated Compose validation';dc(['config','--quiet'])
    phase='Docker image builds';dc(['build','django','node','frontend'])
    phase='isolated Compose startup';started=true;dc(['up','-d','--no-build','--wait','--wait-timeout','240'])
  }else console.log('ATTACH MODE: testing the existing isolated Docker HTTP services; Docker API, builds, container unit tests and logs are not checked.')
  phase='isolation guard'
  const marker=await request('/api/__verification__/')
  pass('HTTP tests target only disposable PostgreSQL',marker.status===200&&marker.data?.mode==='monolith-docker-verification'&&marker.data?.database==='monolith_verification'&&marker.data?.engine==='postgresql')
  if(!httpOnly&&!browserOnly){phase='backend unit and concurrent PostgreSQL tests';dc(['--profile','checks','run','--rm','--no-deps','tests'])}
  if(!browserOnly){
  phase='Nginx and service communication'
  pass('React frontend served by Nginx',(await request('/')).text.includes('id="root"'))
  pass('React/Nginx -> Node health',(await request('/catalog-service/health')).status===200)
  const catalog=await request('/catalog-service/api/productos/')
  pass('React/Nginx -> Node -> Django -> PostgreSQL catalog',catalog.status===200&&catalog.data.results?.length>0)
  const product=catalog.data.results.find(p=>p.nombre==='Monolith Test Game');assert.ok(product)
  for(const [url,label] of [['http://127.0.0.1:18001/','Django direct'],['http://127.0.0.1:14001/health','Node direct']])pass(label,(await fetch(url,{signal:AbortSignal.timeout(10000)})).ok)

  phase='automatic registration'
  const registrationKey=randomUUID(),registrationBody={nombre:'Docker verification user',email:`docker-${randomUUID()}@example.invalid`,password1:fixturePassword,password2:fixturePassword}
  async function register(){const r=await fetch(base+'/auth/register',{method:'POST',headers:{Origin:base,'content-type':'application/json','Idempotency-Key':registrationKey},body:JSON.stringify(registrationBody),signal:AbortSignal.timeout(35000)});return {status:r.status,headers:r.headers,data:await r.json()}}
  const registration=await register()
  pass('Automatic registration issues access and HttpOnly refresh',registration.status===201&&!!registration.data.access&&/HttpOnly/i.test(registration.headers.get('set-cookie')||''))
  pass('Email remains pending',registration.data.user.email_verificado===false)
  const repeated=await register();pass('Registration retry does not duplicate account',repeated.status===200&&repeated.data.user.id===registration.data.user.id)
  pass('Automatic session can read its profile',(await request('/api/auth/me/',{token:registration.data.access})).status===200)
  pass('Unverified checkout rejected',(await request('/api/cart/checkout/',{method:'POST',data:{},token:registration.data.access})).status===403)

  phase='wishlist and administrator access'
  const buyer=await login('browser-buyer@example.invalid'),admin=await login('browser-admin@example.invalid')
  const wished=await request(`/api/wishlist/${product.id}/`,{method:'PUT',token:registration.data.access})
  pass('Persistent wishlist add',[200,201].includes(wished.status))
  pass('Wishlist saved in PostgreSQL',(await request('/api/wishlist/',{token:registration.data.access})).data.saved_ids.includes(product.id))
  const isolated=await request('/api/wishlist/',{token:admin.token})
  pass('Wishlist belongs only to its owner',isolated.data.items.every(item=>item.id!==wished.data.id))
  for(const name of ['dashboard','products','orders','users','inventory','reviews','promotions'])pass(`Common user denied /admin/${name}/`,(await request(`/api/admin/${name}/`,{token:buyer.token})).status===403)
  const dashboard=await request('/api/admin/dashboard/',{token:admin.token})
  pass('Original admin dashboard and real sales available',dashboard.status===200&&Number(dashboard.data.ventas_total)>0&&Array.isArray(dashboard.data.top_productos))

  phase='cart, coupon, checkout and reviews'
  pass('Fixture cart cleared before purchase',(await request('/api/cart/clear/',{method:'POST',data:{},token:buyer.token})).status===200)
  const inventoryBefore=(await request(`/api/productos/${product.id}/`,{token:buyer.token})).data
  const cart=await request('/api/cart/add/',{method:'POST',data:{producto_id:product.id,cantidad:1},token:buyer.token});pass('Cart add',cart.status===200)
  const coupon=await request('/api/cart/aplicar-cupon/',{method:'POST',data:{codigo:'MONOLITH10'},token:buyer.token});pass('Legacy coupon managed by backend',coupon.status===200&&Number(coupon.data.descuento)>0)
  pass('Cart uses current backend unit price',cents(coupon.data.subtotal)===cents(inventoryBefore.precio)&&coupon.data.cantidad_items===1)
  pass('Discount and total reconcile',cents(coupon.data.subtotal)-cents(coupon.data.descuento)===cents(coupon.data.total))
  const checkoutBody={direccion:{calle:'Calle temporal 123',ciudad:'Lima',departamento:'Lima',codigo_postal:'15001'},metodo_pago:'transferencia',pago:{}}
  const key=randomUUID()
  async function checkout(){const r=await fetch(base+'/api/cart/checkout/',{method:'POST',headers:{Origin:base,'content-type':'application/json',Authorization:`Bearer ${buyer.token}`,'Idempotency-Key':key},body:JSON.stringify(checkoutBody),signal:AbortSignal.timeout(35000)});return {status:r.status,data:await r.json()}}
  const order=await checkout();pass('Checkout approved with server-side price',order.status===201&&order.data.pedido.monto_total===coupon.data.total)
  pass('Checkout retains server subtotal and discount',order.data.pedido.subtotal===coupon.data.subtotal&&order.data.pedido.descuento===coupon.data.descuento)
  const stockAfter=(await request(`/api/productos/${product.id}/`,{token:buyer.token})).data.stock
  pass('Purchase deducts stock exactly once',stockAfter===inventoryBefore.stock-1)
  const replay=await checkout();pass('Checkout replay returns the same order',replay.status===200&&replay.data.pedido.id===order.data.pedido.id)
  pass('Repeated checkout leaves stock unchanged',(await request(`/api/productos/${product.id}/`,{token:buyer.token})).data.stock===stockAfter)
  const invoice=await fetch(base+`/api/profile/orders/${order.data.pedido.id}/receipt/`,{headers:{Authorization:`Bearer ${buyer.token}`,'Accept-Language':'es'},signal:AbortSignal.timeout(15000)})
  assert.equal(invoice.status,200)
  assertReceiptTotals(Buffer.from(await invoice.arrayBuffer()),{subtotal:coupon.data.subtotal,discount:coupon.data.descuento,total:coupon.data.total})
  pass('Actual PDF reconciles subtotal, discount, included IGV and total',true)
  const reviewsPath=`/api/productos/${product.id}/reviews/`
  let reviews=await request(reviewsPath,{token:buyer.token})
  if(reviews.data.mine)await request(reviewsPath+'mine/',{method:'DELETE',token:buyer.token})
  pass('Verified purchase can review',(await request(reviewsPath,{method:'POST',data:{puntuacion:5,comentario:'Docker verified purchase review'},token:buyer.token})).status===201)
  pass('Own review edit',(await request(reviewsPath+'mine/',{method:'PATCH',data:{puntuacion:4},token:buyer.token})).status===200)
  pass('Own review delete',(await request(reviewsPath+'mine/',{method:'DELETE',token:buyer.token})).status===204)
  pass('Cancellation returns stock',(await request(`/api/profile/orders/${order.data.pedido.id}/cancel/`,{method:'POST',data:{motivo:'Docker verification cancellation'},token:buyer.token})).status===200)
  pass('Stock after cancellation matches the original',(await request(`/api/productos/${product.id}/`,{token:buyer.token})).data.stock===inventoryBefore.stock)
  const refreshed=await request('/auth/refresh',{method:'POST',data:{},cookie:buyer.cookie})
  pass('Refresh rotation',refreshed.status===200&&!!refreshed.data.access)
  pass('Logout',(await request('/auth/logout',{method:'POST',data:{},cookie:refreshed.headers.get('set-cookie')?.split(';')[0]})).status===200)
  pass('Logout revokes access JWT',(await request('/api/auth/me/',{token:buyer.token})).status===401)
  }

  phase='browser through Docker Nginx'
  const require=createRequire(path.join(root,'frontend/package.json'))
  require.resolve('playwright') // Fail clearly if host browser dependencies are absent.
  const original=fs.readFileSync(path.join(root,'frontend/test/browser.mjs'),'utf8')
  const beforeStart=original.indexOf('before(async()=>{'),afterStart=original.indexOf('after(async()=>{'),helpersStart=original.indexOf('async function login(')
  assert.ok(beforeStart>0&&afterStart>beforeStart&&helpersStart>afterStart)
  const replacement=`before(async()=>{const r=await fetch(base+'/api/__verification__/');const d=await r.json();assert.equal(d.mode,'monolith-docker-verification');assert.equal(d.database,'monolith_verification');browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROME_CHANNEL?{channel:process.env.PLAYWRIGHT_CHROME_CHANNEL}:{})})})\nafter(async()=>{await browser?.close()})\n`
  const adapted=original.slice(0,beforeStart).replace("const base='http://127.0.0.1:3000'",`const base='${base}'`)+replacement+original.slice(helpersStart)
  const temporary=path.join(root,'frontend/test/.docker-browser.mjs')
  try{
    assert.ok(!fs.existsSync(temporary));fs.writeFileSync(temporary,adapted)
    if(browserPattern)assert.ok(new RegExp(browserPattern).test(original),'Pattern does not match any browser source')
    const result=spawnSync(process.execPath,['--test',...(browserPattern?['--test-name-pattern',browserPattern]:[]),temporary],{cwd:root,stdio:'inherit',windowsHide:true})
    assert.equal(result.status,0,'Browser verification failed')
  }finally{if(fs.existsSync(temporary))fs.unlinkSync(temporary)}
  if(!httpOnly){phase='service logs';logs();dc(['ps'])}
  else console.log('NOT VERIFIED in attach mode: Docker engine health, container unit tests and service logs.')
  console.log('\nVerified local URLs:\nFrontend: '+base+'\nDjango: http://127.0.0.1:18001/\nNode: http://127.0.0.1:14001/health\nAdmin React: '+base+'/admin')
  console.log('Isolated services remain running. Stop only this isolated stack with: docker compose -p monolith-verification -f compose.verify.yaml down -v')
}catch(error){
  console.error(`NOT VERIFIED: ${phase}: ${error.message}`)
  if(started){try{logs()}catch{}}
  console.error('No production database migration is performed by this script.')
  process.exitCode=1
}finally{
  for(const [p,digest] of archives)assert.equal(createHash('sha256').update(fs.readFileSync(p)).digest('hex'),digest,'Original ZIP changed')
}
