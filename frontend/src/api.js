import { resourcesApi } from './api/resources.js'
import { workbenchApi } from './api/workbench.js'
import { notesApi } from './api/notes.js'
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'network_error', uncertain = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.uncertain = uncertain
  }
}

export function createApi(fetcher = (...args) => fetch(...args)) {
  async function request(path, { method = 'GET', body, formData, timeout = 20000 } = {}) {
    const writing = !['GET', 'HEAD'].includes(method)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await fetcher(path, {
        method, signal: controller.signal,
        headers: body === undefined || formData ? {} : { 'Content-Type': 'application/json' },
        ...(formData ? { body: formData } : body === undefined ? {} : { body: JSON.stringify(body) }),
      })
      if (response.ok && response.status === 204) return undefined
      let data
      try { data = await response.json() } catch {
        throw new ApiError('服务返回了无法读取的结果，请检查后端是否正常运行。', {
          status: response.status, code: 'invalid_response', uncertain: writing,
        })
      }
      if (!response.ok) {
        throw new ApiError(data?.error?.message || '请求未完成，请稍后重试。', {
          status: response.status, code: data?.error?.code || 'http_error', uncertain: response.status >= 500,
        })
      }
      return data
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(controller.signal.aborted
        ? '等待服务响应超时，请先刷新学习记录。'
        : '暂时连接不到服务，请检查后端是否运行后再重试。', { uncertain: writing })
    } finally { clearTimeout(timer) }
  }
  const studentPath = (id) => `/api/v1/students/${encodeURIComponent(id)}`
  return {
    ...resourcesApi(request,studentPath),
    publishedCourses: () => request('/api/v1/courses/published'),
    courseReleases: id => request(`${studentPath(id)}/course-releases`),
    courseBuilder: id => request(`${studentPath(id)}/course-builder`),
    courseWorkflow: (id,path,method='GET',body) => request(`${studentPath(id)}/${path}`,{method,body}),
    currentDecision: id => request(`${studentPath(id)}/current-decision`),
    teachingHistory: id => request(`${studentPath(id)}/teaching-history`),
    teachingContexts: id => request(`${studentPath(id)}/teaching-explanations`),
    teachingExplain: (id,session,body) => request(`${studentPath(id)}/teaching-sessions/${encodeURIComponent(session)}/explain`,{method:'POST',body,timeout:260000}),
    health: () => request('/health'),
    knowledge: () => request('/api/v1/knowledge-points'),
    start: (id, goals) => request('/api/v1/students', {
      method: 'POST', body: { student_id: id, ...(goals ? { goals } : {}) },
    }),
    mastery: (id) => request(`${studentPath(id)}/mastery`),
    next: (id) => request(`${studentPath(id)}/next`, { method: 'POST' }),
    history: (id) => request(`${studentPath(id)}/history?limit=50`),
    tutorRuns: (id) => request(`${studentPath(id)}/tutor-runs?limit=5`),
    submit: (id, body) => request(`${studentPath(id)}/answers`, { method: 'POST', body }),
    tutor: (id, question) => request(`${studentPath(id)}/tutor`, {
      method: 'POST', body: { question }, timeout: 120000,
    }),
    search: (query) => request('/api/v1/materials/search', { method: 'POST', body: { query } }),
    ...workbenchApi(request,studentPath),
    learningGuidance: (id) => request(`${studentPath(id)}/learning-guidance`),
    selfAssessments: (id) => request(`${studentPath(id)}/self-assessments/latest`),
    selfAssessmentHistory: (id) => request(`${studentPath(id)}/self-assessments?limit=50`),
    saveSelfAssessments: (id, body) => request(`${studentPath(id)}/self-assessments`, { method: 'POST', body }),
    selfAssessmentReceipt: (id, requestId) => request(`${studentPath(id)}/self-assessments/requests/${encodeURIComponent(requestId)}`),
    studyGuides: (id) => request(`${studentPath(id)}/study-guides?limit=20`),
    studyGuide: (id, requestId) => request(`${studentPath(id)}/study-guides/${encodeURIComponent(requestId)}`),
    generateStudyGuide: (id, body) => request(`${studentPath(id)}/study-guides`, { method: 'POST', body, timeout: 260000 }),
    ...notesApi(request,studentPath),
  }
}

export const api = createApi()
