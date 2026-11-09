import { djangoProxyHeaders } from './djangoProxyHeaders.js';
import {AsyncLocalStorage} from 'node:async_hooks';
import {localeResponses, language} from './locale.js';
import { Router } from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'node:crypto';

export function authRouter({backendUrl = process.env.DJANGO_API_URL || 'http://127.0.0.1:8000/api', secret = process.env.JWT_SHARED_SECRET, refreshSecret = process.env.JWT_REFRESH_SECRET, fetchImpl = fetch, production = process.env.NODE_ENV === 'production'} = {}) {
  if (!secret || secret.length < 32 || !refreshSecret || refreshSecret.length < 32) throw new Error('Configura JWT_SHARED_SECRET y JWT_REFRESH_SECRET (mínimo 32 caracteres aleatorios).');
  const router = Router();
  const locale = new AsyncLocalStorage();
  router.use(localeResponses);
  router.use((req,res,next)=>locale.run(language(req),next));
  const issuer = 'monolith-node';
  const audience = 'monolith-django';
  const secure = process.env.COOKIE_SECURE === undefined ? production : process.env.COOKIE_SECURE === 'true';
  const sameSite = process.env.COOKIE_SAME_SITE || (production ? 'none' : 'lax');
  const cookieName = 'monolith_refresh';
  const cookieOptions = { httpOnly: true, secure, sameSite, path: '/auth', maxAge: 7 * 86400000 };
  const signAccess = u => jwt.sign({ sub: String(u.id), typ: 'access', sid: u.sid, token_version: u.token_version }, secret, { algorithm:'HS256', issuer, audience, expiresIn:'15m' });
  const signRefresh = u => jwt.sign({ sub:String(u.id), typ:'refresh', sid:u.sid, token_version:u.token_version, jti:u.jti }, refreshSecret, { algorithm:'HS256', issuer, audience, expiresIn:'7d' });
  const clearCookie = res => res.clearCookie(cookieName, { path:'/auth', httpOnly:true, secure, sameSite });
  const readRefresh = req => {
    const token = req.cookies?.[cookieName];
    if (!token) throw new Error('Missing refresh');
    const payload = jwt.verify(token, refreshSecret, { algorithms:['HS256'], issuer, audience });
    if (payload.typ !== 'refresh' || typeof payload.sub !== 'string' || !/^\d+$/.test(payload.sub) || !payload.sid || !payload.jti || !payload.token_version) throw new Error('Invalid refresh');
    return payload;
  };
  // CORS alone does not stop cross-origin form POSTs using ambient cookies.
  router.use((req, res, next) => {
    const origins = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000,http://127.0.0.1:3000').split(',').map(x => x.trim());
    if ((req.headers.origin && !origins.includes(req.headers.origin)) || req.headers['sec-fetch-site'] === 'cross-site') {
      return res.status(403).json({ detail:'Origen no permitido.' });
    }
    next();
  });
  async function django(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), path === '/auth/node/register/' ? 25000 : 8000);
    try {
      const body = JSON.stringify(payload);
      const serviceToken = jwt.sign({typ:'service', purpose:'/api' + path, body_hash:crypto.createHash('sha256').update(body).digest('hex')}, secret, {algorithm:'HS256', issuer, audience:'monolith-internal', expiresIn:'30s'});
      const headers = {'content-type':'application/json', 'accept-language': locale.getStore() || 'es', ...djangoProxyHeaders(backendUrl)};
      if (path.startsWith('/auth/node/')) headers.authorization = `Bearer ${serviceToken}`;
      const response = await fetchImpl(`${backendUrl.replace(/\/$/,'')}${path}`, {method:'POST', headers, body, signal:controller.signal});
      const data = await response.json().catch(() => ({}));
      return {status:response.status, data};
    } finally {clearTimeout(timer);}
  }
  const rate = new Map();
  router.post('/login', async (req,res) => {
    if (typeof req.body?.email !== 'string' || typeof req.body?.password !== 'string' || req.body.password.length > 128) return res.status(400).json({detail:'Correo y contraseña inválidos.'});
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = req.body?.password;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || !password) return res.status(400).json({detail:'Correo y contraseña obligatorios.'});
    const key = `${req.ip}:${email}`; const now=Date.now(); const hit=rate.get(key) || {n:0, until:now+60000};
    if (now > hit.until) {hit.n=0;hit.until=now+60000;}
    if (++hit.n > 8) return res.status(429).json({detail:'Demasiados intentos. Espera un minuto.'});
    rate.set(key,hit);if (rate.size>3000) rate.clear();
    try {
      const r=await django('/auth/node/login/',{email,password});
      if (r.status !== 200 || !r.data?.user?.id) return res.status(401).json({detail:'Credenciales inválidas o cuenta inactiva.'});
      rate.delete(key);
      if (!r.data.session?.sid) throw new Error('Missing session');
      res.cookie(cookieName,signRefresh(r.data.session),cookieOptions);
      return res.json({access:signAccess(r.data.session),user:r.data.user,token_type:'Bearer',expires_in:900});
    } catch {return res.status(502).json({detail:'No se pudo contactar el backend Django.'});}
  });
  router.post('/register', async (req,res) => {
    const {nombre,email,telefono,password1,password2}=req.body || {};
    if (!nombre || !email || !password1 || password1 !== password2 || String(password1).length < 8) return res.status(400).json({detail:'Revisa nombre, correo y contraseñas (mínimo 8 caracteres).'});
    const request_id = req.get('Idempotency-Key');
    if (!/^[0-9a-f-]{36}$/i.test(request_id || '')) return res.status(400).json({detail:'Identificador de registro inválido.'});
    try {
      const r=await django('/auth/node/register/',{nombre,email,telefono:telefono||'',password1,password2,request_id});
      if (![200,201].includes(r.status)) return res.status(r.status).json(r.data);
      if (!r.data.session?.sid) throw new Error('Missing session');
      res.cookie(cookieName,signRefresh(r.data.session),cookieOptions);
      return res.status(r.status).json({access:signAccess(r.data.session),user:r.data.user,token_type:'Bearer',expires_in:900});
    }
    catch {return res.status(502).json({detail:'No se pudo registrar el usuario en Django.'});}
  });
  router.post('/refresh',async (req,res)=>{
    let payload;
    try { payload = readRefresh(req); } catch { clearCookie(res); return res.status(401).json({detail:'Sesión expirada.'}); }
    try {
      const r = await django('/auth/node/refresh/', payload);
      if (r.status !== 200 || !r.data.session?.sid) {
        if (r.status >= 500) return res.status(502).json({detail:'Autenticación temporalmente no disponible.'});
        clearCookie(res); return res.status(401).json({detail:'Sesión expirada o revocada.'});
      }
      res.cookie(cookieName,signRefresh(r.data.session),cookieOptions);
      return res.json({access:signAccess(r.data.session),token_type:'Bearer',expires_in:900});
    } catch {return res.status(502).json({detail:'No se pudo contactar el backend Django.'});}
  });
  router.post('/logout',async (req,res)=>{
    let payload;
    try { payload = readRefresh(req); } catch { clearCookie(res); return res.json({message:'Sesión cerrada.'}); }
    try {
      const r = await django('/auth/node/logout/', payload);
      if (r.status >= 500) return res.status(502).json({detail:'No se pudo revocar la sesión.'});
      clearCookie(res); return res.json({message:'Sesiones cerradas.'});
    } catch {return res.status(502).json({detail:'No se pudo revocar la sesión.'});}
  });
  return router;
}
