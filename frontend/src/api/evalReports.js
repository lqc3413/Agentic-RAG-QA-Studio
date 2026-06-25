import { http } from './http'

export async function getEvalReports() {
  const { data } = await http.get('/api/eval/reports')
  return data
}

export async function getEvalReportDetail(name) {
  const { data } = await http.get(`/api/eval/reports/${encodeURIComponent(name)}`)
  return data
}

export async function getEvalReportMarkdown(name) {
  const { data } = await http.get(`/api/eval/reports/${encodeURIComponent(name)}/markdown`)
  return data
}
