import { buildAuthHeaders, http } from './http'

function buildApiUrl(path) {
  const baseUrl = http.defaults.baseURL || ''
  if (!baseUrl) return path

  return `${baseUrl.replace(/\/$/, '')}${path}`
}

export async function sendChatMessageStream(message, session_id, onChunk) {
  const response = await fetch(buildApiUrl('/api/chat'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ message, session_id }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')

    // 在缓冲区中保留最后一行不完整的数据
    buffer = lines.pop()

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (trimmed.startsWith('data: ')) {
        const jsonStr = trimmed.slice(6)
        try {
          const parsed = JSON.parse(jsonStr)
          onChunk(parsed)
        } catch (e) {
          console.warn('Failed to parse SSE JSON:', jsonStr, e)
        }
      }
    }
  }
}

export async function resetChatSession(session_id) {
  const { data } = await http.post('/api/chat/reset', { session_id })
  return data
}

export async function getChatSessions(limit = 50) {
  const { data } = await http.get('/api/chat/sessions', {
    params: { limit },
  })
  return data
}

export async function deleteChatSession(sessionId) {
  const { data } = await http.delete(`/api/chat/sessions/${encodeURIComponent(sessionId)}`)
  return data
}

export async function renameChatSession(sessionId, title) {
  const { data } = await http.patch(`/api/chat/sessions/${encodeURIComponent(sessionId)}`, { title })
  return data
}

export async function getChatRecords(limit = 20, session_id = null) {
  const { data } = await http.get('/api/chat/records', {
    params: { limit, session_id },
  })
  return data
}

export async function getChatRecordDetail(id) {
  const { data } = await http.get(`/api/chat/records/${id}`)
  return data
}
