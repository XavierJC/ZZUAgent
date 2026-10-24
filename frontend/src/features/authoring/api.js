export function authoringApi(request, studentPath) {
  const architecturePath=(id,key='')=>`${studentPath(id)}/knowledge-architectures${key ? '/'+encodeURIComponent(key) : ''}`
  return {
    publishedCourses: () => request('/api/v1/courses/published'),
    courseReleases: id => request(`${studentPath(id)}/course-releases`),
    courseBuilder: id => request(`${studentPath(id)}/course-builder`),
    teachingLinks: id => request(`${studentPath(id)}/teaching-material-links`),
    courseWorkflow: (id,path,method='GET',body) => request(`${studentPath(id)}/${path}`,{method,body}),
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
  }
}
