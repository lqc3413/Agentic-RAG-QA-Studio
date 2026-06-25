<template>
  <div class="message-bubble" :class="[message.role, { 'has-error': message.is_error }]">
    <!-- Avatar -->
    <div class="avatar-box">
      <div v-if="message.role === 'user'" class="avatar user">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="avatar-svg">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      </div>
      <div v-else class="avatar bot" :class="{ unclear: message.is_clear === false }">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="avatar-svg">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M12 2v2M8 5a4 4 0 0 1 8 0"></path>
        </svg>
      </div>
    </div>

    <!-- Content Card -->
    <div class="content-wrapper">
      <div class="sender-name">
        <template v-if="message.role === 'user'">用户</template>
        <template v-else-if="message.is_clear === false">分析助手 (澄清请求)</template>
        <template v-else>智能助手</template>
      </div>
      
      <div class="content-card" :class="{ 'is-clarify': message.is_clear === false }">
        <!-- Query Analysis inside Assistant Bubble -->
        <template v-if="message.role === 'assistant' && message.query_analysis">
          <details class="bubble-details query-details" open>
            <summary class="details-summary">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="details-icon query-icon">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <span>查询分析与重写</span>
            </summary>
            <div class="details-content">
              <div class="clarity-status">
                <span class="status-dot" :class="{ 'is-clear': message.query_analysis.is_clear }"></span>
                <span>{{ message.query_analysis.is_clear ? '查询意图明确' : '查询意图需澄清' }}</span>
              </div>
              <div class="rewritten-box" v-if="message.query_analysis.rewritten_queries && message.query_analysis.rewritten_queries.length > 0">
                <strong>已重写查询：</strong>
                <ul>
                  <li v-for="(q, idx) in message.query_analysis.rewritten_queries" :key="idx">{{ q }}</li>
                </ul>
              </div>
              <div class="clarify-reason" v-if="message.query_analysis.clarification_needed">
                <strong>澄清理由：</strong>
                <p>{{ message.query_analysis.clarification_needed }}</p>
              </div>
            </div>
          </details>
        </template>

        <!-- System Alerts inside Assistant Bubble -->
        <template v-if="message.role === 'assistant' && message.system_alerts && message.system_alerts.length > 0">
          <details 
            v-for="(alert, index) in message.system_alerts" 
            :key="'alert-' + index" 
            class="bubble-details system-details"
            open
          >
            <summary class="details-summary">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="details-icon system-icon">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="9" x2="15" y2="9"></line>
                <line x1="9" y1="13" x2="15" y2="13"></line>
                <line x1="9" y1="17" x2="15" y2="17"></line>
                <line x1="5" y1="9" x2="5.01" y2="9"></line>
                <line x1="5" y1="13" x2="5.01" y2="13"></line>
                <line x1="5" y1="17" x2="5.01" y2="17"></line>
              </svg>
              <span>{{ alert.title }}</span>
            </summary>
            <div class="details-content">
              {{ alert.content }}
            </div>
          </details>
        </template>

        <!-- Render User text directly (plain text) -->
        <span v-if="message.role === 'user'" class="plain-text">{{ message.content }}</span>
        
        <!-- Render Assistant markdown (cleaned HTML) or Loading status -->
        <div v-else class="assistant-content-area">
          <div v-if="!message.content && !message.is_error" class="ai-thinking-loader">
            <span class="thinking-text">智能助手正在思考中</span>
            <div class="thinking-dots">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
          <div v-else>
            <div v-html="renderedHtml" class="markdown-body"></div>
            

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const md = new MarkdownIt({
  html: false, // 确保转义原始 HTML
  linkify: true,
  typographer: true,
})

const renderedHtml = computed(() => {
  if (!props.message.content) return ''
  const rawHtml = md.render(props.message.content)
  return DOMPurify.sanitize(rawHtml)
})</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  max-width: 90%;
  align-self: flex-start;
  animation: slideIn 0.25s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.message-bubble.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.user .content-wrapper {
  align-items: flex-end;
}

.user .content-card {
  border-top-left-radius: var(--border-radius-md) !important;
  border-top-right-radius: 2px !important;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 气泡内部 RAG 追踪细节的样式 */
.bubble-details {
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  margin-bottom: 12px;
  overflow: hidden;
  transition: all var(--transition-fast);
}

.bubble-details[open] {
  background-color: var(--bg-tertiary);
  border-color: var(--color-primary-hover);
}

.details-summary {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
  outline: none;
  transition: color var(--transition-fast) ease;
}

.bubble-details[open] .details-summary {
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
}

.details-summary::-webkit-details-marker {
  display: none;
}

.details-summary::before {
  content: '▶';
  font-size: 8px;
  color: var(--text-muted);
  transition: transform var(--transition-fast) ease;
  display: inline-block;
}

.bubble-details[open] .details-summary::before {
  transform: rotate(90deg);
}

.details-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

.details-icon.system-icon {
  color: var(--color-warning);
}

.details-icon.query-icon {
  color: var(--color-primary);
}

.details-content {
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-secondary);
  background-color: rgba(9, 11, 30, 0.02);
  word-break: break-all;
  font-family: var(--font-mono);
}

