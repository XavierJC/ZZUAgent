import { createHttp } from './shared/http.js'
import { learningApi } from './features/learning/api.js'
import { materialsApi } from './features/materials/api.js'
import { authoringApi } from './features/authoring/api.js'
import { practiceApi } from './features/practice/api.js'
import { workbenchApi } from './features/chat/api.js'
import { notesApi } from './features/notes/api.js'
import { notebooksApi } from './features/notebooks/api.js'
export { ApiError } from './shared/http.js'

// Preserve the public client contract; each feature owns its endpoints.
export function createApi(fetcher = (...args) => fetch(...args)) {
  const request = createHttp(fetcher)
  const studentPath = id => `/api/v1/students/${encodeURIComponent(id)}`
  return {
    ...learningApi(request, studentPath), ...materialsApi(request, studentPath),
    ...authoringApi(request, studentPath), ...practiceApi(request, studentPath),
    ...workbenchApi(request, studentPath), ...notesApi(request, studentPath),
    ...notebooksApi(request, studentPath),
  }
}
export const api = createApi()
