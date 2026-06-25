import { defineStore } from 'pinia'
import {
  sendChatMessageStream,
  resetChatSession,
  getChatSessions,
  deleteChatSession,
  renameChatSession,
  getChatRecords,
  getChatRecordDetail,
} from '@/api/chat'

function generateUUID() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

const parseJsonField = (value, fallback) => {
  if (!value) return fallback
  if (typeof value !== 'string') return value

  try {
    return JSON.parse(value)
  } catch (err) {
    console.warn('Failed to parse chat record JSON:', err)
    return fallback
  }
}

const buildSourcesFromTraces = (traces) => {
  const sources = []
  const seenKeys = new Set()

  for (const trace of traces || []) {
    for (const candidate of trace.candidates || []) {
      if (candidate.status !== 'selected') continue

      const sourceKey = [
        candidate.source || '',
        candidate.parent_id || '',
        candidate.content_preview || '',
      ].join('|')
      if (seenKeys.has(sourceKey)) continue

      sources.push({
        source_id: candidate.citation_id || `S${sources.length + 1}`,
        source: candidate.source || '',
        parent_id: candidate.parent_id || '',
        score: Number(candidate.score || 0),
        threshold: Number(candidate.threshold || 0),
        rerank_score: candidate.rerank_score !== null && candidate.rerank_score !== undefined
          ? Number(candidate.rerank_score)
          : null,
        content_preview: candidate.content_preview || '',
      })
      seenKeys.add(sourceKey)
    }
  }

  return sources
}

const buildLatestResponseFromRecord = (record) => {
  const parsedTraces = parseJsonField(record.trace_json, [])
  const traces = Array.isArray(parsedTraces) ? parsedTraces : []
  const meta = parseJsonField(record.meta_json, null)
  const rewrittenQueries = traces.map(t => t.query).filter(Boolean)
  const isClarificationFailure = record.failure_reason === 'Query clarification needed'
  const queryClear = record.answerable || traces.length > 0 || !isClarificationFailure

  return {
    query_analysis: queryClear ? {
      is_clear: true,
      rewritten_queries: rewrittenQueries,
      clarification_needed: '',
    } : {
      is_clear: false,
      rewritten_queries: [],
      clarification_needed: record.failure_reason || '无法作答',
    },
    retrieval_traces: traces,
    sources: buildSourcesFromTraces(traces),
    meta,
  }
}

