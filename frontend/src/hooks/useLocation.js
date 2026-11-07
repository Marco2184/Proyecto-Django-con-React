import { useCallback, useEffect, useState } from 'react'
import { parseRoute, routeUrl } from '../navigation'

const read = () => parseRoute(window.location.pathname, window.location.search)
export default function useLocation() {
  const [location, setLocation] = useState(read)
  useEffect(() => {
    const update = event => setLocation({...read(), navigationType:event.type==='popstate'?'pop':'push'})
    window.addEventListener('popstate', update)
    window.addEventListener('monolith:navigate', update)
    return () => { window.removeEventListener('popstate', update); window.removeEventListener('monolith:navigate', update) }
  }, [])
  const visit = useCallback((url, {replace = false} = {}) => {
    if (url === window.location.pathname + window.location.search) return
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    window.dispatchEvent(new Event('monolith:navigate'))
  }, [])
  const navigate = useCallback((page, payload = {}) => {
    let url = routeUrl(page, payload)
    if (page==='catalog') {
      const previous=sessionStorage.getItem('monolith-catalog-url')
      if (previous && parseRoute(previous.split('?')[0]).page==='catalog') url=previous
    }
    if (['login','register'].includes(page) && payload.next) url += '?next=' + encodeURIComponent(payload.next)
    visit(url, payload)
  }, [visit])
  const query = useCallback((changes, {replace = false} = {}) => {
    const params = new URLSearchParams(window.location.search)
    Object.entries(changes).forEach(([key,value]) => {
      params.delete(key)
      for (const item of Array.isArray(value) ? value : [value]) if (item !== '' && item != null) params.append(key, String(item))
    })
    visit(window.location.pathname + (params.size ? '?' + params.toString() : ''), {replace})
  }, [visit])
  return { location, navigate, visit, query }
}
