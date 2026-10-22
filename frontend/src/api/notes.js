export function notesApi(request,studentPath) {
  return {
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
