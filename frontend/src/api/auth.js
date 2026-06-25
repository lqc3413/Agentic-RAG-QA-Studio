import { http, setAuthToken } from './http'

export async function registerUser(username, password) {
  const { data } = await http.post('/api/auth/register', { username, password })
  setAuthToken(data.access_token)
  return data
}

export async function loginUser(username, password) {
  const { data } = await http.post('/api/auth/login', { username, password })
  setAuthToken(data.access_token)
  return data
}

export async function getCurrentUser() {
  const { data } = await http.get('/api/auth/me')
  return data
}

export async function logoutUser() {
  const { data } = await http.post('/api/auth/logout')
  setAuthToken(null)
  return data
}
