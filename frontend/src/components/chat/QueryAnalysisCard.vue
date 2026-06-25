<template>
  <div class="query-analysis-card glass-card animate-fade-in">
    <div class="card-header">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="header-icon">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="11" y1="8" x2="11" y2="14"></line>
        <line x1="8" y1="11" x2="14" y2="11"></line>
      </svg>
      <span>查询分析 & 改写 (Query Analysis)</span>
    </div>

    <!-- Empty State -->
    <div v-if="!analysis" class="empty-text">
      暂无此问题的分析数据
    </div>

    <!-- Content -->
    <div v-else class="card-body">
      <!-- Status Badge -->
      <div class="status-row">
        <span class="label">查询意图：</span>
        <span class="status-badge" :class="analysis.is_clear ? 'clear' : 'unclear'">
          <span class="status-dot"></span>
          {{ analysis.is_clear ? '表意清晰' : '意图模糊（触发澄清）' }}
        </span>
      </div>

      <!-- Rewritten Questions -->
      <div v-if="analysis.is_clear && rewrittenQueries.length > 0" class="queries-section">
        <span class="section-label">改写后的独立查询：</span>
        <div class="query-list">
          <div 
            v-for="(q, idx) in rewrittenQueries" 
            :key="idx" 
            class="query-item"
          >
            <span class="query-number">{{ idx + 1 }}</span>
            <span class="query-text">{{ q }}</span>
          </div>
        </div>
      </div>

      <!-- Clarification -->
      <div v-if="!analysis.is_clear && analysis.clarification_needed" class="clarify-box">
        <div class="clarify-header">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="warn-icon">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          澄清提示
        </div>
        <div class="clarify-body">
          {{ analysis.clarification_needed }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  analysis: {
    type: Object,
    default: null,
  },
})

const rewrittenQueries = computed(() => {
  if (!props.analysis || !props.analysis.rewritten_queries) return []
  return props.analysis.rewritten_queries
})
</script>

<style scoped>
.query-analysis-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(75, 85, 99, 0.15);
  padding-bottom: 8px;
}

.header-icon {
  width: 15px;
  height: 15px;
  color: var(--color-primary);
}

.empty-text {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  padding: 12px 0;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-row {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.label {
  color: var(--text-secondary);
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.status-badge.clear {
  background-color: var(--color-success-bg);
  color: var(--color-success-hover);
}

.status-badge.clear .status-dot {
  background-color: var(--color-success);
}

.status-badge.unclear {
  background-color: var(--color-warning-bg);
  color: var(--color-warning-hover);
}

.status-badge.unclear .status-dot {
  background-color: var(--color-warning);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.queries-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.query-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.query-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
}

.query-number {
  font-size: 11px;
  background-color: var(--color-primary-bg);
  color: var(--color-primary-hover);
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.query-text {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.clarify-box {
  border: 1px solid rgba(245, 158, 11, 0.25);
  background-color: rgba(245, 158, 11, 0.03);
  border-radius: var(--border-radius-sm);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.clarify-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-warning-hover);
}

.warn-icon {
  width: 14px;
  height: 14px;
  color: var(--color-warning);
}

.clarify-body {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.45;
}
</style>
