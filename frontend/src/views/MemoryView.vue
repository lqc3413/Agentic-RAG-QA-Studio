<template>
  <div class="memory-view animate-fade-in">
    <!-- 头部区域 -->
    <div class="view-header">
      <div class="header-main">
        <h2>智能体记忆管理控制台</h2>
        <div class="header-actions">
          <el-button v-if="activeMainTab === 'facts'" type="primary" class="btn-primary" @click="openCreateDialog">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            手动注入事实
          </el-button>
        </div>
      </div>
      <p class="view-subtitle">查看和治理 Agent 跨会话的长期事实记忆与行为规范画像，维持上下文决策透明与精准控制。</p>
    </div>

    <!-- 主 Tabs 切换：事实库 与 用户画像 -->
    <div class="tabs-container main-tabs">
      <el-tabs v-model="activeMainTab" @tab-change="handleMainTabChange" class="memory-tabs">
        <el-tab-pane label="长期事实库 (Facts)" name="facts" />
        <el-tab-pane label="用户画像偏好 (User Profile)" name="profile" />
      </el-tabs>
    </div>

    <!-- 1. 长期事实库 -->
    <div v-if="activeMainTab === 'facts'" class="tab-content-wrapper">
      <!-- 检索与过滤控制区 -->
      <div class="filter-bar glass-card">
        <div class="search-input-wrapper">
          <el-input
            v-model="searchQuery"
            placeholder="输入关键词搜索事实记忆..."
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="search-icon">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </template>
          </el-input>
        </div>
        <div class="facts-count-info">
          <span>共 <strong>{{ filteredMemories.length }}</strong> 条事实</span>
        </div>
      </div>

      <!-- 列表展示区 -->
      <div v-loading="loading" class="list-section">
        <div v-if="filteredMemories.length === 0" class="empty-state glass-card">
          <div class="empty-icon-wrapper">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="empty-icon">
              <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
              <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"></path>
            </svg>
          </div>
          <h3>未查询到事实记忆</h3>
          <p>当您与 Agent 对话时，系统将自动从问答中提炼有价值的技术事实与决策。您也可以点击右上角手动注入一条事实。</p>
        </div>

        <div v-else class="memory-grid">
          <div 
            v-for="item in filteredMemories" 
            :key="item.id" 
            class="memory-card glass-card animate-fade-in"
          >
            <div class="card-header">
              <div class="tags-group">
                <el-tag :type="item.session_id ? 'warning' : 'success'" size="small" class="tag-item">
                  {{ item.session_id ? '会话级事实' : '全局事实' }}
                </el-tag>
                <el-tag v-if="item.session_id" type="info" size="small" class="tag-item">
                  session: {{ item.session_id.slice(0, 8) }}...
                </el-tag>
                <el-tag type="info" size="small" class="tag-item">
                  来源: {{ getSourceLabel(item.source) }}
                </el-tag>
              </div>
            </div>

            <div class="card-body">
              <p class="memory-content">{{ item.content }}</p>
            </div>

            <div class="card-metrics">
              <div class="metric-item">
                <span class="metric-label">重要度:</span>
                <div class="progress-bar-wrapper">
                  <div class="progress-track">
                    <div class="progress-fill importance" :style="{ width: `${item.importance * 100}%` }"></div>
                  </div>
                  <span class="metric-value">{{ (item.importance * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>

            <div class="card-footer">
              <div class="hit-meta">
                <span>🎯 命中: <strong>{{ item.hit_count }}</strong> 次</span>
                <span class="divider">|</span>
                <span>更新: {{ formatTime(item.updated_at) }}</span>
              </div>

              <div class="actions-group">
                <el-button type="primary" size="small" plain @click="openEditDialog(item)">
                  编辑
                </el-button>
                <el-button type="danger" size="small" plain @click="confirmDelete(item.id)" class="btn-delete">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 用户画像管理 -->
    <div v-else-if="activeMainTab === 'profile'" class="tab-content-wrapper">
      <div v-loading="loadingProfile" class="profile-layout">
        
        <!-- 基础偏好配置 -->
        <div class="glass-card profile-settings-card">
          <h3 class="card-title">基础习惯设定</h3>
          <el-form :model="profileForm" label-position="top" class="profile-form">
            <div class="form-row">
              <el-form-item label="首选语言 (preferred_language)" style="flex: 1;">
                <el-select v-model="profileForm.preferred_language" placeholder="选择回答语言" style="width: 100%;">
                  <el-option label="中文 (zh)" value="zh" />
                  <el-option label="英文 (en)" value="en" />
                </el-select>
              </el-form-item>
              
              <el-form-item label="回答风格 (response_style)" style="flex: 1;">
                <el-select v-model="profileForm.response_style" placeholder="选择回答风格" style="width: 100%;">
                  <el-option label="简洁精炼 (concise)" value="concise" />
                  <el-option label="详细完整 (detailed)" value="detailed" />
                  <el-option label="表格展示 (table)" value="table" />
                </el-select>
              </el-form-item>
            </div>
            
            <div class="form-actions-row">
              <el-button type="primary" :loading="savingProfile" @click="saveBaseProfile">
                保存基础设定
              </el-button>
            </div>
          </el-form>
        </div>

        <!-- 自定义协作规则列表 -->
        <div class="glass-card profile-rules-card">
          <div class="rules-header">
            <h3 class="card-title">自定义工作流规则与行为限制 (custom_rules)</h3>
            <p class="rules-subtitle">注入到智能体 System Prompt 的强制性前置规范约束。</p>
          </div>

          <!-- 新增规则栏 -->
          <div class="add-rule-bar">
            <el-input
              v-model="newRuleText"
              placeholder="添加新的自定义规则（例如：代码修改前必须先执行单元测试...）"
              clearable
              @keyup.enter="addNewRule"
            />
            <el-button type="primary" @click="addNewRule" class="btn-add-rule">
              添加规则
            </el-button>
          </div>

          <!-- 规则列表 -->
          <div class="rules-list-section">
            <div v-if="profileForm.custom_rules.length === 0" class="no-rules-state">
              <p>暂无自定义协作规则。您可以输入上述规则并添加。</p>
            </div>
            <div class="rules-list" v-else>
              <div 
                v-for="(rule, index) in profileForm.custom_rules" 
                :key="index"
                class="rule-item-row"
              >
                <div class="rule-index">{{ index + 1 }}</div>
                <div class="rule-text-content">
                  <el-input 
                    v-model="profileForm.custom_rules[index]" 
                    size="small" 
                    @change="saveRulesOnly"
                    class="rule-input-field"
                  />
                </div>
                <div class="rule-actions">
                  <el-button 
                    type="danger" 
                    size="small" 
                    plain 
                    circle 
                    @click="deleteRule(index)"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 12px; height: 12px;">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- 创建/编辑事实对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditMode ? '修改长期事实记忆' : '手动注入事实记忆'"
      width="600px"
      custom-class="memory-dialog"
      :before-close="closeDialog"
    >
      <el-form :model="form" label-position="top" ref="formRef" :rules="formRules">
        
        <el-form-item label="绑定当前会话" prop="bindSession" v-if="!isEditMode">
          <el-checkbox v-model="form.bindSession">
            仅在当前聊天会话有效 (Session-level) ；如果不勾选，则为跨会话全局生效。
          </el-checkbox>
        </el-form-item>

        <el-form-item label="事实记忆具体内容 (Content)" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            placeholder="请客观描述技术选型或决策事实（例如：项目目前采用 Vite + Vue 3 进行构建，数据库选用 SQLite）"
          />
        </el-form-item>

        <div class="slider-row">
          <el-form-item label="重要度评级 (Importance)" prop="importance" style="flex: 1;">
            <div class="slider-wrapper">
              <el-slider v-model="form.importance" :min="0" :max="1" :step="0.05" show-input />
            </div>
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" :loading="formLoading" @click="submitForm">确定保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import {
  listMemories,
  createMemory,
  updateMemory,
  deleteMemory,
  searchMemories,
  getProfile,
  updateProfile
} from '@/api/memory'
import { useChatStore } from '@/stores/chat'
import { ElMessageBox, ElMessage } from 'element-plus'

const chatStore = useChatStore()

// 状态定义
const activeMainTab = ref('facts')
const loading = ref(false)
const memoriesList = ref([])
const searchQuery = ref('')

// 画像配置状态
const loadingProfile = ref(false)
const savingProfile = ref(false)
const newRuleText = ref('')
const profileForm = ref({
  preferred_language: 'zh',
  response_style: 'concise',
  custom_rules: []
})

// 对话框表单状态
const dialogVisible = ref(false)
const isEditMode = ref(false)
const formLoading = ref(false)
const currentEditId = ref(null)
const formRef = ref(null)

const form = ref({
  bindSession: false,
  content: '',
  importance: 0.8,
})

const formRules = {
  content: [
    { required: true, message: '请输入记忆具体内容', trigger: 'blur' },
    { min: 5, message: '记忆内容不能少于 5 个字符', trigger: 'blur' }
  ],
}

// 载入数据
const fetchAllMemories = async () => {
  loading.value = true
  try {
    let list
    if (searchQuery.value.trim()) {
      list = await searchMemories({
        query: searchQuery.value.trim(),
        session_id: chatStore.session_id || null,
        limit: 100,
      })
    } else {
      list = await listMemories({
        session_id: chatStore.session_id || undefined,
      })
    }
    memoriesList.value = list || []
  } catch (err) {
    ElMessage.error(`获取事实记忆失败: ${err.message || '未知网络错误'}`)
  } finally {
    loading.value = false
  }
}

// 获取用户画像
const fetchUserProfile = async () => {
  loadingProfile.value = true
  try {
    const data = await getProfile()
    profileForm.value = {
      preferred_language: data.preferred_language || 'zh',
      response_style: data.response_style || 'concise',
      custom_rules: data.custom_rules || []
    }
  } catch (err) {
    ElMessage.error(`获取画像习惯失败: ${err.message}`)
  } finally {
    loadingProfile.value = false
  }
}

onMounted(() => {
  fetchAllMemories()
  fetchUserProfile()
})

const handleMainTabChange = (tabName) => {
  if (tabName === 'facts') {
    fetchAllMemories()
  } else if (tabName === 'profile') {
    fetchUserProfile()
  }
}

// 搜索
const handleSearch = () => {
  fetchAllMemories()
}

const filteredMemories = computed(() => {
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    return memoriesList.value.filter(item => item.content.toLowerCase().includes(q))
  }
  return memoriesList.value
})

// 保存基础习惯设定
const saveBaseProfile = async () => {
  savingProfile.value = true
  try {
    await updateProfile({
      preferred_language: profileForm.value.preferred_language,
      response_style: profileForm.value.response_style,
    })
    ElMessage.success('🚀 画像基础设定保存成功')
  } catch (err) {
    ElMessage.error(`保存失败: ${err.message}`)
  } finally {
    savingProfile.value = false
  }
}

// 新增规则
const addNewRule = async () => {
  const rule = newRuleText.value.trim()
  if (!rule) return
  profileForm.value.custom_rules.push(rule)
  newRuleText.value = ''
  await saveRulesOnly()
}

// 删除规则
const deleteRule = async (index) => {
  profileForm.value.custom_rules.splice(index, 1)
  await saveRulesOnly()
}

// 单独保存规则列表
const saveRulesOnly = async () => {
  try {
    await updateProfile({
      custom_rules: profileForm.value.custom_rules
    })
    ElMessage.success('📋 画像工作流规则已同步更新')
  } catch (err) {
    ElMessage.error(`规则更新失败: ${err.message}`)
  }
}

// 操作方法：物理删除
const confirmDelete = (id) => {
  ElMessageBox.confirm(
    '删除此事实记忆后将无法恢复，确定继续吗？',
    '提示：确定删除该事实记忆？',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'btn-danger-confirm',
    }
  ).then(async () => {
    try {
      await deleteMemory(id)
      ElMessage.success('🗑️ 事实记忆已成功清除')
      fetchAllMemories()
    } catch (err) {
      ElMessage.error(`删除失败: ${err.message}`)
    }
  }).catch(() => {})
}

