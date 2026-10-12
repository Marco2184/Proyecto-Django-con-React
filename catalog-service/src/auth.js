import { Router } from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'node:crypto';

export function authRouter({backendUrl = process.env.DJANGO_API_URL || 'http://127.0.0.1:8000/api', secret = process.env.JWT_SHARED_SECRET, refreshSecret = process.env.JWT_REFRESH_SECRET, fetchImpl = fetch, production = process.env.NODE_ENV === 'production'} = {}) {
  if (!secret || secret.length < 32 || !refreshSecret || refreshSecret.length < 32) throw new Error('Configura JWT_SHARED_SECRET y JWT_REFRESH_SECRET (mínimo 32 caracteres aleatorios).');
  const router = Router();
  const issuer = 'monolith-node';
  const audience = 'monolith-django';
  const secure = production;
  const cookieName = 'monolith_refresh';
  const cookieOptions = { httpOnly: true, secure, sameSite: production ? 'none' : 'lax', path: '/auth', maxAge: 7 * 86400000 };
  const signAccess = u => jwt.sign({ sub: String(u.id), typ: 'access', token_version: u.token_version || 0 }, secret, { algorithm:'HS256', issuer, audience, expiresIn:'15m' });
  const signRefresh = u => jwt.sign({ sub:String(u.id), typ:'refresh', jti:crypto.randomUUID() }, refreshSecret, { algorithm:'HS256', issuer, audience, expiresIn:'7d' });
  async function django(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetchImpl(`${backendUrl.replace(/\/$/,'')}${path}`, {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(payload), signal:controller.signal});
      const data = await response.json().catch(() => ({}));
      return {status:response.status, data};
    } finally {clearTimeout(timer);}
  }
  const rate = new Map();
  router.post('/login', async (req,res) => {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = req.body?.password;
    if (!email || typeof password !== 'string') return res.status(400).json({detail:'Correo y contraseña obligatorios.'});
    const key = `${req.ip}:${email}`; const now=Date.now(); const hit=rate.get(key) || {n:0, until:now+60000};
    if (now > hit.until) {hit.n=0;hit.until=now+60000;}
    if (++hit.n > 8) return res.status(429).json({detail:'Demasiados intentos. Espera un minuto.'});
    rate.set(key,hit);if (rate.size>3000) rate.clear();
    try {
      const r=await django('/auth/login/',{email,password});
      if (r.status !== 200 || !r.data?.user?.id) return res.status(401).json({detail:'Credenciales inválidas o cuenta inactiva.'});
      rate.delete(key);
      res.cookie(cookieName,signRefresh(r.data.user),cookieOptions);
      return res.json({access:signAccess(r.data.user),user:r.data.user,token_type:'Bearer',expires_in:900});
    } catch {return res.status(502).json({detail:'No se pudo contactar el backend Django.'});}
  });
  router.post('/register', async (req,res) => {
    const {nombre,email,telefono,password1,password2}=req.body || {};
    if (!nombre || !email || !password1 || password1 !== password2 || String(password1).length < 8) return res.status(400).json({detail:'Revisa nombre, correo y contraseñas (mínimo 8 caracteres).'});
    try { const r=await django('/auth/register/',{nombre,email,telefono:telefono||'',password1,password2});return res.status(r.status).json(r.data); }
    catch {return res.status(502).json({detail:'No se pudo registrar el usuario en Django.'});}
  });
  router.post('/refresh',(req,res)=>{
    const match=(req.headers.cookie || '').split(';').map(s=>s.trim()).find(s=>s.startsWith(cookieName+'='));
    if(!match) return res.status(401).json({detail:'Sesión expirada.'});
    try {const payload=jwt.verify(decodeURIComponent(match.slice(cookieName.length+1)),refreshSecret,{algorithms:['HS256'],issuer,audience});
      if(payload.typ!=='refresh') throw Error('Tipo inválido');
      const user={id:payload.sub};
      res.cookie(cookieName,signRefresh(user),cookieOptions);
      res.json({access:signAccess(user),token_type:'Bearer',expires_in:900});
    }catch{res.clearCookie(cookieName,{path:'/auth',httpOnly:true,secure,sameSite:production?'none':'lax'});res.status(401).json({detail:'Sesión expirada.'});}
  });
  router.post('/logout',(_req,res)=>{res.clearCookie(cookieName,{path:'/auth',httpOnly:true,secure,sameSite:production?'none':'lax'});res.json({message:'Sesión cerrada en el navegador.'});});
  return router;
}
