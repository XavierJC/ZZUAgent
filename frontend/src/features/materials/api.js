export function materialsApi(request, studentPath) {
  const docPath = (id,key='') => `${studentPath(id)}/documents${key ? '/'+encodeURIComponent(key) : ''}`
  const upload=(path,file,metadata)=>{const formData=new FormData();formData.append('metadata',JSON.stringify(metadata));formData.append('file',file);return request(path,{method:'POST',formData,timeout:60000})}
  return {
    courseResources: id => request(`${studentPath(id)}/course-resources`),
    courseResource: (id, resourceId) => request(`${studentPath(id)}/course-resources/${encodeURIComponent(resourceId)}`),
    saveCourseResource: (id, resourceId, body) => request(`${studentPath(id)}/course-resources/${encodeURIComponent(resourceId)}`, { method: 'PUT', body }),
    resourceReceipt: (id, requestId) => request(`${studentPath(id)}/personal-bank/requests/${encodeURIComponent(requestId)}`),
    documentPreview: (id, docId, version, page = 1) => `${docPath(id, docId)}/preview?${new URLSearchParams({ version_id: version, page: String(page) })}`,
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
