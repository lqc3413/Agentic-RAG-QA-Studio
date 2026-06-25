<template>
  <div class="source-panel glass-card animate-fade-in">
    <div class="panel-header" @click="toggleOpen">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="header-icon">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
      </svg>
      <span>参考依据 ({{ sources.length }} 条)</span>
      <button type="button" class="panel-toggle" @click.stop="toggleOpen">
        {{ isOpen ? '收起' : '展开' }}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="toggle-icon" :class="{ rotated: isOpen }">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    </div>

    <template v-if="isOpen">
      <!-- Empty State -->
      <div v-if="sources.length === 0" class="empty-text">
        本次回答暂无对应的参考依据。
      </div>

      <!-- Sources list -->
      <div v-else class="panel-body">
        <div 
          v-for="source in sources" 
          :key="source.source_id" 
          class="source-item"
          :class="{ 'is-expanded': expandedIds.includes(source.source_id) }"
        >
        <!-- Source Header -->
        <div class="source-header" @click="toggleExpand(source.source_id)">
          <div class="left-section">
            <span class="source-id">{{ source.source_id }}</span>
            <span class="file-name" :title="source.source">{{ source.source }}</span>
          </div>
          <div class="right-section">
            <div class="score-badge">
              检索评分: <strong>{{ formatScore(source.score) }}</strong>
            </div>
            <div class="score-badge" v-if="source.rerank_score !== null && source.rerank_score !== undefined">
              重排评分: <strong>{{ formatScore(source.rerank_score) }}</strong>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="chevron" :class="{ rotated: expandedIds.includes(source.source_id) }">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
        </div>

        <!-- Source Body (Expandable) -->
        <div class="source-body">
          <div class="metadata-row">
            <span class="meta-label">段落关联：</span>
            <span class="meta-val monospace">{{ source.parent_id || 'N/A' }}</span>
          </div>
          <div class="content-box">
            {{ source.content_preview }}
          </div>
        </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  sources: {
    type: Array,
    default: () => [],
  },
})

const expandedIds = ref([])
const isOpen = ref(false)

const toggleOpen = () => {
  isOpen.value = !isOpen.value
}

const toggleExpand = (id) => {
  const idx = expandedIds.value.indexOf(id)
  if (idx > -1) {
    expandedIds.value.splice(idx, 1)
  } else {
    expandedIds.value.push(id)
  }
}

const formatScore = (val) => {
  if (typeof val !== 'number') return '0.000'
  return val.toFixed(3)
}
</script>

<style scoped>
.source-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(75, 85, 99, 0.15);
  padding-bottom: 8px;
  cursor: pointer;
  user-select: none;
}

.header-icon {
  width: 15px;
  height: 15px;
  color: var(--color-primary);
  flex-shrink: 0;
}

.panel-header span {
  flex: 1;
}

.panel-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 7px;
}

.panel-toggle:hover {
  color: var(--color-primary-hover);
  border-color: var(--border-color-hover);
}

.toggle-icon {
  width: 12px;
  height: 12px;
  transition: transform var(--transition-fast);
}

.toggle-icon.rotated {
  transform: rotate(180deg);
}

.empty-text {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  padding: 16px 0;
}

.panel-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-item {
  background-color: rgba(255, 255, 255, 0.01);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.source-item:hover {
  background-color: rgba(255, 255, 255, 0.03);
  border-color: var(--border-color-hover);
}

.source-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.left-section {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.source-id {
  font-size: 10px;
  font-weight: 700;
  background-color: var(--color-success-bg);
  color: var(--color-success-hover);
  border: 1px solid rgba(16, 185, 129, 0.2);
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.right-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-badge {
  font-size: 11px;
  color: var(--text-secondary);
}

.score-badge strong {
  color: var(--color-success-hover);
}

.chevron {
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.chevron.rotated {
  transform: rotate(180deg);
}

/* 数据源可展开主体的样式 */
.source-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--transition-normal) ease;
  padding: 0 14px;
}

.source-item.is-expanded .source-body {
  max-height: 500px; /* 任意较大的高度以便向下展开滑动动画 */
  padding-bottom: 14px;
  border-top: 1px dashed rgba(75, 85, 99, 0.15);
  padding-top: 12px;
}

.metadata-row {
  display: flex;
  align-items: center;
  font-size: 11px;
  margin-bottom: 8px;
}

.meta-label {
  color: var(--text-muted);
}

.meta-val {
  color: var(--text-secondary);
}

.meta-val.monospace {
  font-family: Consolas, Monaco, monospace;
}

.content-box {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
  background-color: rgba(0, 0, 0, 0.15);
  border-radius: var(--border-radius-sm);
  padding: 10px;
  border: 1px solid rgba(75, 85, 99, 0.1);
  word-break: break-all;
}
</style>
