import test from 'node:test'
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import jwt from 'jsonwebtoken'
import {createApp} from '../src/app.js'

test('registration uses a bound service JWT and returns an HttpOnly refresh cookie',async()=>{
  process.env.JWT_SHARED_SECRET='ci-only-shared-secret-00000000000000000000000'
  process.env.JWT_REFRESH_SECRET='ci-only-refresh-secret-0000000000000000000000'
  process.env.COOKIE_SECURE='false'
  let calls=0
  const app=createApp({fetchImpl:async(url,opts)=>{
    calls++;assert.ok(url.endsWith('/auth/node/register/'))
    const token=jwt.verify(opts.headers.authorization.slice(7),process.env.JWT_SHARED_SECRET,{algorithms:['HS256'],issuer:'monolith-node',audience:'monolith-internal'})
    assert.equal(token.purpose,'/api/auth/node/register/')
    assert.equal(token.body_hash,crypto.createHash('sha256').update(opts.body).digest('hex'))
    return new Response(JSON.stringify({user:{id:1,nombre:'New',email_verificado:false},session:{id:1,sid:crypto.randomUUID(),token_version:crypto.randomUUID(),jti:crypto.randomUUID()}}),{status:201})
  }})
  const server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r))
  const origin=`http://127.0.0.1:${server.address().port}`
  try{
    let r=await fetch(origin+'/auth/register',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({nombre:'New',email:'new@example.invalid',password1:'Password!9482',password2:'Password!9482'})})
    assert.equal(r.status,400);assert.equal(calls,0)
    r=await fetch(origin+'/auth/register',{method:'POST',headers:{'content-type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({nombre:'New',email:'new@example.invalid',password1:'Password!9482',password2:'Password!9482'})})
    assert.equal(r.status,201);assert.match(r.headers.get('set-cookie'),/HttpOnly/)
    const data=await r.json();assert.ok(data.access);assert.equal(data.user.email_verificado,false);assert.equal(data.session,undefined)
    const claims=jwt.verify(data.access,process.env.JWT_SHARED_SECRET,{audience:'monolith-django',issuer:'monolith-node'});assert.equal(claims.typ,'access')
    r=await fetch(origin+'/auth/refresh',{method:'POST'});assert.equal(r.status,401)
    r=await fetch(origin+'/auth/login',{method:'POST',headers:{Origin:'https://untrusted.invalid','content-type':'application/json'},body:'{}'});assert.equal(r.status,403)
  }finally{await new Promise(r=>server.close(r))}
})
