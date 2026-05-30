import axios from 'axios'

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')

  if (token) {
    config.headers.Authorization = `Token ${token}`
  }

  return config
})

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('token', token)
    api.defaults.headers.common.Authorization = `Token ${token}`
  } else {
    localStorage.removeItem('token')
    delete api.defaults.headers.common.Authorization
  }
}

export function getAuthToken() {
  return localStorage.getItem('token')
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