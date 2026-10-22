export function resourcesApi(request, studentPath) {
  const docPath = (id,key='') => `${studentPath(id)}/documents${key ? '/'+encodeURIComponent(key) : ''}`
  const architecturePath=(id,key='')=>`${studentPath(id)}/knowledge-architectures${key ? '/'+encodeURIComponent(key) : ''}`
  const upload=(path,file,metadata)=>{const formData=new FormData();formData.append('metadata',JSON.stringify(metadata));formData.append('file',file);return request(path,{method:'POST',formData,timeout:60000})}
  return {
    bank: (id, path, method = 'GET', body) => request(`${studentPath(id)}/${path}`, { method, body }),
    documentPreview: (id, docId, version, page = 1) => `${docPath(id, docId)}/preview?${new URLSearchParams({ version_id: version, page: String(page) })}`,
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
  }
}