/* 问题清晰度状态的特定样式 */
.clarity-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 750;
  margin-bottom: 10px;
  font-size: 12px;
}

.status-dot {
  width: 6px;
  height: 6px;
  background-color: var(--color-danger);
  border-radius: 50%;
}

.status-dot.is-clear {
  background-color: var(--color-success);
}

.rewritten-box strong, .clarify-reason strong {
  font-size: 10.5px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.rewritten-box ul {
  margin-left: 14px;
  margin-bottom: 0;
  padding-left: 0;
}

.rewritten-box li {
  margin-bottom: 4px;
  list-style-type: square;
  color: var(--text-secondary);
}

.clarify-reason p {
  margin: 0;
  font-style: italic;
  color: var(--color-warning);
}

.avatar-box {
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
}

.avatar.user {
  background-color: var(--bg-tertiary);
  color: var(--text-secondary);
  border-color: var(--border-color);
}

.avatar.bot {
  background-color: var(--text-primary);
  color: var(--bg-secondary);
  border-color: var(--text-primary);
}

.avatar.bot.unclear {
  background-color: var(--color-warning-bg);
  color: var(--color-warning);
  border-color: rgba(245, 158, 11, 0.2);
}

.avatar-svg {
  width: 16px;
  height: 16px;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.sender-name {
  font-size: 11.5px;
  color: var(--text-muted);
  font-weight: 700;
  padding-left: 4px;
}

.content-card {
  padding: 12px 18px;
  border-radius: var(--border-radius-md);
  box-shadow: 0 1px 3px rgba(9, 11, 30, 0.05);
  font-size: 14px;
  line-height: 1.6;
  border-top-left-radius: 2px;
  width: fit-content;
  max-width: 100%;
}

.user .content-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.assistant .content-card {
  background-color: #f8fafc;
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.assistant .content-card.is-clarify {
  border-color: rgba(245, 158, 11, 0.25);
  background-color: var(--color-warning-bg);
}

.has-error .content-card {
  border-color: rgba(255, 77, 79, 0.25) !important;
  color: var(--color-danger-hover) !important;
  background-color: var(--color-danger-bg) !important;
}

.plain-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 气泡内 Markdown 渲染的覆盖样式 */
.markdown-body {
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin-bottom: 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(code) {
  background-color: rgba(9, 11, 30, 0.04);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.88em;
  color: #ef4444;
}

.markdown-body :deep(pre) {
  background-color: #0f172a;
  border: 1px solid #1e293b;
  border-radius: var(--border-radius-md);
  padding: 12px 14px;
  margin: 12px 0;
  overflow-x: auto;
  box-shadow: inset 0 1px 4px rgba(0,0,0,0.25);
}

.markdown-body :deep(pre code) {
  background-color: transparent;
  padding: 0;
  font-size: 0.85em;
  color: #e2e8f0;
  font-family: var(--font-mono);
}

.markdown-body :deep(ul), .markdown-body :deep(ol) {
  margin-left: 20px;
  margin-bottom: 8px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

/* AI 思考中加载器 */
.assistant-content-area {
  min-height: 24px;
  display: flex;
  flex-direction: column;
}

.ai-thinking-loader {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
  user-select: none;
  padding: 2px 0;
}

.thinking-text {
  font-weight: 400;
  letter-spacing: 0.5px;
}

.thinking-dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.thinking-dots .dot {
  width: 5px;
  height: 5px;
  background-color: var(--color-primary);
  border-radius: 50%;
  opacity: 0.4;
  animation: pulse-dot 1.4s infinite both;
}

.thinking-dots .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking-dots .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes pulse-dot {
  0%, 100% {
    transform: scale(0.8);
    opacity: 0.4;
  }
  50% {
    transform: scale(1.2);
    opacity: 1;
  }
}

/* 气泡下方动作控制栏 */
.bubble-action-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.action-footer-btn {
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: color var(--transition-fast) ease;
  padding: 0;
}

.action-footer-btn:hover {
  color: var(--color-primary);
}

.footer-btn-icon {
  width: 11px;
  height: 11px;
}
</style>
