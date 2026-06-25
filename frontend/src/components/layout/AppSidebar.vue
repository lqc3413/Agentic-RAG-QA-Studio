<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-top">
      <!-- 品牌 LOGO & 顶部收起按钮区域 -->
      <div class="sidebar-header-row">
        <div class="brand-container" v-if="!isCollapsed">
          <div class="logo-grid">
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
          </div>
          <span class="brand-name">Agentic RAG Studio</span>
        </div>
        <div class="brand-container collapsed-logo" v-else>
          <div class="logo-grid">
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
            <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
          </div>
        </div>

        <!-- 顶部折叠收起按钮 (ChatGPT 风格) -->
        <button class="header-toggle-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="header-toggle-icon">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </button>
      </div>

      <!-- 模块导航 -->
      <nav class="nav-links">
        <!-- 新对话菜单项 (ChatGPT 风格) -->
        <el-tooltip content="新对话" placement="right" :disabled="!isCollapsed">
          <button class="nav-link-btn" @click="handleNewSession" :disabled="isBusy">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-icon">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4z"></path>
            </svg>
            <span v-if="!isCollapsed" class="nav-text">新对话</span>
          </button>
        </el-tooltip>

        <el-tooltip content="知识库问答" placement="right" :disabled="!isCollapsed">
          <router-link to="/chat" class="nav-link" active-class="active">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-icon">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span v-if="!isCollapsed" class="nav-text">知识库问答</span>
          </router-link>
        </el-tooltip>
        
        <el-tooltip content="文档管理" placement="right" :disabled="!isCollapsed">
          <router-link to="/documents" class="nav-link" active-class="active">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-icon">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span v-if="!isCollapsed" class="nav-text">文档管理</span>
          </router-link>
        </el-tooltip>

        <el-tooltip content="评估报告" placement="right" :disabled="!isCollapsed">
          <router-link to="/eval" class="nav-link" active-class="active">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-icon">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
            <span v-if="!isCollapsed" class="nav-text">评估报告</span>
          </router-link>
        </el-tooltip>

        <el-tooltip content="记忆管理" placement="right" :disabled="!isCollapsed">
          <router-link to="/memory" class="nav-link" active-class="active">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="nav-icon">
              <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
              <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"></path>
            </svg>
            <span v-if="!isCollapsed" class="nav-text">记忆管理</span>
          </router-link>
        </el-tooltip>
      </nav>
    </div>

    <!-- 中间会话列表区域 -->
    <div v-if="!isCollapsed" class="sidebar-middle">
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索会话..."
          clearable
          size="small"
          class="dark-search-input"
        >
          <template #prefix>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="search-icon">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </template>
        </el-input>
      </div>

      <!-- 会话历史流 -->
      <div class="sessions-container">
        <div v-if="chatStore.sessionsLoading && chatStore.sessions.length === 0" class="loading-state">
          <div class="mini-spinner">
            <span class="spinner-dot"></span>
            <span class="spinner-dot"></span>
            <span class="spinner-dot"></span>
          </div>
          <span>读取中...</span>
        </div>

        <div v-else-if="chatStore.sessions.length === 0" class="empty-state">
          <span>暂无历史会话</span>
        </div>

        <div v-else-if="filteredSessions.length === 0" class="empty-state">
          <span>无匹配会话</span>
        </div>

        <div v-else class="sessions-list">
          <div
            v-for="item in filteredSessions"
            :key="item.session_id"
            class="session-item-card"
            :class="{ active: item.session_id === chatStore.session_id, disabled: isBusy }"
            @click="handleLoadSession(item.session_id)"
          >
            <div class="session-info">
              <div class="session-title-row">
                <span class="session-title-text" :title="item.title || '新会话'">
                  {{ item.title || '新会话' }}
                </span>
                
                <!-- 操作按钮在 hover 时展示 -->
                <div class="session-item-actions" @click.stop>
                  <button class="mini-btn" @click="handleRenameSession(item)" :disabled="isBusy" title="重命名">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mini-icon">
                      <path d="M12 20h9"></path>
                      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
                    </svg>
                  </button>
                  <button class="mini-btn danger" @click="handleDeleteSession(item)" :disabled="isBusy" title="删除">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mini-icon">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Meta info: Time and count -->
              <div class="session-meta-row">
                <span class="meta-time">{{ formatTime(item.updated_at) }}</span>
                <span class="meta-count">{{ item.record_count || 0 }} 条</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部控制与元数据 -->
    <div class="sidebar-footer">
      <!-- 仿真主题选择器 -->
      <div class="theme-selector-wrapper" v-if="!isCollapsed">
        <div class="theme-selector">
          <div 
            class="selector-option" 
            :class="{ active: currentTheme === 'light' }"
            @click="toggleTheme('light')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="selector-icon"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
            <span>浅色</span>
          </div>
          <div 
            class="selector-option"
            :class="{ active: currentTheme === 'dark' }"
            @click="toggleTheme('dark')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="selector-icon"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
            <span>深色</span>
          </div>
        </div>
      </div>

      <div v-if="!isCollapsed" class="system-meta">
        <div class="meta-label">RAG Engine</div>
        <div class="meta-value">LangGraph + Qdrant</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { ElMessage, ElMessageBox } from 'element-plus'

