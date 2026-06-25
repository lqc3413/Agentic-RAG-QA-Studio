import { defineStore } from 'pinia'
import { getEvalReports, getEvalReportDetail, getEvalReportMarkdown } from '@/api/evalReports'

export const useEvalReportStore = defineStore('evalReports', {
  state: () => ({
    reports: [],
    activeReportName: null,
    activeReport: null,
    markdown: '',
    loading: false,
    detailLoading: false,
    error: null,
  }),
  actions: {
    async fetchReports() {
      this.loading = true
      this.error = null
      try {
        const data = await getEvalReports()
        this.reports = data.reports || []
        
        // 自动选择第一份最新的报告
        if (this.reports.length > 0) {
          // 如果当前选中的报告不再列表中，或者没有选中任何报告，就默认选择最新的
          const exists = this.reports.some(r => r.name === this.activeReportName)
          if (!this.activeReportName || !exists) {
            await this.selectReport(this.reports[0].name)
          }
        } else {
          this.activeReportName = null
          this.activeReport = null
          this.markdown = ''
        }
      } catch (err) {
        console.error('Failed to fetch reports:', err)
        this.error = '获取评估报告列表失败'
      } finally {
        this.loading = false
      }
    },
    async selectReport(name) {
      this.activeReportName = name
      this.detailLoading = true
      this.error = null
      this.activeReport = null
      this.markdown = ''
      
      try {
        // 并发加载 JSON 详情与 Markdown 内容
        const [detailData, mdData] = await Promise.allSettled([
          getEvalReportDetail(name),
          getEvalReportMarkdown(name)
        ])
        
        if (detailData.status === 'fulfilled') {
          this.activeReport = detailData.value
        } else {
          console.error('Failed to load report detail:', detailData.reason)
          this.error = '加载评估报告详情失败'
        }
        
        if (mdData.status === 'fulfilled') {
          this.markdown = mdData.value.content || ''
        } else {
          console.warn('Failed to load report markdown:', mdData.reason)
          this.markdown = '未找到对应的 Markdown 报告或加载失败。'
        }
      } catch (err) {
        console.error('Error in selectReport:', err)
        this.error = '加载报告详情发生错误'
      } finally {
        this.detailLoading = false
      }
    }
  }
})
