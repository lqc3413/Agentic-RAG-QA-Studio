<template>
  <div class="candidate-card" :class="[candidate.status, { 'is-expanded': isExpanded }]">
    <!-- Header Row (Always Visible) -->
    <div class="card-header-bar" @click="toggleExpand">
      <div class="left-badges">
        <span class="rank-badge">#{{ candidate.rank }}</span>
        <span class="status-badge" :class="candidate.status">
          {{ statusLabel }}
        </span>
        <span class="citation-badge" v-if="candidate.citation_id">{{ candidate.citation_id }}</span>
      </div>
      
      <div class="score-box" :class="candidate.status">
        <span class="score-value">{{ formatScore(candidate.score) }}</span>
        <span class="threshold-limit">/ &ge;{{ candidate.threshold }}</span>
      </div>
    </div>

    <!-- Body Row (Expandable) -->
    <div class="card-body-panel">
      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">来源：</span>
          <span class="meta-value" :title="candidate.source">{{ candidate.source }}</span>
        </div>
        <div class="meta-item" v-if="candidate.parent_id">
          <span class="meta-label">段落 ID：</span>
          <span class="meta-value monospace">{{ candidate.parent_id }}</span>
        </div>
        <div class="meta-item" v-if="candidate.rerank_score !== null && candidate.rerank_score !== undefined">
          <span class="meta-label">重排评分：</span>
          <span class="meta-value monospace">{{ formatScore(candidate.rerank_score) }}</span>
        </div>
        <div class="meta-item" v-if="candidate.rank_before_rerank && candidate.rank_after_rerank">
          <span class="meta-label">排序：</span>
          <span class="meta-value monospace">#{{ candidate.rank_before_rerank }} → #{{ candidate.rank_after_rerank }}</span>
        </div>
        <div class="meta-item" v-if="candidate.rejection_reason">
          <span class="meta-label">过滤原因：</span>
          <span class="meta-value">{{ rejectionLabel }}</span>
        </div>
        <div class="meta-item" v-if="candidate.estimated_tokens">
          <span class="meta-label">估算 tokens：</span>
          <span class="meta-value monospace">{{ candidate.estimated_tokens }}</span>
        </div>
      </div>
      
      <div class="text-preview" :class="{ 'is-collapsed': !isExpanded }">
        {{ candidate.content_preview }}
      </div>
      
      <div class="toggle-expand-btn" @click="toggleExpand">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="chevron-icon" :class="{ rotated: isExpanded }">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
        {{ isExpanded ? '收起全文' : '展开全文' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  candidate: {
    type: Object,
    required: true,
  },
})

const isExpanded = ref(false)

const STATUS_LABELS = {
  selected: '入选',
  rejected_low_score: '分数低',
  rejected_low_rerank: '重排分数低',
  rejected_duplicate_parent: '重复父节点',
  rejected_duplicate_content: '重复内容',
  rejected_context_budget: '超出预算',
  rejected: '已过滤',
}

const REJECTION_LABELS = {
  BELOW_SCORE_THRESHOLD: '低于相似度阈值',
  BELOW_RERANK_THRESHOLD: '低于 rerank 阈值',
  DUPLICATE_PARENT: '同一 parent 已入选',
  DUPLICATE_CONTENT: '内容重复',
  CONTEXT_BUDGET_EXCEEDED: '超过最终上下文预算',
}

const statusLabel = computed(() => STATUS_LABELS[props.candidate.status] || 'REJECTED')
const rejectionLabel = computed(() => {
  return REJECTION_LABELS[props.candidate.rejection_reason] || props.candidate.rejection_reason
})

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const formatScore = (val) => {
  if (typeof val !== 'number') return '0.000'
  return val.toFixed(3)
}
</script>

<style scoped>
.candidate-card {
  border: 1px solid var(--border-color);
  background-color: rgba(255, 255, 255, 0.01);
  border-radius: var(--border-radius-md);
  overflow: hidden;
  transition: all var(--transition-normal);
  border-left-width: 4px;
}

.candidate-card.selected {
  border-left-color: var(--color-success);
}

.candidate-card.rejected_low_score {
  border-left-color: var(--text-muted);
}

.candidate-card.rejected_low_rerank {
  border-left-color: var(--color-warning);
}

.candidate-card.rejected_duplicate_parent,
.candidate-card.rejected_duplicate_content {
  border-left-color: var(--color-primary);
}

.candidate-card.rejected_context_budget {
  border-left-color: var(--color-warning-hover);
}

.candidate-card:hover {
  background-color: rgba(255, 255, 255, 0.03);
  border-color: var(--border-color-hover);
}

.candidate-card.selected:hover {
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.05);
}

.card-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  background-color: rgba(255, 255, 255, 0.01);
  user-select: none;
}

.left-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rank-badge {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background-color: rgba(255, 255, 255, 0.03);
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.status-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.status-badge.selected {
  background-color: var(--color-success-bg);
  color: var(--color-success-hover);
}

.status-badge.rejected_low_score {
  background-color: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
}

.status-badge.rejected_low_rerank,
.status-badge.rejected_context_budget {
  background-color: var(--color-warning-bg);
  color: var(--color-warning-hover);
}

.status-badge.rejected_duplicate_parent,
.status-badge.rejected_duplicate_content {
  background-color: var(--color-primary-bg);
  color: var(--color-primary-hover);
}

.citation-badge {
  font-size: 10px;
  font-weight: 600;
  background-color: var(--color-primary-bg);
  color: var(--color-primary-hover);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.score-box {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-family: var(--font-family);
}

.score-value {
  font-size: 14px;
  font-weight: 700;
}

.score-box.selected .score-value {
  color: var(--color-success-hover);
}

.score-box.rejected_low_score .score-value {
  color: var(--text-secondary);
}

.score-box.rejected_low_rerank .score-value,
.score-box.rejected_context_budget .score-value {
  color: var(--color-warning-hover);
}

.score-box.rejected_duplicate_parent .score-value,
.score-box.rejected_duplicate_content .score-value {
  color: var(--color-primary-hover);
}

.threshold-limit {
  font-size: 11px;
  color: var(--text-muted);
}

/* 内容面板 */
.card-body-panel {
  padding: 0 14px 12px 14px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 6px;
  border-top: 1px dashed rgba(75, 85, 99, 0.15);
  padding-top: 10px;
  margin-bottom: 10px;
}

.meta-item {
  display: flex;
  align-items: center;
  font-size: 11.5px;
  min-width: 0;
}

.meta-label {
  color: var(--text-muted);
  flex-shrink: 0;
}

.meta-value {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-value.monospace {
  font-family: Consolas, Monaco, monospace;
}

.text-preview {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
  background-color: rgba(0, 0, 0, 0.15);
  border-radius: var(--border-radius-sm);
  padding: 10px;
  border: 1px solid rgba(75, 85, 99, 0.1);
  word-break: break-all;
}

.text-preview.is-collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toggle-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  margin-top: 8px;
  padding: 4px 0;
  transition: color var(--transition-fast);
  user-select: none;
}

.toggle-expand-btn:hover {
  color: var(--color-primary-hover);
}

.chevron-icon {
  width: 12px;
  height: 12px;
  transition: transform var(--transition-fast);
}

.chevron-icon.rotated {
  transform: rotate(180deg);
}
</style>
