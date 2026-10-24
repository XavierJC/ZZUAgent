// Compatibility composition for older resource clients.
import { materialsApi } from '../features/materials/api.js'
import { authoringApi } from '../features/authoring/api.js'
import { practiceApi } from '../features/practice/api.js'
export function resourcesApi(request, studentPath) {
  return { ...materialsApi(request, studentPath), ...authoringApi(request, studentPath), ...practiceApi(request, studentPath) }
}
