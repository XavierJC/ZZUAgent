export function notebooksApi(request, studentPath) {
  const base = (student, id = '') => `${studentPath(student)}/notebooks${id ? '/' + encodeURIComponent(id) : ''}`
  return {
    notebooks: (student, archived = false) => request(`${base(student)}?archived=${archived}`),
    notebook: (student, id) => request(base(student, id)),
    createNotebook: (student, body) => request(base(student), { method: 'POST', body }),
    updateNotebook: (student, id, body) => request(base(student, id), { method: 'PATCH', body }),
    notebookReceipt: (student, id) => request(`${base(student)}/requests/${encodeURIComponent(id)}`),
    notebookSources: (student, id, body) => request(`${base(student, id)}/sources`, { method: 'PUT', body }),
    notebookAsk: (student, id, body) => request(`${base(student, id)}/questions`, { method: 'POST', body, timeout: 260000 }),
    notebookRuns: (student, id) => request(`${base(student, id)}/runs`),
    notebookRun: (student, id, requestId) => request(`${base(student, id)}/runs/${encodeURIComponent(requestId)}`),
    notebookPreview: (student, id, body) => request(`${base(student, id)}/sources/open`, { method: 'POST', body }),
    saveNotebookAnswer: (student, id, requestId) => request(`${base(student, id)}/runs/${encodeURIComponent(requestId)}/note`, { method: 'POST' }),
    notebookQuestions: (student, id) => request(`${base(student, id)}/practice/questions`),
    notebookQuestion: (student, id, questionId) => request(`${base(student, id)}/practice/questions/${encodeURIComponent(questionId)}`),
    notebookPractice: (student, id, body) => request(`${base(student, id)}/practice`, { method: 'POST', body }),
    notebookSessions: (student, id) => request(`${base(student, id)}/practice/sessions`),
    notebookPracticeReceipt: (student, id, requestId) => request(`${base(student, id)}/practice/requests/${encodeURIComponent(requestId)}`),
    notebookSession: (student, id, sessionId) => request(`${base(student, id)}/practice/sessions/${encodeURIComponent(sessionId)}`),
    notebookAnswer: (student, id, sessionId, body) => request(`${base(student, id)}/practice/sessions/${encodeURIComponent(sessionId)}/answer`, { method: 'POST', body }),
    notebookPracticeDraft: (student, id, sessionId, body) => request(`${base(student, id)}/practice/sessions/${encodeURIComponent(sessionId)}/draft`, { method: 'PUT', body }),
  }
}
