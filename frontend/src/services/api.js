import axios from 'axios'

export const AUTH_BASE_URL = import.meta.env.VITE_AUTH_API_URL || 'http://127.0.0.1:4000'

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const catalogApi = axios.create({
  baseURL: import.meta.env.VITE_CATALOG_API_URL || (import.meta.env.DEV ? '/catalog-service/api' : API_BASE_URL),
  timeout: 12000
})

export const authApi = axios.create({baseURL: AUTH_BASE_URL, withCredentials: true, timeout:12000})

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = getAuthToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

export function setAuthToken(token) {
  if (token) {
    sessionStorage.setItem('jwt_access', token)
    api.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    sessionStorage.removeItem('jwt_access')
    delete api.defaults.headers.common.Authorization
  }
}

export function getAuthToken() {
  return sessionStorage.getItem('jwt_access')
}

let refreshPromise = null
async function refreshAccess() {
  if (!refreshPromise) refreshPromise = authApi.post('/auth/refresh').then(({data}) => {setAuthToken(data.access);return data.access}).finally(()=>{refreshPromise=null})
  return refreshPromise
}
api.interceptors.response.use(r=>r,async error=>{
  const original=error.config
  if(error.response?.status===401 && original && !original._retried && !original.url?.includes('/auth/login/')) {
    original._retried=true
    try {original.headers.Authorization=`Bearer ${await refreshAccess()}`;return api(original)} catch {setAuthToken(null)}
  }
  return Promise.reject(error)
})
export async function bootstrapAuth() {
  try {
    if (!getAuthToken()) await refreshAccess()
    const {data}=await api.get('/auth/me/')
    return data
  } catch {setAuthToken(null);return null}
}

export function getApiError(error) {
  const data = error?.response?.data
  const status = error?.response?.status

  if (!error?.response) {
    return error?.message || 'No se pudo conectar con el servidor.'
  }

  if (!data) {
    return `Error HTTP ${status || ''}`
  }

  if (typeof data === 'string') {
    if (data.trim().startsWith('<!doctype html') || data.trim().startsWith('<html')) {
      return `Error interno del servidor${status ? ` (${status})` : ''}. Revisa los logs de Render.`
    }
    return data
  }

  if (data.detail) {
    return data.detail
  }

  if (data.message) {
    return data.message
  }

  if (data.error) {
    if (typeof data.error === 'string') {
      return data.error
    }

    if (Array.isArray(data.error)) {
      return data.error.join(', ')
    }

    return JSON.stringify(data.error)
  }

  if (typeof data === 'object') {
    const formatted = Object.entries(data)
      .map(([key, value]) => {
        if (Array.isArray(value)) {
          return `${key}: ${value.join(', ')}`
        }

        if (typeof value === 'object' && value !== null) {
          return `${key}: ${JSON.stringify(value)}`
        }

        return `${key}: ${value}`
      })
      .join(' | ')

    return formatted || `Error HTTP ${status || ''}`
  }

  return `Error HTTP ${status || ''}`
}

// Sprint 4 helpers
export const checkoutApi = {
  listAddresses: () => api.get('/profile/addresses/'),
  listOrders: (params = {}) => api.get('/profile/orders/', { params }),
  getOrder: (id) => api.get(`/profile/orders/${id}/`),
  cancelOrder: (id, motivo = 'Cancelado por el cliente') => api.post(`/profile/orders/${id}/cancel/`, { motivo }),
  receipt: (id) => api.get(`/profile/orders/${id}/receipt/`, { responseType: 'blob' }),
  confirm: (payload) => api.post('/cart/checkout/', payload),
}
