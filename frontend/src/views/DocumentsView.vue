<template>
  <div class="documents-view">
    <div class="view-header">
      <h2>文档知识库管理</h2>
      <p class="view-subtitle">管理我的文档与公共文档。检索时会自动使用我的文档和公共文档。</p>
    </div>

    <div class="view-body">
      <DocumentUploader />
      <DocumentList />

      <div class="danger-zone glass-card animate-fade-in">
        <div class="danger-info">
          <span class="danger-title">{{ dangerTitle }}</span>
          <span class="danger-desc">{{ dangerDesc }}</span>
        </div>
        <div class="danger-actions">
          <el-button
            type="danger"
            :loading="store.loading"
            @click="confirmClearMine"
            class="btn-danger"
          >
            清空我的文档
          </el-button>
          <el-button
            v-if="authStore.isAdmin"
            type="danger"
            plain
            :loading="store.loading"
            @click="confirmClearAll"
            class="btn-danger-plain"
          >
            清空全部知识库
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DocumentUploader from '@/components/documents/DocumentUploader.vue'
import DocumentList from '@/components/documents/DocumentList.vue'
import { useAuthStore } from '@/stores/auth'
import { useDocumentStore } from '@/stores/documents'

const store = useDocumentStore()
const authStore = useAuthStore()

const dangerTitle = computed(() => (
  authStore.isAdmin ? '清空知识库' : '清空我的文档'
))

const dangerDesc = computed(() => (
  authStore.isAdmin
    ? '可以清空个人私有文档；管理员也可以清空全部知识库。'
    : '只会删除我的私有文档，不影响公共文档和其他用户文档。'
))

const confirmClearMine = () => {
  ElMessageBox.confirm(
    '确定清空我的私有文档吗？该操作会删除对应 Markdown、Parent Chunk 和向量数据。',
    '清空我的文档',
    {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'btn-danger-confirm',
    }
  ).then(async () => {
    try {
      await store.clearDocuments('mine')
      ElMessage({
        type: 'success',
        message: '我的文档已清空',
        duration: 3000,
      })
    } catch (err) {
      ElMessage({
        type: 'error',
        message: `清空失败：${store.error || '未知错误'}`,
      })
    }
  }).catch(() => {})
}

const confirmClearAll = () => {
  ElMessageBox.confirm(
    '确定清空全部知识库吗？这会删除所有用户文档、公共文档和向量集合。',
    '清空全部知识库',
    {
      confirmButtonText: '清空全部',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'btn-danger-confirm',
    }
  ).then(async () => {
    try {
      await store.clearDocuments('all')
      ElMessage({
        type: 'success',
        message: '全部知识库已清空',
        duration: 3000,
      })
    } catch (err) {
      ElMessage({
        type: 'error',
        message: `清空失败：${store.error || '未知错误'}`,
      })
    }
  }).catch(() => {})
}
</script>

<style scoped>
.documents-view {
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

.view-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.view-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

.view-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}

.danger-zone {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  border: 1px solid rgba(239, 68, 68, 0.2) !important;
  background-color: rgba(239, 68, 68, 0.02) !important;
  border-radius: var(--border-radius-md);
  margin-top: 12px;
}

.danger-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.danger-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-danger-hover);
}

.danger-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.danger-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.btn-danger {
  background-color: var(--color-danger) !important;
  border-color: var(--color-danger) !important;
  color: #fff !important;
}

.btn-danger:hover {
  background-color: var(--color-danger-hover) !important;
  border-color: var(--color-danger-hover) !important;
}

.btn-danger-plain {
  background-color: transparent !important;
  border-color: rgba(239, 68, 68, 0.45) !important;
  color: var(--color-danger-hover) !important;
}

@media (max-width: 720px) {
  .documents-view {
    padding: 20px;
  }

  .danger-zone {
    align-items: stretch;
    flex-direction: column;
  }

  .danger-actions {
    flex-direction: column;
  }
}
</style>

<style>
.btn-danger-confirm {
  background-color: var(--color-danger) !important;
  border-color: var(--color-danger) !important;
  color: #fff !important;
}

.btn-danger-confirm:hover {
  background-color: var(--color-danger-hover) !important;
  border-color: var(--color-danger-hover) !important;
}
</style>
