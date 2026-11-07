export class AssistantError extends Error {
  constructor(status, code) { super(code); this.status=status; this.code=code; }
}
const invalid=()=>{throw new AssistantError(400,'invalid')};
const object=value=>value && typeof value==='object' && !Array.isArray(value);
const keys=(value,allowed)=>{if(!object(value) || Object.keys(value).some(key=>!allowed.includes(key))) invalid()};
export function ids(value, max=4) {
  if(!Array.isArray(value) || value.length>max || value.some(id=>!Number.isSafeInteger(id) || id<1 || id>2147483647)) invalid();
  return [...new Set(value)];
}
export function filters(value={}) {
  keys(value,['search','category','platforms','min','max']);
  const result={};
  for(const name of ['search','category']) if(value[name]!==undefined) {
    if(typeof value[name]!=='string' || value[name].length>(name==='search'?100:80)) invalid();
    if(value[name]) result[name]=value[name].trim();
  }
  if(value.platforms!==undefined) {
    if(!Array.isArray(value.platforms) || value.platforms.length>4 || value.platforms.some(p=>typeof p!=='string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(p))) invalid();
    result.platforms=[...new Set(value.platforms)];
  }
  for(const name of ['min','max']) if(value[name]!==undefined && value[name]!=='') {
    const raw=String(value[name]);
    if(!/^\d{1,8}(\.\d{1,2})?$/.test(raw)) invalid();
    result[name]=raw;
  }
  if(result.min && result.max && Number(result.min)>Number(result.max)) invalid();
  return result;
}
export function validateInput(body) {
  keys(body,['message','language','context','compare_ids']);
  if(typeof body.message!=='string' || body.message.trim().length<1 || body.message.length>500 || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(body.message)) invalid();
  if(body.language!==undefined && !['es','en'].includes(body.language)) invalid();
  const context=body.context || {};
  keys(context,['filters','product_ids']);
  return {message:body.message.trim(), language:body.language || 'es',
    context:{filters:filters(context.filters),product_ids:ids(context.product_ids || [])},
    compare_ids:ids(body.compare_ids || [],3)};
}
// An optional future model can produce ONLY this intent contract. It cannot
// supply facts, URLs, SQL, user IDs, tools or business mutations.
export function validatePlan(value) {
  keys(value,['intent','topic','filters','product_ids','names','order_id','order_number','sort']);
  if(!['catalog','compare','orders','help','clarify'].includes(value.intent)) invalid();
  const result={intent:value.intent,filters:filters(value.filters)};
  if(value.topic!==undefined) {
    if(!['payments','filters','register','login','forgot','cart','checkout','privacy','capabilities'].includes(value.topic)) invalid();
    result.topic=value.topic;
  }
  result.product_ids=ids(value.product_ids || [],3);
  result.names=value.names || [];
  if(!Array.isArray(result.names) || result.names.length>3 || result.names.some(n=>typeof n!=='string' || n.length<2 || n.length>100)) invalid();
  if(value.order_id!==undefined) result.order_id=ids([value.order_id],1)[0];
  if(value.order_number!==undefined) {
    if(typeof value.order_number!=='string' || !/^MNL-\d{4}-\d{5,10}$/.test(value.order_number)) invalid();
    result.order_number=value.order_number;
  }
  if(value.sort!==undefined) {if(!['price','popular'].includes(value.sort)) invalid(); result.sort=value.sort;}
  return result;
}
