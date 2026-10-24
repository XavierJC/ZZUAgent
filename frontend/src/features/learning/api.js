export function learningApi(request, studentPath) {
  return {
    currentDecision: id => request(`${studentPath(id)}/current-decision`),
    teachingHistory: id => request(`${studentPath(id)}/teaching-history`),
    reviewExercises: id => request(`${studentPath(id)}/review-exercises`),
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
    learningGuidance: (id) => request(`${studentPath(id)}/learning-guidance`),
    selfAssessments: (id) => request(`${studentPath(id)}/self-assessments/latest`),
    selfAssessmentHistory: (id) => request(`${studentPath(id)}/self-assessments?limit=50`),
    saveSelfAssessments: (id, body) => request(`${studentPath(id)}/self-assessments`, { method: 'POST', body }),
    selfAssessmentReceipt: (id, requestId) => request(`${studentPath(id)}/self-assessments/requests/${encodeURIComponent(requestId)}`),
    studyGuides: (id) => request(`${studentPath(id)}/study-guides?limit=20`),
    studyGuide: (id, requestId) => request(`${studentPath(id)}/study-guides/${encodeURIComponent(requestId)}`),
    generateStudyGuide: (id, body) => request(`${studentPath(id)}/study-guides`, { method: 'POST', body, timeout: 260000 }),
  }
}