const chatStore = useChatStore()
const router = useRouter()
const route = useRoute()

const isCollapsed = ref(false)
const searchQuery = ref('')
const currentTheme = ref('light')

const toggleTheme = (themeName) => {
  currentTheme.value = themeName
  document.documentElement.setAttribute('data-theme', themeName)
  localStorage.setItem('app-theme', themeName)
}

const isBusy = computed(() => chatStore.loading || chatStore.sessionsLoading)

const refreshSessions = () => {
  chatStore.fetchSessions()
}

const handleNewSession = () => {
  if (isBusy.value) return
  chatStore.createNewSession()
  if (route.name !== 'chat') {
    router.push('/chat')
  }
}

const handleLoadSession = async (sessionId) => {
  if (isBusy.value || sessionId === chatStore.session_id) return
  await chatStore.loadSession(sessionId)
  if (route.name !== 'chat') {
    router.push('/chat')
  }
}

const handleRenameSession = async (item) => {
  if (isBusy.value) return

  try {
    const { value } = await ElMessageBox.prompt('请输入新的会话标题', '重命名会话', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: item.title || '',
      inputPattern: /\S+/,
      inputErrorMessage: '标题不能为空',
    })
    const title = (value || '').trim().slice(0, 80)
    if (!title) return
    await chatStore.renameSession(item.session_id, title)
    ElMessage.success('会话已重命名')
  } catch (err) {
    if (err !== 'cancel') {
      console.error('Rename session cancelled or failed:', err)
    }
  }
}

const handleDeleteSession = async (item) => {
  if (isBusy.value) return

  try {
    await ElMessageBox.confirm(
      `删除会话“${item.title || '新会话'}”？该会话中的问答记录也会被清理。`,
      '删除会话',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await chatStore.deleteSession(item.session_id)
    ElMessage.success('会话已删除')
  } catch (err) {
    if (err !== 'cancel') {
      console.error('Delete session cancelled or failed:', err)
    }
  }
}

const formatTime = (isoString) => {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    if (Number.isNaN(date.getTime())) return isoString

    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')

    return `${month}-${day} ${hours}:${minutes}`
  } catch (e) {
    return isoString
  }
}

const filteredSessions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return chatStore.sessions
  return chatStore.sessions.filter(s => {
    const titleMatch = (s.title || '').toLowerCase().includes(query)
    const questionMatch = (s.last_question || '').toLowerCase().includes(query)
    return titleMatch || questionMatch
  })
})

onMounted(() => {
  refreshSessions()
  if (window.innerWidth < 1024) {
    isCollapsed.value = true
  }

  // 主题检测与初始化
  const savedTheme = localStorage.getItem('app-theme') || 'light'
  currentTheme.value = savedTheme
  document.documentElement.setAttribute('data-theme', savedTheme)
})
</script>

<style scoped>
.app-sidebar {
  width: 280px;
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: width var(--transition-normal) cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: 68px;
}

.sidebar-top {
  padding: 16px 16px 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.collapsed .sidebar-top {
  padding: 16px 10px 8px 10px;
  align-items: center;
}

/* 顶部品牌 & 收起按钮栏 */
.sidebar-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 4px;
}

.collapsed .sidebar-header-row {
  flex-direction: column;
  gap: 12px;
  align-items: center;
  margin-bottom: 0;
}

.collapsed .brand-container {
  padding-left: 0;
  justify-content: center;
  width: 100%;
}

.brand-container {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 4px;
  animation: fadeIn var(--transition-normal) forwards;
}

.collapsed-logo {
  padding-left: 0;
}

