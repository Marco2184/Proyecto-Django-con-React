import {AssistantError,validatePlan} from './validation.js';
import {planByRules,normalize} from './planner.js';

export const messages={
  es:{invalid:'Revisa el mensaje y los filtros: hasta 500 caracteres y un presupuesto válido en soles.',
    unavailable:'El catálogo no está disponible ahora. No puedo confirmar precios ni stock. Reintenta.',
    unauthorized:'Inicia sesión para consultar exclusivamente tus pedidos.', forbidden:'No puedes consultar esa información.',
    not_found:'No encontré ese pedido o no pertenece a tu cuenta.', rate:'Has enviado demasiadas consultas. Espera un minuto.',
    busy:'El asistente está ocupado. Reintenta en unos segundos.',
    empty:'No encontré juegos disponibles con esos criterios. Prueba otro nombre, plataforma o presupuesto.',
    catalog:'Estas son coincidencias del catálogo actual. Los importes están en soles (S/). Comprueba la ficha antes de agregar.',
    compare:'Comparación de fichas actuales del catálogo. No tengo pruebas de rendimiento ni reseñas independientes para decidir cuál es mejor.',
    clarify:'Necesito una plataforma o título más preciso. También puedes seleccionar dos o tres fichas con «Comparar».',
    partial:'Algún juego no está disponible en el catálogo actual. No puedo confirmar sus datos; te muestro solo las fichas verificadas.',
    orders:'Estos son tus pedidos consultados ahora. Abre el detalle para el comprobante y las acciones disponibles.',
    no_orders:'No encontré pedidos en tu cuenta con ese criterio.',
    payments:'Todas las compras y pagos de Monolith son simulados. No hay cobros reales ni pasarelas bancarias. El checkout utiliza datos ficticios; nunca ingreses información bancaria auténtica. El pedido descuenta inventario simulado y una cancelación válida lo repone una sola vez.',
    filters:'Combina categoría, plataformas y precios mínimo/máximo en el catálogo; aplica los precios y usa la paginación. Puedes decir: «juegos para PC hasta 100». El botón «Ver resultados» abre tus filtros.',
    register:'Abre Registro, completa tus datos y una contraseña segura y revisa el correo de verificación. Nunca envíes tu contraseña por este chat.',
    login:'Inicia sesión con tu correo y contraseña en el formulario de acceso, no en el chat. Tu sesión permite consultar tus propios pedidos y utilizar el carrito.',
    forgot:'Utiliza Recuperar contraseña. Si el correo está registrado, recibirás un enlace de uso único y con caducidad. No compartas el enlace ni tu contraseña aquí.',
    cart:'Selecciona un juego y pulsa Agregar. Te pediré confirmar antes de añadir una unidad; la tienda volverá a comprobar tu sesión y el stock. Puedes ajustar cantidades y aplicar cupones desde el carrito.',
    checkout:'Revisa el carrito y tus descuentos, elige una dirección y confirma tú mismo «Pagar y confirmar» en el checkout simulado. Yo no completo pedidos ni hago cobros. El comprobante PDF está en el detalle del pedido.',
    privacy:'Solo consulto catálogo público y pedidos de tu propia sesión. No revelo secretos ni cuentas ajenas. No compartas contraseñas, tokens, direcciones o datos bancarios por este chat.',
    capabilities:'Soy un asistente de búsquedas y reglas, no IA generativa. Puedo buscar, recomendar según datos del catálogo, comparar fichas y orientar sobre compras simuladas. Prueba «PC hasta 100», «busca Halo» o «mis pedidos».',
  },
  en:{invalid:'Check your message and filters: up to 500 characters and a valid budget in Peruvian soles.',
    unavailable:'The catalog is unavailable right now. I cannot confirm prices or stock. Please retry.',
    unauthorized:'Sign in to view only your own orders.',forbidden:'You cannot access that information.',
    not_found:'That order was not found or does not belong to your account.',rate:'Too many requests. Please wait a minute.',
    busy:'The assistant is busy. Please retry in a few seconds.',
    empty:'No available games matched these criteria. Try a different title, platform or budget.',
    catalog:'These matches come from the current catalog. Prices are in Peruvian soles (S/). Check the product page before adding.',
    compare:'Comparison of current catalog entries. I do not have independent performance tests or reviews to decide which game is better.',
    clarify:'Please specify the platform or title more precisely. You can also select two or three product cards using Compare.',
    partial:'Some games are not available in the current catalog. I cannot confirm their details; only verified entries are shown.',
    orders:'These are your orders checked now. Open an order for its receipt and available actions.',
    no_orders:'No orders in your account matched these criteria.',
    payments:'All Monolith purchases and payments are simulated. There are no real charges or banking gateways. Checkout uses fictional details; never enter real banking information. Orders update simulated inventory, and valid cancellations restore it once.',
    filters:'Combine category, platforms and minimum/maximum prices in the catalog, apply the prices and use pagination. Try “PC games under 100”. View results opens your filters.',
    register:'Open Registration, fill in your details and a strong password, then check the verification email. Never send your password through this chat.',
    login:'Enter your email and password in the sign-in form, never in this chat. Your session lets you view your own orders and use the cart.',
    forgot:'Use Password recovery. If the email is registered, you will receive a single-use expiring link. Do not share the link or password here.',
    cart:'Choose a game and press Add. I will ask you to confirm before adding one unit; Django checks your session and stock again. Adjust quantities and apply coupons in the cart.',
    checkout:'Review the cart and discounts, choose an address and explicitly press Pay and confirm in simulated checkout. I do not complete orders or charge money. The PDF receipt is available in order details.',
    privacy:'I only consult the public catalog and orders from your own session. I do not disclose secrets or other accounts. Do not share passwords, tokens, addresses or banking details here.',
    capabilities:'I am a search and rules assistant, not generative AI. I can find and recommend catalog matches, compare entries and explain simulated shopping. Try “PC under 100”, “find Halo” or “my orders”.',
  },
};
const action=page=>({page});
const money=value=>typeof value==='string' && /^\d{1,8}(\.\d{1,2})?$/.test(value);
function product(data) {
  if(!data || !Number.isSafeInteger(data.id) || typeof data.nombre!=='string' || !money(data.precio) ||
      !Number.isSafeInteger(data.stock) || data.stock<0 || typeof data.disponible!=='boolean' ||
      !Array.isArray(data.plataformas) || ![true,false,null,0].includes(data.tiene_descuento) ||
      (data.precio_original!=null && !money(data.precio_original))) throw new AssistantError(502,'unavailable');
  return {id:data.id,nombre:data.nombre.slice(0,200),precio:data.precio,precio_original:data.precio_original ?? null,
    stock:data.stock,disponible:data.disponible,tiene_descuento:data.tiene_descuento===true,
    porcentaje_descuento:typeof data.porcentaje_descuento==='number'?data.porcentaje_descuento:null,
    plataformas:data.plataformas.map(p=>({slug:String(p.slug).slice(0,80),nombre:String(p.nombre).slice(0,80)})),
    categoria:data.categoria?{slug:String(data.categoria.slug).slice(0,80),nombre:String(data.categoria.nombre).slice(0,100)}:null,
    valoracion:data.valoracion ?? null};
}
function order(data) {
  if(!data || !Number.isSafeInteger(data.id) || typeof data.numero!=='string' || typeof data.estado!=='string' || !money(data.monto_total)) throw new AssistantError(502,'unavailable');
  return {id:data.id,numero:data.numero,estado:data.estado,estado_pago:data.estado_pago,metodo_pago:data.metodo_pago,
    monto_total:data.monto_total,fecha_estimada_entrega:data.fecha_estimada_entrega};
}

