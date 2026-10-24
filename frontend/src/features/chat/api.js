export function workbenchApi(request,studentPath) {
  return {
    knowledgeSources: (id) => request(`${studentPath(id)}/knowledge/sources`),
    workbenchCapabilities: (id) => request(`${studentPath(id)}/workbench/capabilities`),
    workbenchRuns: (id) => request(`${studentPath(id)}/workbench/runs?limit=20`),
    workbenchRun: (id, requestId) => request(`${studentPath(id)}/workbench/runs/${encodeURIComponent(requestId)}`),
    workbenchAsk: (id, body) => request(`${studentPath(id)}/workbench/questions`, { method: 'POST', body, timeout: 260000 }),
    openSource: (id, body) => request(`${studentPath(id)}/workbench/sources/open`, { method: 'POST', body }),
    saveWorkbenchNote: (id, requestId) => request(`${studentPath(id)}/workbench/runs/${encodeURIComponent(requestId)}/note`, { method: 'POST' }),
  }
}