// 对话框方法
const openCreateDialog = () => {
  isEditMode.value = false
  currentEditId.value = null
  form.value = {
    bindSession: false,
    content: '',
    importance: 0.8,
  }
  dialogVisible.value = true
}

const openEditDialog = (item) => {
  isEditMode.value = true
  currentEditId.value = item.id
  form.value = {
    bindSession: !!item.session_id,
    content: item.content,
    importance: item.importance,
  }
  dialogVisible.value = true
}

const closeDialog = () => {
  dialogVisible.value = false
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

const submitForm = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    formLoading.value = true
    try {
      if (isEditMode.value) {
        await updateMemory(currentEditId.value, {
          content: form.value.content,
          importance: form.value.importance,
        })
        ElMessage.success('📝 事实记忆修改成功')
      } else {
        const sessionVal = form.value.bindSession ? (chatStore.session_id || 'temp_session') : null
        await createMemory({
          content: form.value.content,
          importance: form.value.importance,
          session_id: sessionVal,
        })
        ElMessage.success('✨ 新的长期事实记忆已成功手动注入')
      }
      closeDialog()
      fetchAllMemories()
    } catch (err) {
      ElMessage.error(`操作失败: ${err.message || '未知错误'}`)
    } finally {
      formLoading.value = false
    }
  })
}

