import { computed, ref, watch } from 'vue'

const copy = value => JSON.parse(JSON.stringify(value))
// The resource catalogue has no dependency on question editors or practice
// sessions. Reuse the existing backend resource projection, not its UI state.
export function useResourceLibrary(client, student, storage = localStorage) {
  const resources = ref([]), knowledge = ref([]), resource = ref(null), sourceUnits = ref([])
  const editor = ref(null), baseline = ref(''), pending = ref(null), busy = ref(''), error = ref(''), notice = ref('')
  const recoveries = ref([])
  const dirty = computed(() => Boolean(editor.value && JSON.stringify(editor.value) !== baseline.value))
  const owner = computed(() => student.value)
  let epoch = 0, restored = false, saved = null, loading = null, selecting = 0
  const key = () => `eduagent.material-library.v1.${student.value}`
  const request = (path, method = 'GET', body, id = student.value) => client.bank(id, path, method, body)
  const catalogue = id => client.courseResources ? client.courseResources(id) : request('course-resources', 'GET', undefined, id)
  const detail = (id, rid) => client.courseResource ? client.courseResource(id, rid) : request(`course-resources/${rid}`, 'GET', undefined, id)
  function persist() {
    if (!restored || !student.value) return true
    try {
      storage.setItem(key(), JSON.stringify({ selected: resource.value?.resource_id || saved?.selected,
        draft: dirty.value ? editor.value : null, baseline: baseline.value, pending: pending.value, recoveries: recoveries.value }))
      return true
    } catch { error.value = '资料关联草稿无法保存在本机，请先保留内容。'; return false }
  }
  watch(editor, persist, { deep: true, flush: 'sync' })
  watch(student, () => {
    epoch++; selecting++; loading = null; restored = false; saved = null
    resources.value = []; knowledge.value = []; resource.value = null; sourceUnits.value = []; editor.value = null
    baseline.value = ''; pending.value = null; recoveries.value = []; busy.value = ''; error.value = ''; notice.value = ''
  }, { flush: 'sync' })
  async function selectResource(item) {
    if (dirty.value && item.resource_id !== resource.value?.resource_id) { error.value = '请先保存当前资料关联草稿，再选择其他资料。'; return }
    if (!persist()) return
    const token = epoch, serial = ++selecting, id = student.value
    busy.value = 'open'; error.value = ''
    try {
      const value = await detail(id, item.resource_id)
      if (token !== epoch || serial !== selecting) return
      resource.value = value.resource; sourceUnits.value = value.units
      resources.value = resources.value.map(row => row.resource_id === value.resource.resource_id ? value.resource : row)
      const fields = { expected_revision: value.resource.revision, resource_type: value.resource.resource_type, links: copy(value.resource.links || []) }
      baseline.value = JSON.stringify(fields)
      editor.value = saved?.selected === item.resource_id && saved?.draft ? copy(saved.draft) : fields
      if (editor.value.expected_revision !== value.resource.revision) notice.value = '资料已有变化，本机关联草稿保留；保存时必须核对版本。'
      saved = null; persist(); return true
    } catch (e) { if (token === epoch && serial === selecting) error.value = e.message; return false }
    finally { if (token === epoch && serial === selecting) busy.value = '' }
  }
  function load() {
    if (!student.value) return
    if (loading) return loading
    const token = epoch, id = student.value
    loading = (async () => {
      busy.value = 'load'; error.value = ''
      try {
        if (!restored) {
          try { saved = JSON.parse(storage.getItem(key()) || 'null') } catch { /* Read server catalogue even if local cache is invalid. */ }
          if (!saved) {
            try { saved = { selected: JSON.parse(storage.getItem(`eduagent.personal-bank.v1.${id}`) || 'null')?.resource } } catch {}
          }
          pending.value = saved?.pending || null; recoveries.value = Array.isArray(saved?.recoveries) ? saved.recoveries : []; restored = true
        }
        if (pending.value) {
          try {
            if (client.resourceReceipt) await client.resourceReceipt(id, pending.value.request_id)
            else await request(`personal-bank/requests/${pending.value.request_id}`, 'GET', undefined, id)
            if (token !== epoch) return
            pending.value = null; notice.value = '已恢复资料关联回执，没有重复提交。'
          } catch { if (token === epoch) notice.value = '原资料关联保存待核对，刷新只读回执。' }
        }
        const value = await catalogue(id)
        if (token !== epoch) return
        resources.value = value.items; knowledge.value = value.knowledge
        const selected = resource.value?.resource_id || saved?.selected
        const item = value.items.find(r => r.resource_id === selected && r.status === 'active')
        // Refresh must preserve unsaved association edits.
        if (item && !dirty.value) await selectResource(item)
        else if (selected && !item) { resource.value = null; sourceUnits.value = []; notice.value = '所选资料已不可用，本机草稿仍保留。' }
      } catch (e) { if (token === epoch) error.value = e.message }
      finally { if (token === epoch) { busy.value = ''; loading = null } }
    })()
    return loading
  }
  async function saveLinks() {
    if (!resource.value || !editor.value || pending.value || busy.value) return
    const token = epoch, id = student.value, item = resource.value
    pending.value = { request_id: crypto.randomUUID(), resource_id: item.resource_id, body: copy(editor.value) }
    if (!persist()) { pending.value = null; return }
    busy.value = 'save'; error.value = ''
    const operation = copy(pending.value)
    try {
      const body = { ...operation.body, request_id: operation.request_id }
      if (client.saveCourseResource) await client.saveCourseResource(id, item.resource_id, body)
      else await request(`course-resources/${item.resource_id}`, 'PUT', body, id)
      if (token !== epoch) return
      const value = await detail(id, item.resource_id)
      if (token !== epoch) return
      const unchanged = JSON.stringify(editor.value) === JSON.stringify(operation.body)
      resource.value = value.resource; sourceUnits.value = value.units
      resources.value = resources.value.map(row => row.resource_id === value.resource.resource_id ? value.resource : row)
      const fields = { expected_revision: value.resource.revision, resource_type: value.resource.resource_type, links: copy(value.resource.links || []) }
      baseline.value = JSON.stringify(fields)
      if (unchanged) editor.value = fields
      else editor.value.expected_revision = value.resource.revision
      pending.value = null; saved = null; persist()
      notice.value = '资料用途与关联已保存，不改变BKT或正式评分。'
    } catch (e) {
      if (token === epoch) { error.value = e.message; if (e.status && e.status < 500 && !e.uncertain) pending.value = null; persist() }
    } finally { if (token === epoch) busy.value = '' }
  }
  async function readServer() {
    if (!resource.value || busy.value || pending.value) return
    const draft = copy(editor.value), previous = baseline.value, token = epoch
    recoveries.value.push({ id: crypto.randomUUID(), resource_id: resource.value.resource_id, title: resource.value.title, draft })
    if (!persist()) return
    baseline.value = JSON.stringify(editor.value); saved = null
    if (!await selectResource(resource.value) && token === epoch) { editor.value = draft; baseline.value = previous }
  }
  function restoreCopy(entry) {
    if (entry.resource_id !== resource.value?.resource_id || busy.value || pending.value) return
    editor.value = copy(entry.draft); notice.value = '已恢复旧关联草稿；旧版本不能覆盖新数据，请对照核对。'
  }
  return { resources, knowledge, resource, sourceUnits, editor, recoveries, pending, busy, error, notice, dirty, owner,
    load, persist, selectResource, saveLinks, readServer, restoreCopy }
}