export function createAssistant({backendUrl,fetchImpl=fetch,intentProvider=planByRules,timeoutMs=6500}={}) {
  let metadataPromise=null, metadataUntil=0;
  async function get(path,params={},authorization,signal) {
    const url=new URL(backendUrl.replace(/\/+$/,'')+path);
    for(const [key,value] of Object.entries(params)) for(const item of Array.isArray(value)?value:[value]) if(item!=null && item!=='') url.searchParams.append(key,String(item));
    let response;
    try {response=await fetchImpl(url.toString(),{method:'GET',cache:'no-store',signal,headers:{Accept:'application/json',...(authorization?{Authorization:authorization}:{})}});}
    catch {throw new AssistantError(502,'unavailable');}
    if(!response.ok) {
      const codes={401:'unauthorized',403:'forbidden',404:'not_found'};
      throw new AssistantError(codes[response.status]?response.status:502,codes[response.status] || 'unavailable');
    }
    try {return await response.json();} catch {throw new AssistantError(502,'unavailable');}
  }
  async function loadMetadata(signal) {
    if(metadataPromise && Date.now()<metadataUntil) return metadataPromise;
    metadataUntil=Date.now()+300000;
    const all=async path=>{
      let results=[];
      for(let page=1;page<=5;page++) {
        const data=await get(path,{page},undefined,signal), rows=Array.isArray(data)?data:data.results;
        if(!Array.isArray(rows)) throw new AssistantError(502,'unavailable');
        results.push(...rows); if(!data.next) break;
      }
      return results;
    };
    metadataPromise=Promise.all([all('/plataformas/'),all('/categorias/')]).then(([platforms,categories])=>({platforms,categories:categories.flatMap(c=>[c,...(c.subcategorias || [])])}))
      .catch(error=>{metadataPromise=null;throw error;});
    return metadataPromise;
  }
  async function catalog(selected,sort,signal,pageSize=4) {
    const data=await get('/productos/',{search:selected.search,categoria:selected.category,plataforma:selected.platforms,
      precio_min:selected.min,precio_max:selected.max,page_size:pageSize,...(sort==='price'?{ordering:'precio'}:{})},undefined,signal);
    if(!data || !Array.isArray(data.results) || !Number.isSafeInteger(data.count)) throw new AssistantError(502,'unavailable');
    return {products:data.results.slice(0,pageSize).map(product),count:data.count};
  }
  return async function respond(input,{authorization}={}) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeoutMs);
    try {
      if(authorization) {
        if(!/^Bearer [A-Za-z0-9_.-]{10,4096}$/.test(authorization)) throw new AssistantError(401,'unauthorized');
        await get('/auth/me/',{},authorization,controller.signal);
      }
      // Metadata is public, bounded and cached; product/stock/order results never are.
      // Help and order intents need no catalog metadata.
      const preliminary=planByRules(input,{platforms:[],categories:[]});
      const metadata=['help','orders','compare'].includes(preliminary.intent)?{platforms:[],categories:[]}:await loadMetadata(controller.signal);
      const plan=validatePlan(await Promise.race([
        Promise.resolve().then(()=>intentProvider(input,metadata,{signal:controller.signal})),
        new Promise((_resolve,reject)=>controller.signal.addEventListener('abort',()=>reject(new AssistantError(502,'unavailable')),{once:true})),
      ]));
      const lang=input.language, text=messages[lang];
      const result={mode:'catalog-rules',intent:plan.intent,text:'',products:[],orders:[],actions:[],count:0,
        checked_at:new Date().toISOString(),context:{filters:plan.intent==='catalog'?plan.filters:input.context.filters,product_ids:input.context.product_ids}};
      if(plan.intent==='help') {
        result.text=text[plan.topic || 'capabilities'];
        result.actions=({register:[action('register')],login:[action('login')],forgot:[action('forgot')],cart:[action('cart')],
          checkout:[action('cart'),action('checkout')],payments:[action('cart')],filters:[action('catalog')],privacy:[],capabilities:[action('catalog')]})[plan.topic || 'capabilities'];
      } else if(plan.intent==='orders') {
        if(!authorization) throw new AssistantError(401,'unauthorized');
        if(plan.order_id) result.orders=[order(await get(`/profile/orders/${plan.order_id}/`,{},authorization,controller.signal))];
        else {
          const data=await get('/profile/orders/',plan.order_number?{search:plan.order_number}:{},authorization,controller.signal);
          if(!Array.isArray(data.results)) throw new AssistantError(502,'unavailable');
          result.orders=data.results.slice(0,5).map(order);
        }
        result.count=result.orders.length; result.text=result.count?text.orders:text.no_orders; result.actions=[action('misPedidos')];
      } else if(plan.intent==='catalog') {
        const found=await catalog(plan.filters,plan.sort,controller.signal);
        Object.assign(result,found); result.text=result.count?text.catalog:text.empty;
        result.context.product_ids=result.products.map(p=>p.id);
        result.actions=[{page:'catalog',filters:plan.filters}];
      } else if(plan.intent==='compare') {
        let products=[], ambiguous=false, missing=false;
        if(plan.product_ids.length>=2) {
          const results=await Promise.all(plan.product_ids.map(async id=>{
            try {return product(await get(`/productos/${id}/`,{},undefined,controller.signal));}
            catch(error) {if(error.status===404) {missing=true;return null;} throw error;}
          }));
          products=results.filter(Boolean);
        } else if(plan.names.length>=2) {
          const results=await Promise.all(plan.names.map(name=>catalog({search:name},undefined,controller.signal,3)));
          for(let i=0;i<results.length;i++) {
            const found=results[i], exact=found.products.find(p=>normalize(p.nombre)===normalize(plan.names[i]));
            if(exact) products.push(exact);
            else if(found.count===1) products.push(found.products[0]);
            else {ambiguous=true;products.push(...found.products);if(!found.count) missing=true;}
          }
        } else ambiguous=true;
        result.products=[...new Map(products.map(p=>[p.id,p])).values()].slice(0,4);
        if(result.products.length<2) ambiguous=true;
        result.intent=missing?'catalog':ambiguous?'clarify':'compare';
        result.text=missing?text.partial:ambiguous?text.clarify:text.compare;
        result.count=result.products.length;result.context.product_ids=result.products.map(p=>p.id);
      } else result.text=text.clarify;
      return result;
    } finally {clearTimeout(timer);}
  };
}
