<template>
  <div class="document-list glass-card animate-fade-in" v-loading="store.loading">
    <div class="list-header">
      <div>
        <h3 class="panel-title">知识库文档</h3>
        <p class="panel-subtitle">
          {{ store.privateDocuments.length }} 个我的文档，{{ store.publicDocuments.length }} 个公共文档
        </p>
      </div>
      <el-button
        link
        @click="store.fetchDocuments()"
        :disabled="store.loading"
        class="refresh-btn"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="refresh-icon" :class="{ spinning: store.loading }">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        刷新
      </el-button>
    </div>

    <div v-if="store.documents.length === 0" class="empty-state">
      <div class="empty-icon-wrapper">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="empty-svg">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
      </div>
      <span class="empty-title">知识库为空</span>
      <span class="empty-desc">上传 PDF 或 Markdown 后，文档会出现在我的文档或公共文档中。</span>
    </div>

    <div v-else class="section-list">
      <section class="document-section">
        <div class="section-heading">
          <h4>我的文档</h4>
          <span>{{ store.privateDocuments.length }} 个</span>
        </div>
        <div v-if="store.privateDocuments.length === 0" class="section-empty">还没有个人上传的文档</div>
        <div v-else class="grid-container">
          <DocumentCard
            v-for="doc in store.privateDocuments"
            :key="doc.document_id || doc.name"
            :doc="doc"
            :can-delete="true"
            @delete="confirmDelete"
          />
        </div>
      </section>

      <section class="document-section">
        <div class="section-heading">
          <h4>公共文档</h4>
          <span>{{ store.publicDocuments.length }} 个</span>
        </div>
        <div v-if="store.publicDocuments.length === 0" class="section-empty">暂无公共文档</div>
        <div v-else class="grid-container">
          <DocumentCard
            v-for="doc in store.publicDocuments"
            :key="doc.document_id || doc.name"
            :doc="doc"
            :can-delete="authStore.isAdmin"
            @delete="confirmDelete"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDocumentStore } from '@/stores/documents'
import { useAuthStore } from '@/stores/auth'
import DocumentCard from './DocumentCard.vue'

const store = useDocumentStore()
const authStore = useAuthStore()

const displayName = (doc) => doc.original_name || doc.name

const confirmDelete = (doc) => {
  ElMessageBox.confirm(
    `确定删除“${displayName(doc)}”吗？该操作会同时清理 Markdown、Parent Chunk 和向量数据。`,
    '删除文档',
    {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'btn-danger-confirm',
    }
  ).then(async () => {
    try {
      await store.deleteDocument(doc.document_id || doc.name)
      ElMessage({
        type: 'success',
        message: '文档已删除',
        duration: 3000,
      })
    } catch (err) {
      ElMessage({
        type: 'error',
        message: `删除失败：${store.error || '未知错误'}`,
      })
    }
  }).catch(() => {})
}

onMounted(() => {
  store.fetchDocuments()
})
</script>

<style scoped>
.document-list {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(75, 85, 99, 0.15);
  padding-bottom: 12px;
  gap: 16px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.refresh-btn {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.refresh-btn:hover {
  color: var(--color-primary) !important;
}

.refresh-icon {
  width: 14px;
  height: 14px;
}

.refresh-icon.spinning {
  animation: spin 1s infinite linear;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state,
.section-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-state {
  padding: 48px 24px;
  flex: 1;
}

.section-empty {
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
  border: 1px dashed rgba(148, 163, 184, 0.18);
  border-radius: var(--border-radius-md);
}

.empty-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-svg {
  width: 26px;
  height: 26px;
  color: var(--text-muted);
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 340px;
  line-height: 1.5;
}

.section-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  padding-right: 4px;
  flex: 1;
}

.document-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-heading h4 {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.section-heading span {
  font-size: 12px;
  color: var(--text-muted);
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

@media (max-width: 720px) {
  .document-list {
    padding: 18px;
  }

  .grid-container {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
