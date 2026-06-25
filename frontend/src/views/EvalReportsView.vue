<template>
  <div class="eval-reports-view">
    <!-- 顶部标题栏 -->
    <div class="view-header animate-fade-in">
      <div class="header-info">
        <h2>系统评估报告</h2>
        <p class="view-subtitle">查看 RAG 系统批量评估历史、指标达成情况、失败原因分布及用例明细。</p>
      </div>
      <el-button 
        type="primary" 
        :loading="store.loading" 
        @click="refreshReports" 
        class="refresh-btn"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        刷新列表
      </el-button>
    </div>

    <div class="view-body animate-fade-in">
      <!-- 左侧：报告列表 -->
      <div class="reports-sidebar glass-card">
        <div class="sidebar-header">
          <h3>报告历史 ({{ store.reports.length }})</h3>
        </div>
        <div class="sidebar-list" v-loading="store.loading">
          <div v-if="store.reports.length === 0" class="empty-sidebar">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="empty-icon">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="9" x2="15" y2="9"></line>
              <line x1="9" y1="13" x2="15" y2="13"></line>
              <line x1="9" y1="17" x2="11" y2="17"></line>
            </svg>
            <span>暂无评估历史</span>
          </div>
          
          <div 
            v-for="item in store.reports" 
            :key="item.name"
            class="report-item"
            :class="{ active: store.activeReportName === item.name }"
            @click="selectReport(item.name)"
          >
            <div class="item-meta">
              <span class="badge" :class="item.mode">{{ item.mode.toUpperCase() }}</span>
              <span v-if="item.dry_run" class="badge dry-run">DRY RUN</span>
            </div>
            <div class="item-title" :title="item.name">{{ formatFileName(item.name) }}</div>
            <div class="item-time">{{ formatTime(item.created_at) }}</div>
            <div class="item-stats">
              <span>用例数: {{ item.case_count }}</span>
              <span v-if="item.pass_rate !== null" class="pass-rate-stat">
                通过率: <span :class="getPassRateClass(item.pass_rate)">{{ (item.pass_rate * 100).toFixed(0) }}%</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：报告详情 -->
      <div class="report-details" v-loading="store.detailLoading">
        <!-- 空状态或错误 -->
        <div v-if="store.error" class="error-container glass-card">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="error-icon">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <p>{{ store.error }}</p>
          <el-button type="primary" size="small" @click="refreshReports">重试</el-button>
        </div>

        <div v-else-if="!store.activeReport" class="empty-details glass-card">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="empty-icon-large">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <h3>暂无已选评估报告</h3>
          <p class="empty-desc">请确保在后端服务器对应的终端内运行了评估脚本生成报告。</p>
          <div class="command-box">
            <code>.\.venv\Scripts\python.exe -X utf8 eval\run_rag_eval.py</code>
          </div>
        </div>

        <div v-else class="details-content">
          <!-- 报告基本元数据 -->
          <div class="report-meta-card glass-card">
            <div class="meta-row">
              <div class="meta-item">
                <span class="label">运行模式:</span>
                <span class="value badge-text" :class="store.activeReport.run.mode">{{ store.activeReport.run.mode.toUpperCase() }}</span>
              </div>
              <div class="meta-item">
                <span class="label">Dry Run:</span>
                <span class="value">{{ store.activeReport.run.dry_run ? '是' : '否' }}</span>
              </div>
              <div class="meta-item" v-if="store.activeReport.run.base_url">
                <span class="label">API地址:</span>
                <span class="value code-text">{{ store.activeReport.run.base_url }}</span>
              </div>
              <div class="meta-item">
                <span class="label">评估范围:</span>
                <span class="value path-text" :title="store.activeReport.run.cases_path">{{ formatPath(store.activeReport.run.cases_path) }}</span>
              </div>
            </div>
            <div class="meta-row second-row">
              <div class="meta-item">
                <span class="label">开始时间:</span>
                <span class="value">{{ formatTime(store.activeReport.run.started_at) }}</span>
              </div>
              <div class="meta-item">
                <span class="label">结束时间:</span>
                <span class="value">{{ formatTime(store.activeReport.run.finished_at) }}</span>
              </div>
            </div>
          </div>

          <div v-if="configReports.length > 1" class="config-selector-card glass-card">
            <div class="config-selector-header">
              <h4>评估配置对比</h4>
              <span>{{ configReports.length }} 组配置</span>
            </div>
            <div class="config-tabs">
              <button
                v-for="(report, idx) in configReports"
                :key="`${report.label}-${idx}`"
                type="button"
                class="config-tab"
                :class="{ active: activeConfigIndex === idx }"
                @click="selectConfig(idx)"
              >
                {{ report.label || `Config ${idx + 1}` }}
              </button>
            </div>
          </div>

          <!-- 统计指标卡片栏 -->
          <div class="metrics-grid">
            <div class="metric-card glass-card">
              <span class="metric-title">用例通过率</span>
              <span class="metric-value" :class="getPassRateClass(activeSummary.pass_rate)">
                {{ activeSummary.pass_rate !== null ? (activeSummary.pass_rate * 100).toFixed(1) + '%' : '-' }}
              </span>
              <el-progress 
                :percentage="activeSummary.pass_rate !== null ? activeSummary.pass_rate * 100 : 0" 
                :status="activeSummary.pass_rate === 1.0 ? 'success' : ''"
                :show-text="false"
                :stroke-width="4"
                class="metric-progress"
              />
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">关键词匹配率</span>
              <span class="metric-value text-primary">
                {{ activeSummary.keyword_pass_rate !== null ? (activeSummary.keyword_pass_rate * 100).toFixed(1) + '%' : '-' }}
              </span>
              <el-progress 
                :percentage="activeSummary.keyword_pass_rate !== null ? activeSummary.keyword_pass_rate * 100 : 0" 
                :show-text="false"
                :stroke-width="4"
                class="metric-progress"
              />
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">数据源命中率</span>
              <span class="metric-value text-primary">
                {{ activeSummary.source_hit_rate !== null ? (activeSummary.source_hit_rate * 100).toFixed(1) + '%' : '-' }}
              </span>
              <el-progress 
                :percentage="activeSummary.source_hit_rate !== null ? activeSummary.source_hit_rate * 100 : 0" 
                :show-text="false"
                :stroke-width="4"
                class="metric-progress"
              />
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">无答案率</span>
              <span class="metric-value" :class="activeSummary.no_answer_rate > 0 ? 'text-danger' : 'text-success'">
                {{ activeSummary.no_answer_rate !== null ? (activeSummary.no_answer_rate * 100).toFixed(1) + '%' : '-' }}
              </span>
              <el-progress 
                :percentage="activeSummary.no_answer_rate !== null ? activeSummary.no_answer_rate * 100 : 0" 
                :status="activeSummary.no_answer_rate > 0 ? 'exception' : 'success'"
                :show-text="false"
                :stroke-width="4"
                class="metric-progress"
              />
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">平均精选分</span>
              <span class="metric-value text-success">
                {{ activeSummary.average_selected_score !== null ? activeSummary.average_selected_score.toFixed(4) : '-' }}
              </span>
              <span class="metric-sub">选中的 chunks 平均得分</span>
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">平均候选分</span>
              <span class="metric-value text-muted">
                {{ activeSummary.average_candidate_score !== null ? activeSummary.average_candidate_score.toFixed(4) : '-' }}
              </span>
              <span class="metric-sub">召回的所有 chunks 平均得分</span>
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">平均候选数</span>
              <span class="metric-value text-primary">
                {{ formatNumber(activeSummary.average_candidate_count) }}
              </span>
              <span class="metric-sub">每个问题初始召回数量</span>
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">平均入选/拒绝</span>
              <span class="metric-value text-primary">
                {{ formatNumber(activeSummary.average_selected_count) }} / {{ formatNumber(activeSummary.average_rejected_count) }}
              </span>
              <span class="metric-sub">最终上下文筛选结果</span>
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">平均 Rerank 分</span>
              <span class="metric-value text-muted">
                {{ activeSummary.average_rerank_score !== null ? activeSummary.average_rerank_score.toFixed(4) : '-' }}
              </span>
              <span class="metric-sub">rerank 开启时有效</span>
            </div>
            <div class="metric-card glass-card">
              <span class="metric-title">Rerank 改排率</span>
              <span class="metric-value text-primary">
                {{ activeSummary.rerank_changed_top1_rate !== null ? (activeSummary.rerank_changed_top1_rate * 100).toFixed(1) + '%' : '-' }}
              </span>
              <span class="metric-sub">Top1 被 rerank 改变的比例</span>
            </div>
          </div>

          <!-- 失败原因分布 -->
          <div class="failure-distribution-card glass-card" v-if="hasFailureDistribution">
            <div class="card-header">
              <h4>失败原因分布分析</h4>
            </div>
            <div class="failure-list">
              <div 
                v-for="(count, code) in activeSummary.failure_reason_distribution" 
                :key="code"
                class="failure-item"
              >
                <div class="failure-info">
                  <span class="failure-code-badge" :class="code.toLowerCase()">{{ code }}</span>
                  <span class="failure-desc">{{ getFailureReasonDesc(code) }}</span>
                  <span class="failure-count">{{ count }} 例</span>
                </div>
                <el-progress 
                  :percentage="calculateFailurePercentage(count)"
                  :status="code === 'NONE' ? 'success' : 'exception'"
                  :stroke-width="8"
                  class="failure-progress"
                />
              </div>
            </div>
          </div>

          <!-- 用例明细表 -->
          <div class="case-table-card glass-card">
            <div class="card-header flex-header">
              <h4>用例明细表 (Case List)</h4>
              <div class="table-filters">
                <el-radio-group v-model="filterStatus" size="small">
                  <el-radio-button label="all">全部 ({{ totalCasesCount }})</el-radio-button>
                  <el-radio-button label="passed">通过 ({{ passedCasesCount }})</el-radio-button>
                  <el-radio-button label="failed">失败 ({{ failedCasesCount }})</el-radio-button>
                </el-radio-group>
              </div>
            </div>
            
            <el-table 
              :data="filteredCases" 
              style="width: 100%"
              row-class-name="case-row"
              @row-click="handleCaseRowClick"
              highlight-current-row
              ref="caseTableRef"
              class="theme-table"
            >
              <el-table-column prop="case_id" label="Case ID" width="160" show-overflow-tooltip />
              <el-table-column prop="question" label="用例提问" min-width="220" show-overflow-tooltip />
              <el-table-column label="评估状态" width="100">
                <template #default="scope">
                  <el-tag :type="getStatusTagType(scope.row)" size="small">
                    {{ getStatusLabel(scope.row) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="关键词" width="85">
                <template #default="scope">
                  <span v-if="scope.row.status === 'dry_run'" class="text-muted">-</span>
                  <el-tag v-else :type="scope.row.checks?.keyword_pass ? 'success' : 'danger'" size="small">
                    {{ scope.row.checks?.keyword_pass ? '匹配' : '未匹配' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="数据源" width="85">
                <template #default="scope">
                  <span v-if="scope.row.status === 'dry_run'" class="text-muted">-</span>
                  <el-tag v-else :type="scope.row.checks?.source_pass ? 'success' : 'danger'" size="small">
                    {{ scope.row.checks?.source_pass ? '命中' : '未命中' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="可答性" width="85">
                <template #default="scope">
                  <span v-if="scope.row.status === 'dry_run'" class="text-muted">-</span>
                  <el-tag v-else :type="scope.row.checks?.answerable_pass ? 'success' : 'danger'" size="small">
                    {{ scope.row.checks?.answerable_pass ? '匹配' : '不匹配' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="精选分" width="90">
                <template #default="scope">
                  <span class="text-success font-mono" v-if="scope.row.average_selected_score !== null">
                    {{ scope.row.average_selected_score.toFixed(3) }}
                  </span>
                  <span class="text-muted" v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="90">
                <template #default="scope">
                  <span class="font-mono">{{ scope.row.elapsed_seconds.toFixed(2) }}s</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 用例详情对比与问答分析 -->
          <div class="case-detail-panel glass-card" v-if="selectedCase" ref="detailPanelRef">
            <div class="card-header case-detail-header">
              <div class="title-area">
                <h4>用例诊断详情</h4>
                <span class="detail-case-id font-mono">{{ selectedCase.case_id }}</span>
              </div>
              <el-tag :type="getStatusTagType(selectedCase)" size="default">
                {{ getStatusLabel(selectedCase) }}
              </el-tag>
            </div>

            <div class="detail-grid">
              <div class="detail-meta-item">
                <span class="lbl">期望可答:</span>
                <span class="val">{{ selectedCase.expected_answerable ? '是' : '否' }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="lbl">实际可答:</span>
                <span class="val">{{ selectedCase.answerable !== null ? (selectedCase.answerable ? '是' : '否') : '未知' }}</span>
              </div>
              <div class="detail-meta-item" v-if="selectedCase.failure_reason">
                <span class="lbl text-danger">失败原因:</span>
                <span class="val failure-code-badge" :class="selectedCase.failure_reason.toLowerCase()">{{ selectedCase.failure_reason }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="lbl">平均候选分:</span>
                <span class="val font-mono">{{ selectedCase.average_candidate_score !== null ? selectedCase.average_candidate_score.toFixed(4) : '-' }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="lbl">平均精选分:</span>
                <span class="val font-mono text-success">{{ selectedCase.average_selected_score !== null ? selectedCase.average_selected_score.toFixed(4) : '-' }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="lbl">候选/入选/拒绝:</span>
                <span class="val font-mono">
                  {{ selectedCase.candidate_count || 0 }}/{{ selectedCase.selected_count || 0 }}/{{ selectedCase.rejected_count || 0 }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="lbl">平均 Rerank 分:</span>
                <span class="val font-mono">
                  {{ selectedCase.average_rerank_score !== null && selectedCase.average_rerank_score !== undefined ? selectedCase.average_rerank_score.toFixed(4) : '-' }}
                </span>
              </div>
            </div>

            <!-- 问题与答复对比 -->
            <div class="qa-comparison">
              <div class="qa-block user-q">
                <div class="block-title">提问 (Question)</div>
                <div class="block-content">{{ selectedCase.question }}</div>
              </div>
              <div class="qa-block assistant-a">
                <div class="block-title">大模型答复 (Response)</div>
                <div class="block-content whitespace-pre" v-if="selectedCase.answer">{{ selectedCase.answer }}</div>
                <div class="block-content text-muted italic" v-else-if="selectedCase.status === 'dry_run'">Dry-run 模式，未请求真实答复</div>
                <div class="block-content text-danger italic" v-else>无答复内容或请求异常</div>
              </div>
            </div>

            <!-- 关键词匹配明细 -->
            <div class="detail-sub-section" v-if="selectedCase.keyword_results && selectedCase.keyword_results.length > 0">
              <h5>期望关键词匹配情况 (Expected Keywords)</h5>
              <div class="tags-container">
                <div 
                  v-for="kw in selectedCase.keyword_results" 
                  :key="kw.keyword"
                  class="kw-badge" 
                  :class="{ matched: kw.matched }"
                >
                  <svg v-if="kw.matched" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="kw-icon">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="kw-icon">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                  {{ kw.keyword }}
                </div>
              </div>
            </div>

            <!-- 数据源匹配明细 -->
            <div class="detail-sub-section" v-if="selectedCase.source_results && selectedCase.source_results.length > 0">
              <h5>期望引用源匹配情况 (Expected Sources)</h5>
              <div class="tags-container">
                <div 
                  v-for="src in selectedCase.source_results" 
                  :key="src.source"
                  class="src-badge" 
                  :class="{ matched: src.matched }"
                >
                  <svg v-if="src.matched" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="kw-icon">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="kw-icon">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                  {{ src.source }}
                </div>
              </div>
            </div>

            <!-- 检索召回片段 Traces -->
            <div class="detail-sub-section" v-if="selectedCase.retrieval_traces && selectedCase.retrieval_traces.length > 0">
              <h5>检索追踪与筛选诊断 (Retrieval Traces)</h5>
              <div class="trace-list">
                <div 
                  v-for="(trace, tIdx) in selectedCase.retrieval_traces" 
                  :key="tIdx"
                  class="trace-item-box"
                >
                  <div class="trace-header">
                    <span class="trace-tool font-mono">{{ trace.tool }}</span>
                    <span class="trace-meta-lbl">查询: <span class="trace-query-val">"{{ trace.query }}"</span></span>
                    <span class="trace-meta-lbl">阈值: <span class="font-mono">{{ trace.threshold }}</span></span>
                    <span class="trace-meta-lbl">候选TopK: <span class="font-mono">{{ trace.candidate_top_k || trace.top_k }}</span></span>
                    <span class="trace-meta-lbl">最终TopK: <span class="font-mono">{{ trace.final_top_k || '-' }}</span></span>
                    <span class="trace-meta-lbl">召回: <span class="font-mono text-primary">{{ trace.candidate_count }}</span></span>
                    <span class="trace-meta-lbl">精选: <span class="font-mono text-success">{{ trace.selected_count }}</span></span>
                    <span class="trace-meta-lbl">Rerank: <span class="font-mono">{{ trace.rerank_enabled ? `${trace.rerank_provider || ''}/${trace.rerank_model || 'on'}` : 'off' }}</span></span>
                    <span class="trace-meta-lbl" v-if="trace.rerank_enabled">Applied: <span class="font-mono">{{ trace.rerank_applied ? 'yes' : 'fallback' }}</span></span>
                  </div>
                  <div class="trace-context-row text-danger" v-if="trace.rerank_error">
                    Rerank Error: <span class="font-mono">{{ trace.rerank_error }}</span>
                  </div>
                  <div class="trace-context-row" v-if="trace.context_assembly">
                    上下文：
                    <span class="font-mono text-success">{{ trace.context_assembly.used_chunks || 0 }}</span>
                    /
                    <span class="font-mono">{{ trace.context_assembly.max_chunks || '-' }}</span>
                    chunks，估算 tokens：
                    <span class="font-mono">{{ trace.context_assembly.estimated_tokens || 0 }}</span>
                    /
                    <span class="font-mono">{{ trace.context_assembly.max_tokens || '-' }}</span>
                  </div>
                  
                  <div class="trace-candidates-list" v-if="trace.candidates && trace.candidates.length > 0">
                    <div 
                      v-for="cand in trace.candidates" 
                      :key="cand.rank"
                      class="cand-item"
                      :class="cand.status"
                    >
                      <div class="cand-row">
                        <span class="cand-rank badge-text font-mono">#{{ cand.rank }}</span>
                        <span class="cand-citation font-mono">{{ cand.citation_id }}</span>
                        <span class="cand-score font-mono" :class="cand.status === 'selected' ? 'text-success' : 'text-muted'">
                          Score: {{ cand.score.toFixed(4) }}
                        </span>
                        <span class="cand-status-badge badge" :class="cand.status">
                          {{ getCandidateStatusLabel(cand.status) }}
                        </span>
                        <span class="cand-rerank font-mono text-muted" v-if="cand.rerank_score !== null && cand.rerank_score !== undefined">
                          Rerank: {{ cand.rerank_score.toFixed(3) }}
                        </span>
                        <span class="cand-reason text-muted" v-if="cand.rejection_reason">
                          {{ getRejectionLabel(cand.rejection_reason) }}
                        </span>
                        <span class="cand-source text-muted">{{ cand.source }}</span>
                        <span class="cand-parent font-mono text-muted" v-if="cand.parent_id">{{ cand.parent_id }}</span>
                      </div>
                      <div class="cand-preview" :title="cand.content_preview">{{ cand.content_preview }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Markdown 原文区域 -->
          <div class="markdown-report-card glass-card">
            <el-collapse v-model="activeCollapse">
              <el-collapse-item name="markdown" title="📄 查看 Markdown 原文报告摘要">
                <div class="markdown-body" v-html="renderedMarkdown"></div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useEvalReportStore } from '@/stores/evalReports'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const store = useEvalReportStore()
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true
})

const filterStatus = ref('all')
const selectedCase = ref(null)
const activeCollapse = ref([])
const caseTableRef = ref(null)
const detailPanelRef = ref(null)
const activeConfigIndex = ref(0)

// 刷新报告列表
const refreshReports = async () => {
  selectedCase.value = null
  activeConfigIndex.value = 0
  await store.fetchReports()
}

// 选择某份报告
const selectReport = async (name) => {
  selectedCase.value = null
  activeConfigIndex.value = 0
  filterStatus.value = 'all'
  await store.selectReport(name)
}

const selectConfig = (index) => {
  activeConfigIndex.value = index
  selectedCase.value = null
  filterStatus.value = 'all'
}

// 格式化文件名
const formatFileName = (name) => {
  if (!name) return ''
  const match = name.match(/^rag_eval_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(.+)\.json$/)
  if (match) {
    const [_, year, month, day, hour, minute, second, mode] = match
    const modeStr = mode.toUpperCase() === 'HTTP' ? '网络接口' : '本地测试'
    return `评估报告 - ${year}/${month}/${day} ${hour}:${minute}:${second} (${modeStr})`
  }
  return name.replace('rag_eval_', '').replace('.json', '')
}

// 格式化路径，简化显示
const formatPath = (path) => {
  if (!path) return ''
  const parts = path.split(/[\\/]/)
  return parts.slice(-3).join('/')
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  try {
    const date = new Date(timeStr)
    if (isNaN(date.getTime())) return timeStr
    
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    const hh = String(date.getHours()).padStart(2, '0')
    const mm = String(date.getMinutes()).padStart(2, '0')
    const ss = String(date.getSeconds()).padStart(2, '0')
    
    return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
  } catch (e) {
    return timeStr
  }
}

const formatNumber = (value) => {
  if (value === null || value === undefined) return '-'
  if (typeof value !== 'number') return value
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

const configReports = computed(() => {
  return store.activeReport?.threshold_reports || []
})

const activeConfigReport = computed(() => {
  const reports = configReports.value
  if (reports.length === 0) return null
  return reports[Math.min(activeConfigIndex.value, reports.length - 1)]
})

// 对应当前配置报告的 summary 指针
const activeSummary = computed(() => {
  const defaults = {
    case_count: 0,
    pass_rate: null,
    keyword_pass_rate: null,
    source_hit_rate: null,
    no_answer_rate: null,
    average_selected_score: null,
    average_candidate_score: null,
    average_rerank_score: null,
    average_candidate_count: null,
    average_selected_count: null,
    average_rejected_count: null,
    rerank_changed_top1_rate: null,
    failure_reason_distribution: {},
  }
  if (!activeConfigReport.value) return defaults
  return { ...defaults, ...(activeConfigReport.value.summary || {}) }
})

// 检查是否存在失败原因分布
const hasFailureDistribution = computed(() => {
  const dist = activeSummary.value.failure_reason_distribution
  if (!dist) return false
  return Object.keys(dist).length > 0
})

// 计算错误比率
const calculateFailurePercentage = (count) => {
  const cases = activeSummary.value.case_count || 1
  return Math.min(100, Math.round((count / cases) * 100))
}

// 获取失败原因描述
const getFailureReasonDesc = (code) => {
  const mapping = {
    'NONE': '用例通过，无检测错误',
    'NO_SOURCES_FOUND': 'RAG 检索阶段未召回任何符合阈值的数据源 (Recall=0)',
    'LOW_CONFIDENCE': 'LLM 评估检索到的文档证据不足，判定无法回答 (Low Confidence)',
    'LOW_SCORE_FILTERED': '候选片段都低于当前相似度阈值',
    'RERANK_FILTERED': '候选片段被 rerank 阶段过滤',
    'DEDUP_FILTERED': '候选片段因 parent 或内容重复被过滤',
    'CONTEXT_BUDGET_EXCEEDED': '候选片段超过最终上下文条数或 token 预算',
    'NO_CONTEXT_AFTER_ASSEMBLY': '检索后处理完成后没有可用上下文',
    'NO_PARENT_FOUND': '未能取回完整的父文本块导致回答依据受限 (No Parent Found)',
    'TOOL_ERROR': '向量数据库查询或相关检索工具执行出错 (Tool Error)',
    'REWRITE_UNSUPPORTED': '问题意图分析改写模块异常 (Rewrite Error)'
  }
  return mapping[code] || '未知检索失败原因'
}

// 各项用例计数
const totalCases = computed(() => {
  return activeConfigReport.value?.cases || []
})

const totalCasesCount = computed(() => totalCases.value.length)
const passedCasesCount = computed(() => totalCases.value.filter(c => c.passed === true).length)
const failedCasesCount = computed(() => totalCases.value.filter(c => c.passed === false).length)

// 过滤后的用例列表
const filteredCases = computed(() => {
  const cases = totalCases.value
  if (filterStatus.value === 'passed') {
    return cases.filter(c => c.passed === true)
  } else if (filterStatus.value === 'failed') {
    return cases.filter(c => c.passed === false)
  }
  return cases
})

// 表格行点击事件
const handleCaseRowClick = (row) => {
  selectedCase.value = row
  nextTick(() => {
    if (detailPanelRef.value) {
      detailPanelRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

// 获取通过率样式
const getPassRateClass = (rate) => {
  if (rate === null) return 'text-muted'
  if (rate >= 0.9) return 'text-success'
  if (rate >= 0.6) return 'text-warning'
  return 'text-danger'
}

// 获取通过标签类型
const getStatusTagType = (row) => {
  if (row.status === 'dry_run') return 'info'
  return row.passed ? 'success' : 'danger'
}

// 获取状态文案
const getStatusLabel = (row) => {
  if (row.status === 'dry_run') return 'DRY RUN'
  return row.passed ? 'PASSED' : 'FAILED'
}

const getCandidateStatusLabel = (status) => {
  const mapping = {
    selected: 'SELECTED',
    rejected_low_score: 'LOW SCORE',
    rejected_low_rerank: 'LOW RERANK',
    rejected_duplicate_parent: 'DUP PARENT',
    rejected_duplicate_content: 'DUP CONTENT',
    rejected_context_budget: 'BUDGET',
  }
  return mapping[status] || 'REJECTED'
}

const getRejectionLabel = (reason) => {
  const mapping = {
    BELOW_SCORE_THRESHOLD: '低于分数阈值',
    BELOW_RERANK_THRESHOLD: '低于 rerank 阈值',
    DUPLICATE_PARENT: '重复 parent',
    DUPLICATE_CONTENT: '重复内容',
    CONTEXT_BUDGET_EXCEEDED: '上下文预算',
  }
  return mapping[reason] || reason
}

// 渲染 Markdown 为 HTML
const renderedMarkdown = computed(() => {
  if (!store.markdown) return '<p class="text-muted">暂无 Markdown 原文内容</p>'
  return DOMPurify.sanitize(md.render(store.markdown))
})

// 监听选中的报告变化，重置用例选择
watch(() => store.activeReportName, () => {
  selectedCase.value = null
  activeConfigIndex.value = 0
})

onMounted(() => {
  store.fetchReports()
})
</script>

<script>
// 页面级别 CSS 补充
</script>

<style scoped>
.eval-reports-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 32px;
  overflow: hidden;
  gap: 24px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
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

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-icon {
  width: 14px;
  height: 14px;
}

.view-body {
  flex: 1;
  display: flex;
  gap: 24px;
  overflow: hidden;
}

/* 左侧边栏列表 */
.reports-sidebar {
  width: 280px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  background-color: var(--bg-secondary);
}

.sidebar-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-sidebar {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
  gap: 12px;
  font-size: 13.5px;
}

.empty-icon {
  width: 28px;
  height: 28px;
  stroke-width: 1.5;
}

.report-item {
  padding: 14px;
  border-radius: var(--border-radius-sm);
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.report-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: rgba(59, 130, 246, 0.2);
}

.report-item.active {
  background-color: var(--color-primary-bg);
  border-color: var(--color-primary);
  box-shadow: inset 0 0 8px rgba(59, 130, 246, 0.15);
}

.item-meta {
  display: flex;
  gap: 6px;
}

.badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.badge.http {
  background-color: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.badge.local {
  background-color: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.badge.dry-run {
  background-color: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.item-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-time {
  font-size: 11.5px;
  color: var(--text-muted);
}

.item-stats {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.pass-rate-stat {
  font-weight: 600;
}

/* 右侧详情区 */
.report-details {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-details, .error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
  gap: 16px;
  text-align: center;
}

.empty-icon-large, .error-icon {
  width: 48px;
  height: 48px;
  color: var(--text-muted);
  stroke-width: 1.5;
}

.error-icon {
  color: var(--color-danger);
}

.empty-details h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-desc {
  font-size: 13.5px;
  color: var(--text-secondary);
  max-width: 320px;
}

.command-box {
  background-color: rgba(9, 13, 22, 0.6);
  border: 1px solid var(--border-color);
  padding: 12px 18px;
  border-radius: var(--border-radius-sm);
  font-family: monospace;
  font-size: 12.5px;
  color: var(--color-primary-hover);
  margin-top: 8px;
}

.details-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 报告元数据 */
.report-meta-card {
  padding: 16px 20px;
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}

.second-row {
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  padding-top: 10px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}

.meta-item .label {
  color: var(--text-muted);
}

.meta-item .value {
  color: var(--text-primary);
  font-weight: 500;
}

.badge-text {
  font-weight: 600;
}

.badge-text.http {
  color: #34d399;
}

.badge-text.local {
  color: #60a5fa;
}

.code-text {
  font-family: monospace;
  background-color: rgba(0, 0, 0, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.path-text {
  max-width: 250px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: monospace;
  font-size: 12.5px;
  color: var(--text-secondary);
}

/* 指标卡片网络 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.config-selector-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.config-selector-header h4 {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.config-selector-header span {
  font-size: 12px;
  color: var(--text-muted);
}

.config-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-tab {
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  padding: 7px 10px;
  text-align: left;
  transition: all var(--transition-fast);
}

.config-tab:hover,
.config-tab.active {
  border-color: rgba(59, 130, 246, 0.35);
  background: var(--color-primary-bg);
  color: var(--color-primary-hover);
}

.metric-card {
  padding: 20px;
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}

.metric-title {
  font-size: 12.5px;
  color: var(--text-secondary);
  font-weight: 500;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Outfit', sans-serif;
  letter-spacing: -0.5px;
}

.metric-progress {
  margin-top: 4px;
}

.metric-sub {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.3;
}

/* 失败分布卡片 */
.failure-distribution-card {
  padding: 20px;
  background-color: var(--bg-secondary);
}

.card-header {
  margin-bottom: 16px;
}

.card-header h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.flex-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.failure-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.failure-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.failure-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.failure-code-badge {
  font-family: monospace;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: rgba(239, 68, 68, 0.15);
  color: var(--color-danger-hover);
}

.failure-code-badge.none {
  background-color: rgba(16, 185, 129, 0.15);
  color: var(--color-success-hover);
}

.failure-desc {
  color: var(--text-secondary);
  flex: 1;
}

.failure-count {
  font-weight: 600;
  color: var(--text-primary);
}

.failure-progress {
  max-width: 100%;
}

/* 用例明细表 */
.case-table-card {
  padding: 20px;
  background-color: var(--bg-secondary);
}

.theme-table {
  background: transparent !important;
  --el-table-bg-color: transparent !important;
  --el-table-tr-bg-color: transparent !important;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.02) !important;
  --el-table-border-color: rgba(255, 255, 255, 0.05) !important;
  --el-table-text-color: var(--text-secondary) !important;
  --el-table-header-text-color: var(--text-primary) !important;
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.03) !important;
}

:deep(.case-row) {
  cursor: pointer;
  transition: all var(--transition-fast);
}

:deep(.el-table__row.current-row > td.el-table__cell) {
  background-color: rgba(59, 130, 246, 0.08) !important;
  border-left: 2px solid var(--color-primary);
}

/* 用例详情面板 */
.case-detail-panel {
  padding: 24px;
  background-color: var(--bg-secondary);
  border: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: slideDown 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.case-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 12px;
  margin-bottom: 0;
}

.case-detail-header h4 {
  font-size: 15.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-case-id {
  font-size: 12.5px;
  color: var(--text-muted);
  background-color: rgba(255, 255, 255, 0.04);
  padding: 2px 8px;
  border-radius: 4px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  background-color: rgba(0, 0, 0, 0.15);
  padding: 14px 18px;
  border-radius: var(--border-radius-sm);
  border: 1px solid rgba(255, 255, 255, 0.02);
}

.detail-meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.detail-meta-item .lbl {
  color: var(--text-muted);
}

.detail-meta-item .val {
  color: var(--text-primary);
  font-weight: 500;
}

/* 问答对比 */
.qa-comparison {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qa-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: var(--border-radius-sm);
}

.user-q {
  background-color: rgba(59, 130, 246, 0.03);
  border-left: 3px solid var(--color-primary);
}

.assistant-a {
  background-color: rgba(16, 185, 129, 0.02);
  border-left: 3px solid var(--color-success);
}

.block-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.user-q .block-title {
  color: var(--color-primary-hover);
}

.assistant-a .block-title {
  color: var(--color-success-hover);
}

.block-content {
  font-size: 13.5px;
  color: var(--text-primary);
  line-height: 1.6;
}

.block-content.whitespace-pre {
  white-space: pre-wrap;
}

/* 子段落设置 */
.detail-sub-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  padding-top: 16px;
}

.detail-sub-section h5 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kw-badge, .src-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  padding: 4px 10px;
  border-radius: 4px;
  font-family: monospace;
  background-color: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: var(--color-danger-hover);
  transition: all var(--transition-fast);
}

.kw-badge.matched, .src-badge.matched {
  background-color: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.15);
  color: var(--color-success-hover);
}

.kw-icon {
  width: 12px;
  height: 12px;
  stroke-width: 2.5;
}

/* Trace列表 */
.trace-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.trace-item-box {
  background-color: rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-radius: var(--border-radius-sm);
  padding: 14px;
}

.trace-header {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12.5px;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  padding-bottom: 10px;
  margin-bottom: 12px;
}

.trace-context-row {
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  margin: -4px 0 12px;
  padding-bottom: 10px;
}

.trace-tool {
  color: var(--color-warning-hover);
  font-weight: 600;
  background-color: rgba(245, 158, 11, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
}

.trace-meta-lbl {
  color: var(--text-muted);
}

.trace-query-val {
  color: var(--text-primary);
  font-style: italic;
  font-weight: 500;
}

.trace-candidates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cand-item {
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12.5px;
  background-color: rgba(255, 255, 255, 0.01);
  border: 1px solid rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all var(--transition-fast);
}

.cand-item.selected {
  border-left: 3px solid var(--color-success);
  background-color: rgba(16, 185, 129, 0.015);
}

.cand-item.rejected_low_score {
  border-left: 3px solid var(--text-muted);
}

.cand-item.rejected_low_rerank,
.cand-item.rejected_context_budget {
  border-left: 3px solid var(--color-warning);
}

.cand-item.rejected_duplicate_parent,
.cand-item.rejected_duplicate_content {
  border-left: 3px solid var(--color-primary);
}

.cand-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.cand-rank {
  font-size: 11px;
  color: var(--text-muted);
}

.cand-citation {
  font-weight: 700;
  color: var(--color-primary-hover);
}

.cand-score {
  font-weight: 600;
}

.cand-status-badge {
  font-size: 9px;
  padding: 1px 4px;
}

.cand-status-badge.selected {
  background-color: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.cand-status-badge.rejected_low_score {
  background-color: rgba(107, 114, 128, 0.15);
  color: #9ca3af;
}

.cand-status-badge.rejected_low_rerank,
.cand-status-badge.rejected_context_budget {
  background-color: rgba(245, 158, 11, 0.15);
  color: var(--color-warning-hover);
}

.cand-status-badge.rejected_duplicate_parent,
.cand-status-badge.rejected_duplicate_content {
  background-color: rgba(59, 130, 246, 0.12);
  color: var(--color-primary-hover);
}

.cand-preview {
  color: var(--text-secondary);
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: sans-serif;
}

/* Markdown原文卡片 */
.markdown-report-card {
  margin-top: 10px;
  background-color: var(--bg-secondary) !important;
  overflow: hidden;
}

:deep(.el-collapse) {
  border: none !important;
}

:deep(.el-collapse-item__header) {
  background-color: transparent !important;
  color: var(--text-primary) !important;
  font-size: 14.5px !important;
  font-weight: 600 !important;
  border-bottom: none !important;
  padding: 0 20px !important;
  height: 50px !important;
  line-height: 50px !important;
  transition: background var(--transition-fast);
}

:deep(.el-collapse-item__header:hover) {
  background-color: rgba(255, 255, 255, 0.02) !important;
}

:deep(.el-collapse-item__wrap) {
  background-color: transparent !important;
  border-bottom: none !important;
}

:deep(.el-collapse-item__content) {
  color: var(--text-secondary) !important;
  padding: 12px 20px 24px 20px !important;
}

.markdown-body {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-secondary);
}

:deep(.markdown-body h1), :deep(.markdown-body h2), :deep(.markdown-body h3) {
  color: var(--text-primary);
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

:deep(.markdown-body h1) { font-size: 18px; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 6px; }
:deep(.markdown-body h2) { font-size: 15px; }
:deep(.markdown-body h3) { font-size: 13.5px; }

:deep(.markdown-body table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

:deep(.markdown-body th), :deep(.markdown-body td) {
  border: 1px solid rgba(255,255,255,0.06);
  padding: 8px 12px;
  text-align: left;
}

:deep(.markdown-body th) {
  background-color: rgba(255,255,255,0.02);
  color: var(--text-primary);
  font-weight: 600;
}

:deep(.markdown-body code) {
  font-family: monospace;
  background-color: rgba(0,0,0,0.2);
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 12px;
}

:deep(.markdown-body ul), :deep(.markdown-body ol) {
  padding-left: 20px;
  margin: 10px 0;
}

:deep(.markdown-body li) {
  margin-bottom: 4px;
}
</style>