.logo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 3px;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.logo-dot {
  width: 4px;
  height: 4px;
  background-color: var(--text-primary);
  border-radius: 50%;
}

.brand-name {
  font-size: 17px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

/* 顶部收起按钮 */
.header-toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  width: 28px;
  height: 28px;
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast) ease;
  padding: 0;
}

.header-toggle-btn:hover {
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
}

.header-toggle-icon {
  width: 16px;
  height: 16px;
  stroke-width: 2;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.collapsed .nav-links {
  align-items: center;
}

.nav-link, .nav-link-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 16px;
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 13.5px;
  border-radius: 20px; /* Capsule shape */
  transition: all var(--transition-fast);
  white-space: nowrap;
  text-decoration: none;
  background: transparent;
  border: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.collapsed .nav-link, .collapsed .nav-link-btn {
  padding: 10px;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  gap: 0;
}

.nav-link:hover, .nav-link-btn:hover {
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-link.active {
  background-color: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: 700;
}

.nav-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

/* 中间会话列表 */
.sidebar-middle {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 1px solid var(--border-color);
  padding: 12px 16px 0 16px;
}

.search-box {
  margin-bottom: 12px;
}

.search-icon {
  width: 13px;
  height: 13px;
  color: var(--text-muted);
}

:deep(.dark-search-input .el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  box-shadow: none !important;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 0 12px;
}

:deep(.dark-search-input .el-input__wrapper.is-focus) {
  border-color: var(--color-primary) !important;
}

:deep(.dark-search-input .el-input__inner) {
  color: var(--text-primary) !important;
  font-size: 12px;
}

.sessions-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding-right: 2px;
}

/* 自定义滚动条 */
.sessions-container::-webkit-scrollbar {
  width: 4px;
}
.sessions-container::-webkit-scrollbar-track {
  background: transparent;
}
.sessions-container::-webkit-scrollbar-thumb {
  background: rgba(9, 11, 30, 0.05);
  border-radius: 2px;
}
.sessions-container::-webkit-scrollbar-thumb:hover {
  background: rgba(9, 11, 30, 0.12);
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 30px 10px;
  color: var(--text-muted);
  font-size: 12px;
  gap: 8px;
}

.mini-spinner {
  display: flex;
  gap: 4px;
}

.spinner-dot {
  width: 5px;
  height: 5px;
  background-color: var(--color-primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.spinner-dot:nth-child(1) { animation-delay: -0.32s; }
.spinner-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1.0); }
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 16px;
}

.session-item-card {
  padding: 10px 12px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item-card:hover {
  border-color: var(--border-color-hover);
  transform: translateY(-0.5px);
}

.session-item-card.active {
  background-color: var(--color-primary-bg);
  border-color: rgba(0, 133, 255, 0.25);
}

.session-item-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.session-title-text {
  font-size: 12.5px;
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.session-item-card.active .session-title-text {
  color: var(--color-primary);
}

.session-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s ease;
  flex-shrink: 0;
}

.session-item-card:hover .session-item-actions {
  opacity: 1;
}

.mini-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.mini-btn:hover {
  background-color: rgba(9, 11, 30, 0.04);
  color: var(--text-primary);
}

.mini-btn.danger:hover {
  background-color: rgba(239, 68, 68, 0.08);
  color: var(--color-danger);
}

.mini-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.mini-icon {
  width: 11px;
  height: 11px;
}

.session-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10.5px;
  color: var(--text-muted);
}

.meta-time {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-count {
  flex-shrink: 0;
}

/* 底部区域 */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 10px;
  background-color: var(--bg-primary);
}

.collapsed .sidebar-footer {
  padding: 12px 10px;
  align-items: center;
}

/* 仿真主题选择器 */
.theme-selector-wrapper {
  padding: 0 2px;
}

.theme-selector {
  display: flex;
  background-color: var(--bg-tertiary);
  border-radius: 20px;
  padding: 2px;
  border: 1px solid var(--border-color);
}

.selector-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 5px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.selector-option.active {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.selector-icon {
  width: 11px;
  height: 11px;
}

.system-meta {
  background-color: var(--bg-tertiary);
  padding: 8px 12px;
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-color);
}

.meta-label {
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.meta-value {
  font-size: 10.5px;
  color: var(--text-secondary);
  font-weight: 700;
}

/* 渐显 */
.animate-fade-in {
  animation: fadeIn 0.2s ease-out forwards;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