const buildMessagesFromRecords = (records) => {
  return records.flatMap((record) => {
    const answerContent = (record.answer || '').trim()
    const hasValidAnswer = answerContent.length > 0
      && !answerContent.startsWith('❌')
      && !answerContent.startsWith('⚠️')
      && !answerContent.toLowerCase().startsWith('unable to generate')
    const isClarificationFailure = record.failure_reason === 'Query clarification needed'

    let system_alerts = []
    if (!record.answerable && !hasValidAnswer) {
      system_alerts.push({
        title: '检索失败分析',
        content: record.failure_reason || '未能检索到满足相关性阈值的文档片段。',
      })
    } else {
      // 成功回答的情况，根据 sources_count 和 rejected_sources_count 还原卡片类型
      if (record.sources_count > 0) {
        system_alerts.push({
          title: '知识库检索应答',
          content: `已参考知识库中的 ${record.sources_count} 个关联片段进行解答。`,
        })
      } else if (record.rejected_sources_count > 0) {
        system_alerts.push({
          title: '知识库检索未果',
          content: '已发起检索，但未找到关联文档。已通过大模型常识解答。',
        })
      } else {
        system_alerts.push({
          title: '上下文直接对话',
          content: '此提问属于直接对话，已结合会话历史直接回答。',
        })
      }
    }

    return [
      {
        id: `record-${record.id}-user`,
        role: 'user',
        content: record.question || '',
      },
      {
        id: `record-${record.id}-assistant`,
        role: 'assistant',
        content: record.answer || '',
        is_clear: record.answerable || hasValidAnswer,
        query_analysis: isClarificationFailure ? {
          is_clear: false,
          rewritten_queries: [],
          clarification_needed: record.failure_reason || '此问题需要澄清',
        } : null,
        system_alerts: system_alerts,
      },
    ]
  })
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    session_id: (() => {
      let id = localStorage.getItem('session_id')
      if (!id) {
        id = generateUUID()
        localStorage.setItem('session_id', id)
      }
      return id
    })(),
    messages: [],
    latestResponse: null,
    sessions: [],
    sessionsLoading: false,
    loading: false,
    error: null,
  }),
  actions: {
    async fetchSessions() {
      this.sessionsLoading = true
      try {
        const res = await getChatSessions(50)
        this.sessions = res.sessions || []
      } catch (err) {
        console.error('Failed to fetch chat sessions:', err)
        this.error = err.message || 'Failed to fetch chat sessions'
      } finally {
        this.sessionsLoading = false
      }
    },
    createNewSession() {
      const newId = generateUUID()
      localStorage.setItem('session_id', newId)
      this.session_id = newId
      this.messages = []
      this.latestResponse = null
      this.error = null
    },
    async loadSession(sessionId) {
      if (!sessionId || sessionId === this.session_id) return

      this.loading = true
      this.error = null
      try {
        localStorage.setItem('session_id', sessionId)
        this.session_id = sessionId

        const res = await getChatRecords(100, sessionId)
        const records = [...(res.records || [])].sort((a, b) => {
          const aTime = new Date(a.created_at || 0).getTime()
          const bTime = new Date(b.created_at || 0).getTime()
          if (aTime !== bTime) return aTime - bTime
          return Number(a.id || 0) - Number(b.id || 0)
        })

        this.messages = buildMessagesFromRecords(records)
        this.latestResponse = null

        const lastRecord = records[records.length - 1]
        if (lastRecord?.id !== undefined && lastRecord?.id !== null) {
          const detail = await getChatRecordDetail(lastRecord.id)
          this.latestResponse = buildLatestResponseFromRecord(detail)
        }
      } catch (err) {
        console.error('Failed to load chat session:', err)
        this.error = err.message || 'Failed to load chat session'
      } finally {
        this.loading = false
      }
    },
    async deleteSession(sessionId) {
      if (!sessionId) return

      this.loading = true
      this.error = null
      try {
        await deleteChatSession(sessionId)
        if (sessionId === this.session_id) {
          this.createNewSession()
        }
        await this.fetchSessions()
      } catch (err) {
        console.error('Failed to delete chat session:', err)
        this.error = err.message || 'Failed to delete chat session'
      } finally {
        this.loading = false
      }
    },
    async renameSession(sessionId, title) {
      const trimmed = (title || '').trim().slice(0, 80)
      if (!sessionId || !trimmed) return

      this.loading = true
      this.error = null
      try {
        await renameChatSession(sessionId, trimmed)
        await this.fetchSessions()
      } catch (err) {
        console.error('Failed to rename chat session:', err)
        this.error = err.message || 'Failed to rename chat session'
      } finally {
        this.loading = false
      }
    },
    async sendMessage(messageText) {
      if (!messageText.trim()) return

      const userMessageId = Date.now()
      this.messages.push({
        id: userMessageId,
        role: 'user',
        content: messageText.trim(),
      })

      this.loading = true
      this.error = null

      const assistantMessageId = Date.now() + 1
      const assistantMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        is_clear: true,
        query_analysis: null,
        system_alerts: [],
      }
      this.messages.push(assistantMessage)

      this.latestResponse = {
        query_analysis: { is_clear: true, rewritten_queries: [], clarification_needed: '' },
        retrieval_traces: [],
        sources: [],
        meta: null,
      }

      try {
        await sendChatMessageStream(messageText, this.session_id, (chunk) => {
          const assistantIndex = this.messages.findIndex(m => m.id === assistantMessageId)
          if (assistantIndex === -1) return

          const msgObj = this.messages[assistantIndex]

          if (chunk.type === 'text') {
            msgObj.content += chunk.data
          } else if (chunk.type === 'final_answer') {
            msgObj.content = chunk.data
          } else if (chunk.type === 'query_analysis') {
            msgObj.query_analysis = chunk.data
            this.latestResponse.query_analysis = chunk.data
            if (chunk.data.is_clear === false) {
              msgObj.is_clear = false
            }
          } else if (chunk.type === 'system_alert') {
            if (!msgObj.system_alerts) {
              msgObj.system_alerts = []
            }
            msgObj.system_alerts = [...msgObj.system_alerts, chunk.data]
          } else if (chunk.type === 'traces') {
            this.latestResponse.retrieval_traces = chunk.data
          } else if (chunk.type === 'sources') {
            this.latestResponse.sources = chunk.data
          } else if (chunk.type === 'meta') {
            this.latestResponse.meta = chunk.data
          }
        })
      } catch (err) {
        console.error(err)
        this.error = err.message || 'Stream processing failed'

        const assistantIndex = this.messages.findIndex(m => m.id === assistantMessageId)
        if (assistantIndex > -1 && !this.messages[assistantIndex].content) {
          this.messages[assistantIndex].content = `❌ Error: ${this.error}. Please ensure the backend is running.`
          this.messages[assistantIndex].is_error = true
        }
      } finally {
        this.loading = false
        await this.fetchSessions()
      }
    },
    async resetSession() {
      this.loading = true
      try {
        await resetChatSession(this.session_id)
        this.createNewSession()
        await this.fetchSessions()
      } catch (err) {
        console.error(err)
        this.error = 'Failed to reset thread session'
      } finally {
        this.loading = false
      }
    },
  },
})
