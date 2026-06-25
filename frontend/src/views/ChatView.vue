<template>
  <div class="chat-view">
    <div class="conversation-panel">
      <div class="panel-header">
        <div class="header-left">
          <div class="header-info">
            <h2>知识库智能检索问答</h2>
            <p class="subtitle">与您的 RAG 知识库对话，右侧控制台展示当前会话最新回答的推理与检索 Trace。</p>
          </div>
        </div>

        <div class="header-actions">
          <el-button
            type="text"
            @click="isInspectorCollapsed = !isInspectorCollapsed"
            class="toggle-inspector-btn"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="action-icon" :class="{ rotated: !isInspectorCollapsed }">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="15" y1="3" x2="15" y2="21"></line>
            </svg>
            {{ isInspectorCollapsed ? '展开控制台' : '收起控制台' }}
          </el-button>

          <el-button
            v-if="chatStore.messages.length > 0"
            type="text"
            @click="handleResetCurrentSession"
            class="reset-btn"
            :disabled="chatStore.loading"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="reset-icon">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            重置会话
          </el-button>
        </div>
      </div>

      <div ref="messageListRef" class="message-list">
        <div class="message-list-container">
          <div v-if="chatStore.messages.length === 0" class="welcome-box">
            <h2 class="welcome-title">欢迎使用 Agentic RAG Studio</h2>
            <p class="welcome-subtitle">输入任务或问题，智能助手将为您提供基于知识库的精准解答。</p>
          </div>

          <MessageBubble
            v-for="msg in chatStore.messages"
            :key="msg.id"
            :message="msg"
          />

          <div v-if="chatStore.loading && isWaitingResponse" class="loading-bubble">
            <div class="avatar-box">
              <div class="avatar bot">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="avatar-svg">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M12 2v2M8 5a4 4 0 0 1 8 0"></path>
                </svg>
              </div>
            </div>
            <div class="loading-card glass-card">
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-text">分析查询并检索中，请稍候...</span>
            </div>
          </div>
        </div>
      </div>

      <div class="input-panel">
        <div class="input-panel-container">
          <ChatInput
            ref="chatInputRef"
            :loading="chatStore.loading"
            @send="handleSendMessage"
          />
        </div>
      </div>
    </div>

    <div class="inspector-panel" :class="{ collapsed: isInspectorCollapsed }">
      <div class="inspector-header animate-fade-in" v-if="!isInspectorCollapsed">
        <h3>诊断控制台 (Inspector)</h3>
        <span class="console-badge">当前会话</span>
      </div>

      <div class="inspector-body" v-if="!isInspectorCollapsed">
        <QueryAnalysisCard
          :analysis="chatStore.latestResponse?.query_analysis"
        />

        <SourcePanel
          :sources="chatStore.latestResponse?.sources || []"
        />

        <RetrievalTracePanel
          :traces="chatStore.latestResponse?.retrieval_traces || []"
        />

        <div class="metadata-card glass-card animate-fade-in" v-if="chatStore.latestResponse?.meta">
          <div class="meta-header">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="meta-icon">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="3" x2="9" y2="21"></line>
              <line x1="15" y1="3" x2="15" y2="21"></line>
              <line x1="3" y1="9" x2="21" y2="9"></line>
              <line x1="3" y1="15" x2="21" y2="15"></line>
            </svg>
            <span>RAG 模型配置</span>
          </div>
          <div class="meta-body">
            <div class="meta-row">
              <span class="lbl">LLM 模型</span>
              <span class="val">{{ chatStore.latestResponse.meta.llm_model || '-' }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">稠密检索模型 (Dense)</span>
              <span class="val">{{ chatStore.latestResponse.meta.dense_model }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">稀疏检索模型 (Sparse)</span>
              <span class="val">{{ chatStore.latestResponse.meta.sparse_model }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">相似度阈值 (Threshold)</span>
              <span class="val highlighted">{{ chatStore.latestResponse.meta.score_threshold }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">候选 / 最终 Top-K</span>
              <span class="val">{{ chatStore.latestResponse.meta.candidate_top_k || '-' }} / {{ chatStore.latestResponse.meta.final_top_k || '-' }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">Rerank</span>
              <span class="val">
                {{ chatStore.latestResponse.meta.rerank_enabled ? `${chatStore.latestResponse.meta.rerank_provider}/${chatStore.latestResponse.meta.rerank_model}` : 'off' }}
              </span>
            </div>
            <div class="meta-row">
              <span class="lbl">上下文预算</span>
              <span class="val">{{ chatStore.latestResponse.meta.context_max_chunks || '-' }} chunks / {{ chatStore.latestResponse.meta.context_max_tokens || '-' }} tokens</span>
            </div>
          </div>
        </div>

        <div class="metadata-card glass-card animate-fade-in" v-if="chatStore.latestResponse?.meta?.fact_memories?.length || chatStore.latestResponse?.meta?.behavior_memories?.length">
          <div class="meta-header">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="meta-icon">
              <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
              <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"></path>
            </svg>
            <span>命中长期记忆</span>
          </div>
          <div class="meta-body memory-diagnostic-body">
            <div v-if="chatStore.latestResponse.meta.fact_memories?.length" class="memory-sec">
              <div class="sec-title">事实决策记忆 (Fact)</div>
              <ul class="sec-list">
                <li v-for="(fm, idx) in chatStore.latestResponse.meta.fact_memories" :key="idx" class="sec-item">
                  {{ fm }}
                </li>
              </ul>
            </div>

            <div v-if="chatStore.latestResponse.meta.behavior_memories?.length" class="memory-sec">
              <div class="sec-title">行为偏好约束 (Behavior)</div>
              <ul class="sec-list">
                <li v-for="(bm, idx) in chatStore.latestResponse.meta.behavior_memories" :key="idx" class="sec-item">
                  {{ bm }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatInput from '@/components/chat/ChatInput.vue'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import QueryAnalysisCard from '@/components/chat/QueryAnalysisCard.vue'
import SourcePanel from '@/components/chat/SourcePanel.vue'
import RetrievalTracePanel from '@/components/chat/RetrievalTracePanel.vue'
import { ElMessageBox, ElMessage } from 'element-plus'

const chatStore = useChatStore()
const messageListRef = ref(null)
const isInspectorCollapsed = ref(false)
const chatInputRef = ref(null)

const handleStarterClick = (promptText) => {
  if (chatInputRef.value) {
    chatInputRef.value.prefill(promptText)
  }
}

onMounted(() => {
  if (window.innerWidth < 1024) {
    isInspectorCollapsed.value = true
  }
})

const isWaitingResponse = computed(() => {
  if (chatStore.messages.length === 0) return false
  return chatStore.messages[chatStore.messages.length - 1].role === 'user'
})

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTo({
        top: messageListRef.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  })
}

const handleSendMessage = async (msgText) => {
  await chatStore.sendMessage(msgText)
  scrollToBottom()
}

const handleResetCurrentSession = () => {
  ElMessageBox.confirm(
    '重置会话会清空当前对话区和右侧诊断数据，并开启一个新的空会话。确定继续吗？',
    '提示',
    {
      confirmButtonText: '确定重置',
      cancelButtonText: '取消',
      type: 'info',
    }
  ).then(async () => {
    await chatStore.resetSession()
    ElMessage.success('会话已重置')
  }).catch(() => {})
}
</script>

<style scoped>
.chat-view {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.conversation-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  height: 100%;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.panel-header {
  height: 64px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.toggle-history-btn {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  margin-right: 8px;
  flex-shrink: 0;
}

.toggle-history-btn:hover {
  color: var(--color-primary-hover) !important;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.header-info h2 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.header-info .subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.toggle-inspector-btn {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  display: flex;
  align-items: center;
  gap: 6px;
}

.toggle-inspector-btn:hover {
  color: var(--color-primary-hover) !important;
}

.action-icon {
  width: 14px;
  height: 14px;
  transition: transform var(--transition-normal);
}

.action-icon.rotated {
  transform: rotate(180deg);
}

.reset-btn {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  display: flex;
  align-items: center;
  gap: 6px;
}

.reset-btn:hover {
  color: var(--color-danger-hover) !important;
}

.reset-icon {
  width: 14px;
  height: 14px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.message-list-container {
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.welcome-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: auto;
  max-width: 460px;
  text-align: center;
  padding: 40px 20px;
}

.logo-large {
  width: 64px;
  height: 64px;
  background-color: rgba(22, 119, 255, 0.05);
  border: 1px solid rgba(22, 119, 255, 0.2);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  box-shadow: 0 0 20px rgba(22, 119, 255, 0.1);
}

.logo-svg {
  width: 32px;
  height: 32px;
  color: var(--color-primary);
}

.welcome-box h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.welcome-box p {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.input-panel {
  padding: 14px 24px 24px 24px;
  flex-shrink: 0;
  background-color: var(--bg-primary);
  border-top: 1px solid rgba(255, 255, 255, 0.015);
}

.input-panel-container {
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

.loading-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  align-self: flex-start;
}

.avatar-box {
  flex-shrink: 0;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
}

.avatar.bot {
  background-color: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
}

.avatar-svg {
  width: 18px;
  height: 18px;
}

.loading-card {
  padding: 12px 18px;
  border-radius: var(--border-radius-md);
  border-bottom-left-radius: 2px;
  color: var(--text-secondary);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 42px;
}

.loading-text {
  font-size: 13px;
  color: var(--text-muted);
  margin-left: 6px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  background-color: var(--color-primary);
  border-radius: 50%;
  display: inline-block;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1.0); }
}

.inspector-panel {
  width: 380px;
  background-color: var(--bg-secondary);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  transition: width var(--transition-normal) cubic-bezier(0.4, 0, 0.2, 1);
}

.inspector-panel.collapsed {
  width: 0;
  border-left: none;
}

.inspector-header {
  height: 64px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.inspector-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.console-badge {
  font-size: 11px;
  background-color: rgba(16, 185, 129, 0.08);
  color: var(--color-success);
  border: 1px solid rgba(16, 185, 129, 0.2);
  padding: 1px 6px;
  border-radius: 12px;
  font-weight: 600;
}

.inspector-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metadata-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
}

.meta-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(75, 85, 99, 0.15);
  padding-bottom: 8px;
}

.meta-icon {
  width: 15px;
  height: 15px;
  color: var(--text-secondary);
}

.meta-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.meta-row .lbl {
  color: var(--text-secondary);
}

.meta-row .val {
  color: var(--text-primary);
  font-weight: 600;
}

.meta-row .val.highlighted {
  color: var(--color-primary-hover);
}

.memory-diagnostic-body {
  display: flex;
  flex-direction: column;
  gap: 12px !important;
  padding-top: 4px;
}

.memory-sec {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sec-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}

.sec-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sec-item {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  background-color: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  border-radius: var(--border-radius-sm);
  border-left: 2px solid var(--color-primary);
  word-break: break-all;
}

.memory-sec:last-child .sec-item {
  border-left-color: #a855f7;
}

/* Welcome Page Grid Styles (Script style) */
.welcome-title {
  font-size: 26px;
  font-weight: 850;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.welcome-subtitle {
  font-size: 13.5px;
  color: var(--text-muted);
  margin-bottom: 28px;
  max-width: 440px;
  line-height: 1.5;
}

.starter-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 520px;
}

.starter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast) ease;
}

.starter-card:hover {
  border-color: var(--color-primary);
  background-color: var(--color-primary-bg);
  transform: translateY(-0.5px);
}

.starter-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.starter-icon-box {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.starter-icon-box.write { background-color: rgba(245, 158, 11, 0.08); color: #d97706; }
.starter-icon-box.image { background-color: rgba(0, 133, 255, 0.08); color: #0085ff; }
.starter-icon-box.avatar { background-color: rgba(16, 185, 129, 0.08); color: #10b981; }
.starter-icon-box.code { background-color: rgba(239, 68, 68, 0.08); color: #ef4444; }

.starter-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.starter-plus {
  color: var(--text-muted);
  font-size: 15px;
  font-weight: 700;
  transition: color 0.15s ease;
}

.starter-card:hover .starter-plus {
  color: var(--color-primary);
}

@media (max-width: 768px) {
  .panel-header {
    padding: 0 16px;
    height: 56px;
  }

  .header-info .subtitle {
    display: none;
  }

  .message-list {
    padding: 16px 12px;
  }

  .input-panel {
    padding: 12px 16px 16px 16px;
  }
}
</style>
