const paths = { wishlist:'/deseos', catalog:'/', cart:'/carrito', profile:'/perfil', misPedidos:'/pedidos', admin:'/admin',
  checkout:'/checkout', login:'/ingresar', register:'/registro', forgot:'/recuperar' }
export const protectedPages = new Set(['wishlist','cart','profile','misPedidos','detallePedido','pedidoConfirmado','checkout','admin'])

export function parseRoute(pathname, search = '') {
  const path = pathname.replace(/\/$/, '') || '/'
  const result = { pathname:path, search }
  if (path === '/catalogo') return {...result, page:'catalog'}
  for (const [page, value] of Object.entries(paths)) if (path === value) return {...result, page}
  let match
  if ((match = path.match(/^\/producto\/(\d+)$/))) return {...result, page:'detail', productId:match[1]}
  if ((match = path.match(/^\/pedidos\/(\d+)(\/confirmado)?$/))) return {...result, page:match[2] ? 'pedidoConfirmado' : 'detallePedido', orderId:match[1]}
  if ((match = path.match(/^\/(verify|reset-password)\/([^/]+)$/))) return {...result, page:match[1] === 'verify' ? 'verify' : 'reset', token:match[2]}
  return {...result, page:'notFound'}
}

export function routeUrl(page, payload = {}) {
  if (page === 'detail') return `/producto/${encodeURIComponent(payload.productId)}`
  if (page === 'detallePedido') return `/pedidos/${encodeURIComponent(payload.orderId)}`
  if (page === 'pedidoConfirmado') return `/pedidos/${encodeURIComponent(payload.orderId)}/confirmado`
  return paths[page] || '/'
}

export function safeDestination(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') &&
    !['notFound','login','register','forgot','reset','verify'].includes(parseRoute(value.split('?')[0]).page) ? value : '/'
}
