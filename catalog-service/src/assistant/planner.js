import {validatePlan, AssistantError} from './validation.js';
export const normalize=value=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const has=(text,pattern)=>pattern.test(text);
const genres={
  rpg:['rpg','rol','role playing'], action:['accion','action'], adventure:['aventura','adventure'],
  racing:['carreras','racing','race'], sports:['deportes','sports','sport'], strategy:['estrategia','strategy'],
  horror:['terror','horror'], shooter:['shooter','disparos'], puzzle:['puzzle','rompecabezas'],
};
const platforms={pc:['pc','windows','steam'], playstation:['playstation','ps5','ps4'], xbox:['xbox'], nintendo:['nintendo','switch']};
const matches=(item,terms)=>terms.some(term=>[item.slug,item.nombre].some(value=>{
  const name=normalize(value).replace(/[-_]/g,' ');
  return name===term || name.split(/\s+/).includes(term) || name.includes(term+' ');
}));
export function planByRules(input, metadata) {
  const text=normalize(input.message), original=input.message;
  if(input.compare_ids.length) return validatePlan({intent:'compare',product_ids:input.compare_ids});
  if(has(text,/recuper|forgot.*password|reset.*password|olvide.*contra/)) return validatePlan({intent:'help',topic:'forgot'});
  if(has(text,/otros usuarios|other users|someone else|credencial|secret|api.?key|token|contrasena|password|ignore.*instruction|ignora.*instruccion/)) return validatePlan({intent:'help',topic:'privacy'});
  if(has(text,/\b(pedido|pedidos|order|orders|tracking|envio)\b/)) {
    const number=original.toUpperCase().match(/MNL-\d{4}-\d{5,10}/)?.[0];
    const id=text.match(/(?:pedido|order)\s*(?:numero\s*|number\s*|#\s*)?(\d+)\b/)?.[1];
    return validatePlan({intent:'orders',...(number?{order_number:number}:id?{order_id:Number(id)}:{})});
  }
  if(has(text,/\b(compara|comparar|comparalos|comparalas|compare|comparison|versus|vs)\b/)) {
    const quoted=[...original.matchAll(/["“]([^"”]+)["”]/g)].map(match=>match[1]);
    const names=quoted.length?quoted:original.replace(/^.*?\b(compara[r]?|compare|comparison)\b\s*/i,'').split(/\s+(?:vs\.?|versus|y|and)\s+/i).filter(x=>x.trim().length>=2);
    if(names.length>=2 && names.length<=3) return validatePlan({intent:'compare',names:names.map(x=>x.trim())});
    return validatePlan({intent:'compare',product_ids:input.context.product_ids.slice(0,3)});
  }
  const topics=[
    ['payments',/\b(pagos?|payments?|cobros?|bank|banco|tarjeta|transferencia|simulad|simulated|real money)\b/],
    ['filters',/como.*filtr|how.*filter|usar.*filtr|categorias disponibles|available categories/],
    ['register',/registr|crear.*cuenta|sign.?up|create.*account/],
    ['login',/iniciar.*sesion|login|log.?in|sign.?in/],
    ['checkout',/\b(checkout|comprar?|compras|buy|purchase|pagar?)\b/],
    ['cart',/\b(carrito|cart)\b/],
  ];
  for(const [topic,pattern] of topics) if(has(text,pattern)) return validatePlan({intent:'help',topic});
  if(has(text,/^(hola|hello|hi|hey|ayuda|help|buenas)[.!? ]*$/)) return validatePlan({intent:'help',topic:'capabilities'});
  const followup=has(text,/\b(ahora|tambien|solo|mas barato|cheaper|now|also|only|those|estos|esos)\b/);
  const selected={...(followup?input.context.filters:{})};
  if(has(text,/sin presupuesto|cualquier precio|any budget|no budget/)) {delete selected.min; delete selected.max;}
  const range=text.match(/(?:entre|between)\s*(?:s\/\.?\s*|soles?\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:y|and|a|-)\s*(\d+(?:[.,]\d{1,2})?)/);
  const budget=text.match(/(?:hasta|menos de|maximo|max\.?|presupuesto(?: de)?|budget(?: of)?|under|below|up to)\s*(?:s\/\.?\s*|soles?\s*|\$\s*)?(-?\d+(?:[.,]\d{1,2})?)/);
  if(range) {selected.min=range[1].replace(',','.'); selected.max=range[2].replace(',','.');}
  else if(budget) selected.max=budget[1].replace(',','.');
  let recognized=false, chosenPlatforms=[];
  for(const terms of Object.values(platforms)) if(terms.some(term=>new RegExp(`\\b${term}\\b`).test(text))) {
    const requested=terms.filter(term=>new RegExp(`\\b${term}\\b`).test(text));
    const found=metadata.platforms.filter(item=>matches(item,requested) || requested.some(term=>
      /^ps[45]$/.test(term) && normalize(item.nombre).replace(/\W/g,'').includes('playstation'+term.slice(2))));
    // Do not silently substitute another console generation or platform.
    if(!found.length) return validatePlan({intent:'clarify'});
    chosenPlatforms.push(...found.map(item=>item.slug));
    recognized=true;
  }
  if(chosenPlatforms.length) selected.platforms=[...new Set([
    ...(has(text,/\b(tambien|also)\b/) && !has(text,/\b(solo|only)\b/)?selected.platforms || []:[]),...chosenPlatforms,
  ])].slice(0,4);
  for(const [genre,terms] of Object.entries(genres)) if(terms.some(term=>new RegExp(`\\b${term}\\b`).test(text))) {
    const category=metadata.categories.find(item=>matches(item,[genre,...terms]));
    if(category) selected.category=category.slug;
    else selected.search=terms.find(term=>text.includes(term)) || genre;
    recognized=true; break;
  }
  // Exact names/slugs from the current metadata also work for local/custom genres.
  const category=metadata.categories.find(item=>new RegExp(`(?:^|\\W)${normalize(item.nombre).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}(?:$|\\W)`).test(text));
  if(category) {selected.category=category.slug; recognized=true;}
  if(!selected.category) {
    const games=metadata.categories.find(item=>['juegos','videojuegos','games','video games'].includes(normalize(item.nombre)));
    if(games) selected.category=games.slug;
  }
  const quoted=[...original.matchAll(/["“]([^"”]+)["”]/g)].map(m=>m[1]);
  if(quoted.length) selected.search=quoted[0].trim();
  else if(!recognized && !budget && !range && !followup) {
    let clean=original.replace(/^[¿¡\s]+/,'').replace(/(?:please|por favor)[,.]?\s*/i,'')
      .replace(/^(?:cu[aá]nto\s+(?:cuesta|vale)|cu[aá]l\s+es\s+el\s+precio\s+de|precio\s+(?:de|del)|stock\s+(?:de|del)|tienen|hay|h[aá]blame\s+de|qu[eé]\s+sabes\s+de|how much(?: is| does)?|what(?:'s| is) the price of|price(?: of)?|stock(?: of)?|do you have|tell me about|is|busca[r]?|search(?: for)?|find|muestra(?:me)?|show(?: me)?|recomienda(?:me)?|recommend(?: me)?)\s+/i,'')
      .replace(/[?!¿¡]+$/,'').replace(/\s+(?:available|in stock|cost|disponible)$/i,'').trim();
    if(/^(?:videojuegos?|juegos?|games?)(?:\s+(?:disponibles?|available))?$/i.test(clean)) clean='';
    if(clean.length>=2) selected.search=clean;
  }
  if(!selected.search && !recognized && !budget && !range && !followup && !has(text,/recom|recommend|catalog|videojueg|games?|juegos?|ofertas|discount/)) return validatePlan({intent:'help',topic:'capabilities'});
  try {return validatePlan({intent:'catalog',filters:selected,sort:has(text,/barat|cheaper|budget|presupuesto|hasta|under|below/)?'price':'popular'});}
  catch(error) {if(error instanceof AssistantError) throw error; throw new AssistantError(400,'invalid');}
}
