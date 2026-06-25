import { http } from './http'

export async function getDocuments() {
  const { data } = await http.get('/api/documents')
  return data
}

export async function uploadDocuments(files, visibility = 'private', category = 'general') {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  formData.append('visibility', visibility)
  formData.append('category', category)
  const { data } = await http.post('/api/documents', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return data
}

export async function deleteDocument(documentId) {
  const { data } = await http.delete(`/api/documents/${encodeURIComponent(documentId)}`)
  return data
}

export async function clearDocuments(scope = 'mine') {
  const { data } = await http.delete('/api/documents', {
    params: { scope },
  })
  return data
}
