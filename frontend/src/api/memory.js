import { http } from './http'

export const listMemories = async (params = {}) => {
  const response = await http.get('/api/memory', { params })
  return response.data.memories
}

export const createMemory = async (data) => {
  const response = await http.post('/api/memory', data)
  return response.data
}

export const updateMemory = async (id, data) => {
  const response = await http.patch(`/api/memory/${id}`, data)
  return response.data
}

export const deleteMemory = async (id) => {
  const response = await http.delete(`/api/memory/${id}`)
  return response.data
}

export const getProfile = async () => {
  const response = await http.get('/api/memory/profile')
  return response.data
}

export const updateProfile = async (data) => {
  const response = await http.patch('/api/memory/profile', data)
  return response.data
}

export const searchMemories = async (data) => {
  const response = await http.post('/api/memory/search', data)
  return response.data.memories
}
