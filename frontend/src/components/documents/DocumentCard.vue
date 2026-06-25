<template>
  <div class="doc-item">
    <div class="doc-heading">
      <div class="doc-icon-box" :class="fileType">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="file-svg"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <path v-if="fileType === 'pdf'" d="M9 15h3a2 2 0 0 0 0-4H9v6"></path>
          <line v-else x1="8" y1="13" x2="16" y2="13"></line>
        </svg>
      </div>

      <div class="doc-title-block">
        <span class="doc-name" :title="displayName">{{ displayName }}</span>
        <div class="doc-meta-row">
          <span class="doc-badge" :class="fileType">{{ fileType.toUpperCase() }}</span>
          <span class="visibility-badge" :class="doc.visibility || 'private'">{{ visibilityLabel }}</span>
          <span v-if="doc.category && doc.category !== 'general'" class="visibility-badge private" style="background-color: rgba(139, 92, 246, 0.12); color: #c084fc;">
            {{ doc.category.toUpperCase() }}
          </span>
          <span class="doc-status-badge" :class="statusClass">
            <span class="status-dot"></span>
            {{ statusLabel }}
          </span>
        </div>
      </div>

      <el-button
        v-if="canDelete"
        type="danger"
        link
        size="small"
        class="doc-delete-btn"
        @click="$emit('delete', doc)"
      >
        删除
      </el-button>
    </div>

    <div class="detail-list">
      <div class="detail-row">
        <span class="detail-label">大小</span>
        <span class="detail-value">{{ sizeLabel }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">更新</span>
        <span class="detail-value">{{ formatTime }}</span>
      </div>
    </div>

    <div v-if="doc.error_message" class="error-message" :title="doc.error_message">
      {{ doc.error_message }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElButton } from 'element-plus'

const props = defineProps({
  doc: {
    type: Object,
    required: true,
  },
  canDelete: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['delete'])

const statusLabels = {
  indexed: '已入库',
  skipped: '已跳过',
  failed: '失败',
  legacy: '历史文档',
}

const fileType = computed(() => (props.doc?.type || 'md').toLowerCase())
const statusLabel = computed(() => statusLabels[props.doc?.status] || '未知')
const statusClass = computed(() => props.doc?.status || 'unknown')
const displayName = computed(() => props.doc?.original_name || props.doc?.name)
const visibilityLabel = computed(() => props.doc?.visibility === 'public' ? '公共' : '私有')

const sizeLabel = computed(() => {
  const bytes = props.doc?.original_size_bytes
  const value = Number(bytes || 0)
  if (value <= 0) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
})

const formatTime = computed(() => {
  const value = props.doc?.updated_at || props.doc?.created_at
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
})
</script>

<style scoped>
.doc-item {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  padding: 16px;
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  transition: all var(--transition-normal);
}

.doc-item:hover {
  background-color: rgba(255, 255, 255, 0.04);
  border-color: var(--color-primary-bg);
  transform: translateY(-1px);
}

.doc-heading {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.doc-icon-box {
  width: 42px;
  height: 42px;
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.doc-icon-box.pdf {
  background-color: rgba(239, 68, 68, 0.08);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.doc-icon-box.md {
  background-color: rgba(59, 130, 246, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(59, 130, 246, 0.15);
}

.file-svg {
  width: 20px;
  height: 20px;
}

.doc-title-block {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  flex: 1;
}

.doc-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.doc-badge,
.doc-status-badge,
.visibility-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}

.doc-badge,
.visibility-badge {
  padding: 0 6px;
}

.doc-badge.pdf {
  background-color: var(--color-danger-bg);
  color: var(--color-danger-hover);
}

.doc-badge.md {
  background-color: var(--color-primary-bg);
  color: var(--color-primary-hover);
}

.visibility-badge.private {
  background-color: rgba(20, 184, 166, 0.12);
  color: #5eead4;
}

.visibility-badge.public {
  background-color: rgba(234, 179, 8, 0.12);
  color: #fde047;
}

.doc-status-badge {
  gap: 5px;
  padding: 0 7px;
}

.doc-status-badge.indexed {
  background-color: var(--color-success-bg);
  color: var(--color-success-hover);
}

.doc-status-badge.failed {
  background-color: var(--color-danger-bg);
  color: var(--color-danger-hover);
}

.doc-status-badge.skipped {
  background-color: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.doc-status-badge.legacy,
.doc-status-badge.unknown {
  background-color: var(--color-warning-bg);
  color: var(--color-warning-hover);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
}

.doc-delete-btn {
  flex-shrink: 0;
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.detail-label {
  font-size: 11px;
  color: var(--text-muted);
}

.detail-value {
  min-width: 0;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.error-message {
  padding: 8px 10px;
  border-radius: var(--border-radius-sm);
  background-color: rgba(239, 68, 68, 0.08);
  color: var(--color-danger-hover);
  font-size: 12px;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 720px) {
  .detail-row {
    grid-template-columns: 64px minmax(0, 1fr);
  }
}
</style>
