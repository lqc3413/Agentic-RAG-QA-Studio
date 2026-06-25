<template>
  <div class="retrieval-trace-panel glass-card animate-fade-in">
    <div class="panel-header" @click="toggleOpen">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="header-icon">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
      </svg>
      <span>检索诊断 (共 {{ traces.length }} 次)</span>
      <button type="button" class="panel-toggle" @click.stop="toggleOpen">
        {{ isOpen ? '收起' : '展开' }}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="toggle-icon" :class="{ rotated: isOpen }">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    </div>

    <template v-if="isOpen">
      <!-- Empty State -->
      <div v-if="traces.length === 0" class="empty-text">
        本次对话未触发检索调用或尚无诊断数据。
      </div>

      <!-- Traces List -->
      <div v-else class="panel-body">
        <div 
          v-for="(trace, index) in traces" 
          :key="index" 
          class="trace-item"
        >
        <!-- Trace Header Bar -->
        <div class="trace-header">
          <div class="tool-name">
            <span class="dot-indicator"></span>
            调用工具: {{ trace.tool }}
          </div>
          <div class="search-query" :title="trace.query" v-if="trace.query">
            查询词: <code>"{{ trace.query }}"</code>
          </div>
        </div>

        <!-- Metric counters -->
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="val">{{ trace.candidate_top_k || trace.top_k }}</span>
            <span class="lbl">候选 Top-K</span>
          </div>
          <div class="metric-card">
            <span class="val">{{ trace.final_top_k || '-' }}</span>
            <span class="lbl">最终 Top-K</span>
          </div>
          <div class="metric-card">
            <span class="val">{{ trace.threshold }}</span>
            <span class="lbl">评分阈值</span>
          </div>
          <div class="metric-card">
            <span class="val">{{ trace.candidate_count }}</span>
            <span class="lbl">候选总数</span>
          </div>
          <div class="metric-card success">
            <span class="val">{{ trace.selected_count }}</span>
            <span class="lbl">通过筛选</span>
          </div>
          <div class="metric-card warning">
            <span class="val">{{ trace.rejected_count }}</span>
            <span class="lbl">被过滤</span>
          </div>
        </div>

        <div class="pipeline-summary">
          <div class="summary-chip" :class="{ active: trace.rerank_enabled }">
            <span class="chip-label">Rerank</span>
            <span class="chip-value">
              {{ trace.rerank_enabled ? `${trace.rerank_provider || ''}/${trace.rerank_model || 'enabled'}` : 'off' }}
            </span>
          </div>
          <div class="summary-chip" v-if="trace.rerank_enabled" :class="{ active: trace.rerank_applied }">
            <span class="chip-label">重排生效</span>
            <span class="chip-value">{{ trace.rerank_applied ? 'yes' : 'fallback' }}</span>
          </div>
          <div class="summary-chip" v-if="trace.rerank_enabled">
            <span class="chip-label">重排 Top-K</span>
            <span class="chip-value">{{ trace.rerank_top_k }}</span>
          </div>
          <div class="summary-chip" v-if="trace.context_assembly">
            <span class="chip-label">上下文</span>
            <span class="chip-value">
              {{ trace.context_assembly.used_chunks || 0 }}/{{ trace.context_assembly.max_chunks || '-' }} chunks
            </span>
          </div>
          <div class="summary-chip" v-if="trace.context_assembly">
            <span class="chip-label">Token 预算</span>
            <span class="chip-value">
              {{ trace.context_assembly.estimated_tokens || 0 }}/{{ trace.context_assembly.max_tokens || '-' }}
            </span>
          </div>
        </div>

        <div v-if="hasRejectionCounts(trace)" class="rejection-summary">
          <span class="section-title">过滤原因分布：</span>
          <div class="reason-chips">
            <span
              v-for="(count, reason) in trace.context_assembly.rejection_counts"
              :key="reason"
              class="reason-chip"
            >
              {{ getRejectionLabel(reason) }}：{{ count }}
            </span>
          </div>
        </div>

        <!-- Failure reason with Chinese label -->
        <div v-if="trace.failure_reason" class="trace-failure-card">
          <div class="failure-header">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="failure-icon">
              <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span class="failure-title">{{ getFailureLabel(trace.failure_reason).title }}</span>
            <code class="failure-code">{{ trace.failure_reason }}</code>
          </div>
          <p class="failure-description">{{ getFailureLabel(trace.failure_reason).description }}</p>
          <div v-if="trace.parent_ids && trace.parent_ids.length > 0" class="failure-detail-row">
            <span class="detail-label">父节点 ID</span>
            <code class="detail-value">{{ trace.parent_ids.join(', ') }}</code>
          </div>
          <div v-if="trace.error" class="failure-detail-row">
            <span class="detail-label">异常错误</span>
            <code class="detail-value">{{ trace.error }}</code>
          </div>
          <div v-if="trace.rerank_error" class="failure-detail-row">
            <span class="detail-label">重排异常错误</span>
            <code class="detail-value">{{ trace.rerank_error }}</code>
          </div>
        </div>

        <!-- Candidates list -->
        <div v-if="trace.candidates && trace.candidates.length > 0" class="candidates-list">
          <span class="section-title">候选片段明细：</span>
          <div class="cards-stack">
            <CandidateCard 
              v-for="candidate in trace.candidates" 
              :key="candidate.rank" 
              :candidate="candidate" 
            />
          </div>
        </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CandidateCard from './CandidateCard.vue'

