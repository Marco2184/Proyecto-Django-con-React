import axios from 'axios'
import { dict, getTranslatedText } from '../i18n'

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

// Read the current selection for every request, including auth and PDF downloads.
// Explicit headers take precedence over the asynchronously updated Django cookie.
for (const client of [api, authApi, catalogApi]) {
  client.interceptors.request.use(config => {
    config.headers['Accept-Language'] = localStorage.getItem('lang') === 'en' ? 'en' : 'es'
    return config
  })
}

api.interceptors.request.use((config) => {
  if (/\/auth\/(login|register|forgot-password|reset-password|verify)/.test(config.url || '')) {
    delete config.headers.Authorization
    return config
  }
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
  const publicAuth = /\/auth\/(login|register|forgot-password|reset-password|verify)/.test(original?.url || '')
  if(error.response?.status===401 && original && !original._retried && !publicAuth) {
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
  const t = dict[localStorage.getItem('lang') === 'en' ? 'en' : 'es']
  if (!error?.response) return t.networkError
  const data = error.response.data
  if (!data || typeof data === 'string' && /^\s*</.test(data)) return t.serverError
  const flatten = value => {
    if (typeof value === 'string') return [getTranslatedText(t, value)]
    if (Array.isArray(value)) return value.flatMap(flatten)
    if (value && typeof value === 'object') return Object.values(value).flatMap(flatten)
    return []
  }
  return flatten(data.detail || data.message || data.error || data).join(' | ') || t.serverError
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
