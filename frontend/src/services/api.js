import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('token', token)
    api.defaults.headers.common.Authorization = `Token ${token}`
  } else {
    localStorage.removeItem('token')
    delete api.defaults.headers.common.Authorization
  }
}

export function bootstrapAuth() {
  const token = localStorage.getItem('token')
  if (token) setAuthToken(token)
  return token
}

export function getApiError(error) {
  const data = error?.response?.data
  if (!data) return 'No se pudo conectar con el backend Django.'
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.entries(data)[0]
  if (!first) return 'Ocurrió un error inesperado.'
  const [field, value] = first
  return `${field}: ${Array.isArray(value) ? value.join(', ') : value}`
}