const getSourceLabel = (source) => {
  switch (source) {
    case 'manual': return '手动注入'
    case 'qa_interaction': return '问答沉淀'
    default: return source
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return 'n/a'
  try {
    const d = new Date(timeStr)
    return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch (e) {
    return timeStr
  }
}
</script>

<style scoped>
.memory-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 32px;
  overflow-y: auto;
  gap: 24px;
}

.view-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.view-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

.tabs-container {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.tab-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
}

.search-input-wrapper {
  flex: 1;
  max-width: 450px;
}

.search-icon {
  width: 16px;
  height: 16px;
  color: var(--text-muted);
}

.facts-count-info {
  font-size: 13px;
  color: var(--text-secondary);
}

.list-section {
  flex: 1;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  text-align: center;
  gap: 16px;
}

.empty-icon-wrapper {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.empty-icon {
  width: 28px;
  height: 28px;
}

.empty-state h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-state p {
  font-size: 13.5px;
  color: var(--text-secondary);
  max-width: 460px;
  line-height: 1.5;
}

.memory-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

@media (min-width: 1024px) {
  .memory-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.memory-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.memory-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tags-group {
  display: flex;
  gap: 8px;
}

.card-body {
  flex: 1;
}

.memory-content {
  font-size: 14.5px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
}

.card-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 0;
  border-top: 1px dashed rgba(255, 255, 255, 0.04);
  border-bottom: 1px dashed rgba(255, 255, 255, 0.04);
}

.metric-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.metric-label {
  font-size: 12.5px;
  color: var(--text-secondary);
}

.progress-bar-wrapper {
  flex: 1;
  max-width: 70%;
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-track {
  flex: 1;
  height: 4px;
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
}

.progress-fill.importance {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
}

.metric-value {
  font-size: 12px;
  font-family: monospace;
  color: var(--text-primary);
  width: 30px;
  text-align: right;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.hit-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.hit-meta strong {
  color: var(--text-primary);
}

.divider {
  opacity: 0.15;
}

.actions-group {
  display: flex;
  gap: 6px;
}

.btn-icon {
  width: 14px;
  height: 14px;
  margin-right: 4px;
}

.slider-row {
  display: flex;
  gap: 20px;
}

.slider-wrapper {
  padding: 0 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 画像面板布局样式 */
.profile-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.profile-settings-card, .profile-rules-card {
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.form-actions-row {
  display: flex;
  justify-content: flex-end;
  border-top: 1px dashed rgba(255, 255, 255, 0.04);
  padding-top: 16px;
}

.rules-header {
  margin-bottom: 20px;
}

.rules-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.add-rule-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.btn-add-rule {
  flex-shrink: 0;
}

.rules-list-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.no-rules-state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
  font-size: 13.5px;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background-color: rgba(255, 255, 255, 0.01);
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-radius: var(--border-radius-sm);
  transition: all 0.2s ease;
}

.rule-item-row:hover {
  background-color: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.06);
}

.rule-index {
  font-size: 12px;
  font-weight: bold;
  color: var(--color-primary);
  width: 24px;
  text-align: center;
}

.rule-text-content {
  flex: 1;
}

.rule-input-field :deep(.el-input__wrapper) {
  background-color: transparent !important;
  box-shadow: none !important;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1) !important;
  border-radius: 0 !important;
  padding: 0 !important;
}

.rule-input-field :deep(.el-input__inner) {
  color: var(--text-primary) !important;
  font-size: 14px !important;
}

.rule-input-field :deep(.el-input__wrapper.is-focus) {
  border-bottom: 1px solid var(--color-primary) !important;
}

.rule-actions {
  flex-shrink: 0;
}
</style>

<style>
/* Element UI 的一些全局覆盖以保持暗黑精美风格 */
.memory-tabs .el-tabs__item {
  color: var(--text-secondary) !important;
  font-weight: 500;
  font-size: 14px;
}

.memory-tabs .el-tabs__item.is-active {
  color: var(--color-primary) !important;
  font-weight: 600;
}

.memory-tabs .el-tabs__nav-wrap::after {
  background-color: rgba(255, 255, 255, 0.03) !important;
}
</style>
