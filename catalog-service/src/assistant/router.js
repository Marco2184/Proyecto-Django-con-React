import {language as requestLanguage} from '../locale.js';
import {Router} from 'express';
import {createAssistant,messages} from './service.js';
import {AssistantError,validateInput} from './validation.js';

export function assistantRouter({backendUrl,fetchImpl,allowedOrigins='',limit=30,windowMs=60000,maxConcurrent=4,intentProvider}={}) {
  const router=Router(), requests=new Map(), origins=allowedOrigins.split(',').map(x=>x.trim()).filter(Boolean);
  const respond=createAssistant({backendUrl,fetchImpl,intentProvider});
  let active=0;
  router.post('/chat',async(req,res)=>{
    const language=['es','en'].includes(req.body?.language)?req.body.language:requestLanguage(req);
    const fail=error=>res.status(error.status || 502).json({mode:'catalog-rules',code:error.code || 'unavailable',detail:messages[language][error.code] || messages[language].unavailable});
    res.set('Cache-Control','no-store');
    if((req.headers.origin && !origins.includes(req.headers.origin)) || req.headers['sec-fetch-site']==='cross-site') return fail(new AssistantError(403,'forbidden'));
    // REMOTE_ADDR is deliberate: never trust a user-supplied proxy header.
    // One Node instance serves this academic deployment; no business DB writes.
    const now=Date.now(), key=req.socket.remoteAddress || 'local';
    for(const [ip,entry] of requests) if(entry.until<=now) requests.delete(ip);
    if(requests.size>=5000 && !requests.has(key)) return fail(new AssistantError(429,'rate'));
    const entry=requests.get(key) || {count:0,until:now+windowMs};
    requests.set(key,entry);
    if(++entry.count>limit) {res.set('Retry-After',String(Math.max(1,Math.ceil((entry.until-now)/1000))));return fail(new AssistantError(429,'rate'));}
    let input;
    try {input=validateInput(req.body && !Array.isArray(req.body) ? {...req.body,language:req.body.language || language} : req.body);} catch(error) {return fail(error);}
    if(active>=maxConcurrent) {res.set('Retry-After','3');return fail(new AssistantError(503,'busy'));}
    active++;
    try {res.json(await respond(input,{authorization:req.headers.authorization}));}
    catch(error) {return fail(error instanceof AssistantError?error:new AssistantError(502,'unavailable'));}
    finally {active--;}
  });
  return router;
}
