import { ref, computed, watch } from 'vue'
import { emptyQuestion, objective } from '../questions/types.js'

const empty = emptyQuestion
const decorate = value => ({ ...empty(), ...value, subquestions: (value.subquestions || []).map(v => ({ ...empty(), ...v })) })
const copy = value => JSON.parse(JSON.stringify(value))

export function usePersonalBank(client, student, storage = globalThis.localStorage) {
  const resources = ref([]), knowledge = ref([]), questions = ref([]), current = ref(null), editor = ref(empty()), baseline = ref('')
  const resource = ref(null), sourceUnits = ref([]), resourceDetail = ref(null), sessions = ref([]), session = ref(null), selected = ref('')
  const proposalOriginal = ref(null)
  const autoImport = ref(false)
  const parseRuns = ref([]), tasks = ref([]), extractionCapabilities = ref(null), extractionMode = ref('model'), extractionConsent = ref(false), includeImages = ref(false), needsReview = ref(false)
  const busy = ref(''), error = ref(''), notice = ref(''), pending = ref(null), visible = ref(false), section = ref('resources')
  const paste = ref(''), runId = ref(''), ordinals = ref(''), filter = ref({ q: '', status: '', question_type: '', resource_id: '', chapter_id: '', concept_id: '' })
  const drafts = ref({}), reviewed = ref(false), confirmAnswer = ref(false), acknowledge = ref(false), revisions = ref([])
  const dirty = computed(() => JSON.stringify(editor.value) !== baseline.value)
  const conflict = ref(false)
  const owner = computed(() => student.value)
  let epoch = 0, restored = false, savedSelection = null, draftRevision = null
  const cacheKey = () => `eduagent.personal-bank.v1.${student.value}`
  const request = (path, method = 'GET', body, owner = student.value) => client.bank(owner, path, method, body)
  function persist() {
    if (!student.value) return true
    if (dirty.value) drafts.value[current.value?.id || 'new'] = { payload: copy(editor.value), revision: conflict.value ? draftRevision : current.value?.revision || null, baseline: baseline.value }
    else delete drafts.value[current.value?.id || 'new']
    try {
      storage.setItem(cacheKey(), JSON.stringify({ drafts: drafts.value, current: current.value?.id, resource: resource.value?.resource_id, session: session.value?.id, selected: selected.value, pending: pending.value, paste: paste.value, section: section.value }))
      return true
    } catch { error.value = '无法保留本机草稿和请求编号，请清理存储空间后重试。'; return false }
  }
  watch([editor, paste, selected, section], () => { if (restored) persist() }, { deep: true })
  watch([runId, ordinals, includeImages, paste], () => { extractionConsent.value = false }, { flush: 'sync' })
  watch(editor, () => { reviewed.value = false; confirmAnswer.value = false }, { deep: true, flush: 'sync' })
  watch(student, () => {
    epoch++; autoImport.value=false; restored = false; resources.value = []; questions.value = []; knowledge.value = []; current.value = null
    editor.value = empty(); baseline.value = JSON.stringify(editor.value); resource.value = null; session.value = null; sessions.value = []
    sourceUnits.value = []; parseRuns.value = []; drafts.value = {}; pending.value = null; busy.value = ''; error.value = ''; notice.value = ''; paste.value = ''; selected.value = ''; tasks.value = []; extractionConsent.value = false; extractionCapabilities.value = null; needsReview.value = false; conflict.value = false; savedSelection = null
  }, { flush: 'sync' })
  baseline.value = JSON.stringify(editor.value)

  async function list(token = epoch, owner = student.value) {
    const query = new URLSearchParams(Object.entries(filter.value).filter(([, v]) => v))
    const [catalogue, bank, history] = await Promise.all([request('course-resources', 'GET', undefined, owner), request(`personal-bank/questions?${query}`, 'GET', undefined, owner), request('personal-bank/practice', 'GET', undefined, owner)])
    if (token !== epoch) return
    resources.value = catalogue.items; knowledge.value = catalogue.knowledge; questions.value = bank.items; sessions.value = history.items
  }
  async function load() {
    if (!student.value || busy.value) return
    const token = epoch, owner = student.value; busy.value = 'load'; error.value = ''
    try {
      if (!restored) {
        try { savedSelection = JSON.parse(storage.getItem(cacheKey()) || 'null') } catch { notice.value = '本机草稿无法恢复，已保存题目仍在服务器。' }
        drafts.value = savedSelection?.drafts || {}; pending.value = savedSelection?.pending || null
        paste.value = savedSelection?.paste || ''; section.value = savedSelection?.section || 'resources'; restored = true
      }
      if (pending.value) {
        try {
          const isTask = pending.value.path === 'personal-bank/extraction-tasks'
          const receipt = await request(isTask ? `personal-bank/extraction-tasks/${pending.value.request_id}` : `personal-bank/requests/${pending.value.request_id}`, 'GET', undefined, owner)
          if (token !== epoch) return
          const sent = pending.value
          if (sent.payload && JSON.stringify(drafts.value[sent.question_id || 'new']?.payload) === JSON.stringify(sent.payload)) delete drafts.value[sent.question_id || 'new']
          if (receipt.question_id) savedSelection = { ...savedSelection, current: receipt.question_id }
          if (receipt.question_ids?.length) savedSelection = { ...savedSelection, current: receipt.question_ids[0] }
          if (receipt.session_id) savedSelection = { ...savedSelection, session: receipt.session_id }
          pending.value = null; notice.value = isTask ? '已恢复原提取任务，请查看提取记录；未重发模型。' : '已恢复原操作回执，没有重复导入或提交。'
        } catch { notice.value = '原操作待核对，刷新只查询回执，不自动重发。' }
      }
      await list(token, owner)
      if (token !== epoch) return
      const key = savedSelection?.current || current.value?.id
      if (key) await open(key, token, true)
      else if (drafts.value.new) { current.value = null; editor.value = copy(drafts.value.new.payload); baseline.value = drafts.value.new.baseline }
      const rid = savedSelection?.resource || resource.value?.resource_id
      const item = resources.value.find(r => r.resource_id === rid && r.status === 'active')
      if (item) await selectResource(item, token)
      const sid = savedSelection?.session || session.value?.id
      if (sid) {
        const value = await request(`personal-bank/practice/${sid}`, 'GET', undefined, owner)
        if (token === epoch) { session.value = value; selected.value = savedSelection?.selected || value.result?.selected_answer || value.draft?.response_text || ''; needsReview.value = value.draft?.needs_review || false }
      }
      savedSelection = null; persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function open(key, token = epoch, restoring = false) {
    if (!restoring && !persist()) return
    const value = await request(`personal-bank/questions/${key}`)
    if (token !== epoch) return
    current.value = value; baseline.value = JSON.stringify(decorate(value.payload))
    const draft = drafts.value[key]
    draftRevision = draft?.revision ?? value.revision
    editor.value = decorate(copy(draft?.payload || value.payload))
    conflict.value = Boolean(draft && draft.revision !== value.revision)
    if (conflict.value) notice.value = '服务器题目版本已变化，本机草稿已保留。请对照后显式读取新版本，再恢复需要的修改。'
    reviewed.value = false; confirmAnswer.value = false; acknowledge.value = false
    proposalOriginal.value = null
    if (value.source?.proposal_for?.question_id) { try { const original=await request(`personal-bank/questions/${value.source.proposal_for.question_id}`); if (token===epoch) proposalOriginal.value=original } catch {} }
    persist()
  }
  async function selectResource(item, token = epoch) {
    const value = await request(`course-resources/${item.resource_id}`)
    const history = item.original_source_type === 'document' ? await request(`documents/${item.original_source_id}/parse-runs`) : []
    if (token !== epoch) return
    extractionConsent.value = false; includeImages.value = ['pdf','png','jpg','jpeg','webp'].includes(value.resource.format); resource.value = value.resource; resourceDetail.value = value; sourceUnits.value = value.units
    parseRuns.value = history.filter(r => r.version_id === value.resource.source_version && ['ready', 'partial', 'empty'].includes(r.status) && r.current_status === 'current')
    runId.value = value.run_id || ''; ordinals.value = ''; persist()
  }
  async function guard(action) {
    if (busy.value) return false
    const token = epoch; busy.value = 'working'; error.value = ''
    try { return await action(token) } catch (e) { if (token === epoch) error.value = e.message; return false }
    finally { if (token === epoch) busy.value = '' }
  }
  async function write(path, method, body, after) {
    if (pending.value) { error.value = '请先核对原操作回执，不能直接重复提交。'; return false }
    return guard(async token => {
      const owner = student.value, requestId = crypto.randomUUID(), sent = copy(body)
      pending.value = { request_id: requestId, path, method, body: sent, question_id: current.value?.id || null, payload: sent.payload || null }
      if (!persist()) { pending.value = null; return false }
      try {
        const result = await request(path, method, { ...sent, request_id: requestId }, owner)
        if (token !== epoch) return false
        pending.value = null
        await after?.(result, token); await list(token, owner); persist(); return true
      } catch (e) {
        if (token !== epoch) return false
        if (!e.uncertain && e.status && e.status < 500) pending.value = null
        if (e.code === 'revision_conflict' && path.startsWith('personal-bank/questions/')) { conflict.value = true; draftRevision = current.value?.revision }
        persist(); throw e
      }
    })
  }
  function newQuestion() {
    if (!persist()) return
    current.value = null; baseline.value = JSON.stringify(empty()); editor.value = copy(drafts.value.new?.payload || empty()); section.value = 'bank'
    reviewed.value = false; confirmAnswer.value = false; acknowledge.value = false
    conflict.value = false
  }
  function save(status = 'draft') {
    if (conflict.value) { error.value = '请先处理版本冲突，不能直接覆盖服务器题目。'; return false }
    const key = current.value?.id, captured = copy(editor.value)
    return write(`personal-bank/questions${key ? '/' + key : ''}`, key ? 'PUT' : 'POST', { payload: captured, ...(key ? { expected_revision: current.value.revision } : {}), status,
      reviewed: reviewed.value, confirm_answer: confirmAnswer.value, acknowledge_source_change: acknowledge.value }, async (result, token) => {
      delete drafts.value[key || 'new']; baseline.value = JSON.stringify(captured)
      await open(result.question_id, token, true); notice.value = status === 'practice' ? '已人工确认进入普通练习。BKT和正式学习记录未改变。' : '已保存题目草稿。'
    })
  }
  function extractResource() {
    if (extractionMode.value === 'model') return semanticExtract(false)
    if (!resource.value) return
    const pages = ordinals.value.trim() ? ordinals.value.split(/[,，\s]+/).map(Number) : null
    return write('personal-bank/extractions', 'POST', { resource_id: resource.value.resource_id, source_version: resource.value.source_version, run_id: runId.value || null, ordinals: pages, ...(autoImport.value ? {auto_import:true}: {}) }, async (r, token) => { section.value = 'bank'; await open(r.question_ids[0], token); notice.value = autoImport.value ? `已整理：${r.intake?.ready || 0}题可练，${r.intake?.needs_attention || 0}题待处理，${r.intake?.duplicate || 0}题重复。` : `已提取${r.question_ids.length}份待审核草稿，尚未进入练习。` })
  }
  function extractText() {
    if (extractionMode.value === 'model') return semanticExtract(true)
    return write('personal-bank/extractions', 'POST', { text: paste.value, ...(autoImport.value ? {auto_import:true}: {}) }, async (r, token) => { paste.value = ''; section.value = 'bank'; await open(r.question_ids[0], token) })
  }
  function archive() {
    return write(`personal-bank/questions/${current.value.id}`, 'DELETE', { expected_revision: current.value.revision }, async (r, token) => { await open(r.question_id, token, true); notice.value = '已归档，历史快照和作答仍保留。' })
  }
  function restructure(originals, parts) {
    return write('personal-bank/restructure', 'POST', { originals, questions: parts }, async (r, token) => { await open(r.question_ids[0], token); notice.value = '已保存拆分/合并草稿，原题已归档，需重新审核。' })
  }
  function start(questionId = null) {
    return write('personal-bank/practice', 'POST', { question_id: questionId, concept_id: filter.value.concept_id || null, acknowledge_source_change: acknowledge.value }, async (r, token) => {
      const value = await request(`personal-bank/practice/${r.session_id}`)
      if (token === epoch) { session.value = value; selected.value = ''; section.value = 'practice' }
    })
  }
  function submit() {
    const key = session.value.id
    return write(`personal-bank/practice/${key}/answer`, 'POST', { selected_answer: selected.value, needs_review: needsReview.value }, async (r, token) => {
      const value = await request(`personal-bank/practice/${r.session_id}`)
      if (token === epoch) session.value = value
    })
  }
  async function viewSession(value) { await guard(async token => { const fresh = await request(`personal-bank/practice/${value.id}`); if (token === epoch) { session.value = fresh; selected.value = fresh.result?.selected_answer || fresh.draft?.response_text || ''; needsReview.value = fresh.draft?.needs_review || false; section.value = 'practice'; persist() } }) }
  function keepConflictCopy() { if (!current.value || !persist()) return; drafts.value[`recovery-${current.value.id}-${Date.now()}`] = copy(drafts.value[current.value.id]); delete drafts.value[current.value.id]; notice.value = '冲突草稿已保留为恢复副本。'; return guard(token => open(current.value.id, token, true)) }
  function restoreCopy(key) { if (!persist()) return; editor.value = copy(drafts.value[key].payload); notice.value = '已恢复到本机编辑器，请核对后保存。' }
  function releasePending() { if (!pending.value || !persist()) return; notice.value = '已保留待核对请求的恢复副本；必要时通过原请求编号查询。'; drafts.value[`pending-${pending.value.request_id}`] = { receipt: copy(pending.value) }; pending.value = null; persist() }
  async function loadTasks() {
    const token=epoch, owner=student.value
    const [runs,capabilities]=await Promise.all([request('personal-bank/extraction-tasks','GET',undefined,owner),request('personal-bank/extraction-capabilities','GET',undefined,owner)])
    if (token===epoch) { tasks.value=runs.items; extractionCapabilities.value=capabilities }
  }
  function semanticExtract(pasted=false,target=null) {
    if (!extractionConsent.value) { error.value='请明确同意本轮发送选定原文或原页，选择资料不等于同意外发。'; return false }
    const selectedPages=ordinals.value.trim() ? ordinals.value.split(/[,，\s]+/).map(Number) : null
    const body=pasted ? { text:paste.value } : { resource_id:resource.value.resource_id,source_version:resource.value.source_version,run_id:runId.value || null,ordinals:selectedPages }
    extractionConsent.value=false
    return write('personal-bank/extraction-tasks','POST',{...body,consent:true,include_images:includeImages.value,...(autoImport.value && !target ? {auto_import:true}: {}),...(target ? {target_question_id:target.id,target_revision:target.revision}: {})},async () => {
      extractionConsent.value=false; notice.value='已登记提取任务，可在我的题库查看进度。刷新不会重发模型请求。'; await loadTasks(); section.value='bank'
    })
  }
  function reextract() {
    const s=current.value?.source
    const item=resources.value.find(r=>r.resource_id===s?.resource_id)
    if (!item || item.source_version!==s.source_version) { error.value='原来源已变化，请回课程资料选择当前版本。';return }
    resource.value=item;runId.value=s.run_id || '';ordinals.value=[...new Set((s.evidence || []).map(e=>e.location?.page_number || e.location?.slide_number).filter(Boolean))].join(',')
    return semanticExtract(false,current.value)
  }
  function saveResponseDraft() {
    if (!session.value) return
    return write(`personal-bank/practice/${session.value.id}/draft`,'PUT',{expected_revision:session.value.draft?.revision || 0,response_text:selected.value,needs_review:needsReview.value},async r=>{
      session.value.draft={revision:r.revision,response_text:selected.value,needs_review:needsReview.value};notice.value='文字作答草稿已保存，不判分、不更新BKT。'
    })
  }
  function acceptProposal() {
    const proposal=current.value,original=proposalOriginal.value
    if (!proposal || !original || dirty.value) { error.value='请先保存修正稿并对照原题。';return }
    return write(`personal-bank/questions/${original.id}/accept-proposal`,'POST',{expected_revision:original.revision,proposal_id:proposal.id,proposal_revision:proposal.revision},async (r,token)=>{await open(r.question_id,token,true);notice.value='已接受修正为原题的新草稿版本；旧版本仍保留，需重新人工审核。'})
  }
  return { autoImport, organize: () => write('personal-bank/organize','POST',{},async r => {notice.value=`已整理${r.processed}题：${r.ready}题可练，${r.needs_attention}题待处理。`}), refreshList: () => guard(token => list(token, student.value)), proposalOriginal, acceptProposal, tasks, extractionCapabilities, extractionMode, extractionConsent, includeImages, needsReview, loadTasks, semanticExtract, reextract, saveResponseDraft, owner, conflict, parseRuns, resources, knowledge, questions, current, editor, resource, sourceUnits, resourceDetail, sessions, session, selected, busy, error, notice, pending, visible, section, paste, runId, ordinals, filter, drafts, dirty, reviewed, confirmAnswer, acknowledge, revisions,
    load, persist, guard, open: key => guard(token => open(key, token)), selectResource: item => guard(token => selectResource(item, token)), newQuestion, save, extractResource, extractText, archive, restructure, start, submit, viewSession, keepConflictCopy, restoreCopy, releasePending,
    saveLinks: body => write(`course-resources/${resource.value.resource_id}`, 'PUT', body, async (r, token) => { await selectResource(resource.value, token) }),
    history: () => guard(async token => { const r = await request(`personal-bank/questions/${current.value.id}/revisions`); if (token === epoch) revisions.value = r.items }),
    selectRun: id => guard(async token => {
      const value = await request(`documents/${resource.value.original_source_id}/units?run_id=${encodeURIComponent(id)}&limit=20`)
      if (token === epoch) { runId.value = id; sourceUnits.value = value.items; notice.value = '已选择保存的解析记录；预览最多20个单位，未重复调用模型。' }
    }),
    preview: (source, page = 1) => source?.original_source_type === 'document' ? client.documentPreview(student.value, source.original_source_id, source.source_version, page) : null,
  }
}