defineProps({
  traces: {
    type: Array,
    default: () => [],
  },
})

const FAILURE_REASON_LABELS = {
  NO_CHILD_CHUNK: {
    title: '未检索到候选片段',
    description: '知识库没有返回任何 child chunk 候选，可能是知识库为空、问题偏离文档范围，或检索 query 无法召回内容。',
  },
  LOW_SCORE_FILTERED: {
    title: '候选片段低于阈值',
    description: '系统找到了候选片段，但分数都低于当前相似度阈值，因此没有进入最终回答上下文。',
  },
  NO_PARENT_FOUND: {
    title: 'Parent Chunk 回查失败',
    description: '命中了 child chunk，但根据 parent_id 无法找到对应的 parent chunk，可能是 parent_store 缺失或索引不一致。',
  },
  TOOL_ERROR: {
    title: '检索工具异常',
    description: '检索或 parent 回查工具执行时发生异常，需要检查 Qdrant、parent_store、embedding 或本地文件状态。',
  },
  RERANK_FILTERED: {
    title: 'Rerank 过滤后无可用片段',
    description: '候选片段通过了初步召回，但 rerank 分数没有达到要求，因此没有进入最终回答上下文。',
  },
  DEDUP_FILTERED: {
    title: '去重后无可用片段',
    description: '候选片段存在重复 parent 或重复内容，去重后没有剩余片段可进入上下文。',
  },
  CONTEXT_BUDGET_EXCEEDED: {
    title: '上下文预算不足',
    description: '候选片段存在，但最终上下文条数或 token 预算限制导致没有片段进入回答上下文。',
  },
  NO_CONTEXT_AFTER_ASSEMBLY: {
    title: '上下文组装后为空',
    description: '候选片段经过阈值、rerank、去重和上下文预算处理后，没有形成可用回答上下文。',
  },
}

const REJECTION_REASON_LABELS = {
  BELOW_SCORE_THRESHOLD: '低于分数阈值',
  BELOW_RERANK_THRESHOLD: '低于 rerank 阈值',
  DUPLICATE_PARENT: '重复 parent',
  DUPLICATE_CONTENT: '重复内容',
  CONTEXT_BUDGET_EXCEEDED: '上下文预算',
}

const DEFAULT_FAILURE_LABEL = {
  title: '检索异常',
  description: '',
}

const getFailureLabel = (code) => {
  if (FAILURE_REASON_LABELS[code]) {
    return FAILURE_REASON_LABELS[code]
  }
  return { ...DEFAULT_FAILURE_LABEL, description: code }
}

const getRejectionLabel = (reason) => REJECTION_REASON_LABELS[reason] || reason

const hasRejectionCounts = (trace) => {
  return Boolean(
    trace?.context_assembly?.rejection_counts &&
      Object.keys(trace.context_assembly.rejection_counts).length > 0
  )
}

const isOpen = ref(false)

const toggleOpen = () => {
  isOpen.value = !isOpen.value
}
</script>

<style scoped>
.retrieval-trace-panel {
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
  gap: 20px;
}

.trace-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background-color: rgba(255, 255, 255, 0.01);
  border: 1px solid rgba(75, 85, 99, 0.1);
  border-radius: var(--border-radius-md);
  padding: 14px;
}

.trace-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-bottom: 1px dashed rgba(75, 85, 99, 0.15);
  padding-bottom: 10px;
}

.tool-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot-indicator {
  width: 6px;
  height: 6px;
  background-color: var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 6px var(--color-primary);
}

.search-query {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-query code {
  color: var(--color-primary-hover);
  background: rgba(59, 130, 246, 0.05);
  padding: 1px 4px;
  border-radius: 4px;
}

/* 指标网格样式 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 8px;
}

.metric-card {
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
}

.metric-card .val {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-card .lbl {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
  text-align: center;
}

.metric-card.success {
  border-color: rgba(16, 185, 129, 0.2);
  background-color: rgba(16, 185, 129, 0.02);
}

.metric-card.success .val {
  color: var(--color-success);
}

.metric-card.warning {
  border-color: rgba(245, 158, 11, 0.2);
  background-color: rgba(245, 158, 11, 0.02);
}

.metric-card.warning .val {
  color: var(--color-warning-hover);
}

.pipeline-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background: rgba(255, 255, 255, 0.02);
  padding: 6px 8px;
  min-height: 30px;
}

.summary-chip.active {
  border-color: rgba(59, 130, 246, 0.28);
  background: var(--color-primary-bg);
}

.chip-label {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 600;
}

.chip-value {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 600;
}

.rejection-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reason-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.reason-chip {
  font-size: 11px;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background-color: rgba(255, 255, 255, 0.02);
  padding: 4px 7px;
}

.trace-failure-card {
  background-color: var(--color-danger-bg);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: var(--border-radius-sm);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.failure-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.failure-icon {
  width: 16px;
  height: 16px;
  color: var(--color-danger);
  flex-shrink: 0;
}

.failure-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-danger-hover);
}

.failure-code {
  font-size: 10px;
  font-weight: 600;
  background-color: rgba(239, 68, 68, 0.08);
  color: var(--color-danger);
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid rgba(239, 68, 68, 0.2);
  font-family: Consolas, Monaco, monospace;
  margin-left: auto;
  flex-shrink: 0;
}

.failure-description {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  margin: 0;
}

.failure-detail-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
}

.detail-value {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-secondary);
  background-color: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--border-radius-sm);
  padding: 6px 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 候选片段列表样式 */
.candidates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.cards-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
