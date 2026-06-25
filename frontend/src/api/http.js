import axios from 'axios'

let apiBaseURL = import.meta.env.VITE_API_BASE_URL
if (apiBaseURL === undefined || apiBaseURL === '') {
  apiBaseURL = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''
}

export const http = axios.create({
  baseURL: apiBaseURL,
  timeout: 120000,
})

export const AUTH_TOKEN_KEY = 'auth_token'

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY)
  }
}

export function buildAuthHeaders() {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

http.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
