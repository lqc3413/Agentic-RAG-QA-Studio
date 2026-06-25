<template>
  <div class="document-uploader glass-card animate-fade-in">
    <div class="uploader-heading">
      <div>
        <h3 class="panel-title">添加新文档</h3>
        <p class="panel-desc">支持 PDF / Markdown。普通用户上传到我的文档，单文件最大 5 MB。</p>
      </div>
      <div class="uploader-controls" style="display: flex; gap: 12px; align-items: center;">
        <el-select
          v-model="category"
          placeholder="选择分类"
          :disabled="store.uploading"
          style="width: 140px;"
          size="small"
        >
          <el-option
            v-for="item in categoryOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-segmented
          v-if="authStore.isAdmin"
          v-model="visibility"
          :options="visibilityOptions"
          :disabled="store.uploading"
          class="visibility-control"
        />
      </div>
    </div>

    <div class="upload-wrapper">
      <el-upload
        class="upload-drag-area"
        drag
        action=""
        :auto-upload="false"
        multiple
        :show-file-list="true"
        accept=".pdf,.md"
        v-model:file-list="fileList"
        :disabled="store.uploading"
      >
        <div class="upload-icon-container">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="upload-icon-svg">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
        </div>
        <div class="el-upload__text">
          将文档拖到此处，或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="upload-tip">
            仅支持 .pdf / .md，上传目标：{{ visibilityLabel }}
          </div>
        </template>
      </el-upload>
    </div>

    <div class="quota-note">
      私有文档配额：最多 10 个，总大小 30 MB。公共文档仅管理员可上传。
    </div>

    <div class="upload-actions" v-if="fileList.length > 0">
      <el-button
        type="primary"
        :loading="store.uploading"
        @click="handleUpload"
        class="btn-primary"
      >
        导入 {{ fileList.length }} 个文档
      </el-button>
      <el-button
        @click="clearFileList"
        :disabled="store.uploading"
        class="btn-secondary"
      >
        取消
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDocumentStore } from '@/stores/documents'
import { useAuthStore } from '@/stores/auth'

const MAX_UPLOAD_FILE_SIZE = 5 * 1024 * 1024

const store = useDocumentStore()
const authStore = useAuthStore()
const fileList = ref([])
const visibility = ref('private')
const category = ref('general')

const visibilityOptions = [
  { label: '我的文档', value: 'private' },
  { label: '公共文档', value: 'public' },
]

const categoryOptions = [
  { label: '通用/默认', value: 'general' },
  { label: '人力资源 (hr)', value: 'hr' },
  { label: '技术研发 (tech)', value: 'tech' },
  { label: '财务合同 (finance)', value: 'finance' },
]

const visibilityLabel = computed(() => (
  visibility.value === 'public' ? '公共文档' : '我的文档'
))

const clearFileList = () => {
  fileList.value = []
}

const handleUpload = async () => {
  if (fileList.value.length === 0) return

  const rawFiles = fileList.value.map((file) => file.raw).filter(Boolean)
  const oversized = rawFiles.find((file) => file.size > MAX_UPLOAD_FILE_SIZE)
  if (oversized) {
    ElMessage({
      type: 'warning',
      message: `${oversized.name} 超过 5 MB，请压缩或拆分后再上传`,
      duration: 5000,
      showClose: true,
    })
    return
  }

  try {
    const result = await store.uploadFiles(rawFiles, visibility.value, category.value)
    if (result) {
      ElMessage({
        type: 'success',
        message: `导入完成：新增 ${result.added} 个，跳过 ${result.skipped} 个`,
        duration: 5000,
        showClose: true,
      })
      clearFileList()
    }
  } catch (err) {
    ElMessage({
      type: 'error',
      message: `导入失败：${store.error || '未知错误'}`,
      duration: 6000,
      showClose: true,
    })
  }
}
</script>

<style scoped>
.document-uploader {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: fit-content;
}

.uploader-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-desc {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.visibility-control {
  flex-shrink: 0;
}

.upload-wrapper {
  margin-top: 8px;
}

:deep(.el-upload-dragger) {
  background-color: rgba(9, 11, 30, 0.02);
  border: 1px dashed var(--border-color);
  border-radius: var(--border-radius-md);
  transition: all var(--transition-normal);
}

:deep(.el-upload-dragger:hover) {
  border-color: var(--color-primary);
  background-color: rgba(59, 130, 246, 0.03);
}

.upload-icon-container {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.upload-icon-svg {
  width: 44px;
  height: 44px;
  color: var(--text-muted);
  transition: color var(--transition-fast), transform var(--transition-fast);
}

:deep(.el-upload-dragger:hover) .upload-icon-svg {
  color: var(--color-primary);
  transform: translateY(-2px);
}

.el-upload__text {
  color: var(--text-secondary);
  font-size: 14px;
}

.el-upload__text em {
  color: var(--color-primary);
  font-style: normal;
  font-weight: 500;
}

.upload-tip,
.quota-note {
  font-size: 12px;
  color: var(--text-muted);
}

.upload-tip {
  margin-top: 10px;
  text-align: center;
}

.quota-note {
  line-height: 1.5;
}

:deep(.el-upload-list__item) {
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

:deep(.el-upload-list__item:hover) {
  background-color: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

:deep(.el-upload-list__item .el-icon--close) {
  color: var(--text-muted);
}

:deep(.el-upload-list__item .el-icon--close:hover) {
  color: var(--color-danger);
}

.upload-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  justify-content: flex-end;
}

.btn-primary {
  background-color: var(--color-primary) !important;
  border-color: var(--color-primary) !important;
  color: #fff !important;
}

.btn-primary:hover {
  background-color: var(--color-primary-hover) !important;
  border-color: var(--color-primary-hover) !important;
}

.btn-secondary {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-color: var(--border-color) !important;
  color: var(--text-secondary) !important;
}

.btn-secondary:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.08) !important;
  color: var(--text-primary) !important;
}

@media (max-width: 720px) {
  .uploader-heading {
    flex-direction: column;
  }
}
</style>
