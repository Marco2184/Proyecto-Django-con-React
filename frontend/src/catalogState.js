export const PAGE_SIZE = 20
export function readCatalog(search) {
  const p = new URLSearchParams(search), page = Number(p.get('page'))
  return {q:(p.get('search') || '').slice(0,150), category:p.get('categoria') || '',
    platforms:[...new Set(p.getAll('plataforma'))], min:p.get('precio_min') || '', max:p.get('precio_max') || '',
    sort:p.get('sort') || 'popularidad', page:Number.isSafeInteger(page) && page>0 ? page : 1}
}
export function catalogParams(state) {
  const params = new URLSearchParams({page:String(state.page),page_size:String(PAGE_SIZE)})
  if (state.q.trim().length>=2) params.set('search',state.q.trim())
  const ordering = {precio_asc:'precio',precio_desc:'-precio',recientes:'-activo'}[state.sort]
  if (ordering) params.set('ordering',ordering)
  for (const platform of state.platforms) params.append('plataforma',platform)
  if (state.category) params.set('categoria',state.category)
  if (state.min!=='') params.set('precio_min',state.min)
  if (state.max!=='') params.set('precio_max',state.max)
  return params.toString()
}
export function visiblePages(page,total) {
  return [...new Set([1,...Array.from({length:5},(_,i)=>page+i-2),total])].filter(n=>n>0 && n<=total).sort((a,b)=>a-b)
}
