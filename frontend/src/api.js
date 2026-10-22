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
  const docPath = (id, docId = '') => `${studentPath(id)}/documents${docId ? '/' + encodeURIComponent(docId) : ''}`
  const architecturePath = (id, key = '') => `${studentPath(id)}/knowledge-architectures${key ? '/' + encodeURIComponent(key) : ''}`
  const upload = (path, file, metadata) => {
    const formData = new FormData(); formData.append('metadata', JSON.stringify(metadata)); formData.append('file', file)
    return request(path, { method: 'POST', formData, timeout: 60000 })
  }
  return {
    architectures: id => request(architecturePath(id)),
    architecture: (id, key) => request(architecturePath(id, key)),
    createArchitecture: (id, body) => request(architecturePath(id), { method: 'POST', body }),
    architectureReceipt: (id, requestId) => request(`${architecturePath(id)}/requests/${encodeURIComponent(requestId)}`),
    saveArchitecture: (id, key, body) => request(`${architecturePath(id, key)}/draft`, { method: 'PUT', body }),
    forkArchitecture: (id, key, body) => request(`${architecturePath(id, key)}/draft`, { method: 'POST', body }),
    publishArchitecture: (id, key, body) => request(`${architecturePath(id, key)}/publish`, { method: 'POST', body }),
    architectureVersion: (id, key, version) => request(`${architecturePath(id, key)}/versions/${version}`),
    extractArchitecture: (id, key, body) => request(`${architecturePath(id, key)}/candidates`, { method: 'POST', body }),
    architectureCandidates: (id, key, batchId) => request(`${architecturePath(id, key)}/candidates/${encodeURIComponent(batchId)}`),
    conceptLearningState: (id, key, concept, version, draft = false) => request(`${architecturePath(id, key)}/concepts/${encodeURIComponent(concept)}/learning-state?${new URLSearchParams({ draft: String(draft), ...(version ? { version: String(version) } : {}) })}`),
    documents: (id) => request(docPath(id)),
    documentCapabilities: (id) => request(`${docPath(id)}/capabilities`),
    document: (id, docId) => request(docPath(id, docId)),
    documentReceipt: (id, requestId) => request(`${docPath(id)}/operations/${encodeURIComponent(requestId)}`),
    documentRuns: (id, docId) => request(`${docPath(id, docId)}/parse-runs`),
    documentUnits: (id, docId, runId, offset = 0) => request(`${docPath(id, docId)}/units?${new URLSearchParams({ run_id: runId, offset: String(offset), limit: '10' })}`),
    uploadDocument: (id, file, metadata) => upload(docPath(id), file, metadata),
    uploadDocumentVersion: (id, docId, file, metadata) => upload(`${docPath(id, docId)}/versions`, file, metadata),
    updateDocument: (id, docId, body) => request(docPath(id, docId), { method: 'PATCH', body }),
    deleteDocument: (id, docId, body) => request(docPath(id, docId), { method: 'DELETE', body }),
    parseDocument: (id, docId, body) => request(`${docPath(id, docId)}/parse`, { method: 'POST', body }),
    visionDocument: (id, docId, body) => request(`${docPath(id, docId)}/vision`, { method: 'POST', body }),
    documentDownloadUrl: (id, docId, versionId) => `${docPath(id, docId)}/original?${new URLSearchParams({ version_id: versionId })}`,
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
    knowledgeSources: (id) => request(`${studentPath(id)}/knowledge/sources`),
    workbenchCapabilities: (id) => request(`${studentPath(id)}/workbench/capabilities`),
    workbenchRuns: (id) => request(`${studentPath(id)}/workbench/runs?limit=20`),
    workbenchRun: (id, requestId) => request(`${studentPath(id)}/workbench/runs/${encodeURIComponent(requestId)}`),
    workbenchAsk: (id, body) => request(`${studentPath(id)}/workbench/questions`, { method: 'POST', body, timeout: 260000 }),
    openSource: (id, body) => request(`${studentPath(id)}/workbench/sources/open`, { method: 'POST', body }),
    saveWorkbenchNote: (id, requestId) => request(`${studentPath(id)}/workbench/runs/${encodeURIComponent(requestId)}/note`, { method: 'POST' }),
    learningGuidance: (id) => request(`${studentPath(id)}/learning-guidance`),
    selfAssessments: (id) => request(`${studentPath(id)}/self-assessments/latest`),
    selfAssessmentHistory: (id) => request(`${studentPath(id)}/self-assessments?limit=50`),
    saveSelfAssessments: (id, body) => request(`${studentPath(id)}/self-assessments`, { method: 'POST', body }),
    selfAssessmentReceipt: (id, requestId) => request(`${studentPath(id)}/self-assessments/requests/${encodeURIComponent(requestId)}`),
    studyGuides: (id) => request(`${studentPath(id)}/study-guides?limit=20`),
    studyGuide: (id, requestId) => request(`${studentPath(id)}/study-guides/${encodeURIComponent(requestId)}`),
    generateStudyGuide: (id, body) => request(`${studentPath(id)}/study-guides`, { method: 'POST', body, timeout: 260000 }),
    notes: (id, query = '', knowledge = '') => request(`${studentPath(id)}/notes?${new URLSearchParams({
      limit: '50', ...(query ? { q: query } : {}), ...(knowledge ? { knowledge_id: knowledge } : {}),
    })}`),
    note: (id, noteId) => request(`${studentPath(id)}/notes/${encodeURIComponent(noteId)}`),
    createNote: (id, body) => request(`${studentPath(id)}/notes`, { method: 'POST', body }),
    updateNote: (id, noteId, body) => request(`${studentPath(id)}/notes/${encodeURIComponent(noteId)}`, { method: 'PATCH', body }),
    deleteNote: (id, noteId, revision) => request(`${studentPath(id)}/notes/${encodeURIComponent(noteId)}?expected_revision=${revision}`, { method: 'DELETE' }),
    importNote: (id, body) => request(`${studentPath(id)}/notes/import`, { method: 'POST', body }),
  }
}

export const api = createApi()
