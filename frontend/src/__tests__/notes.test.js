import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'
import { useNotesWorkspace } from '../useNotesWorkspace.js'
import { noteStore } from '../noteStorage.js'
import { ApiError } from '../api.js'
import { copy, deferred, file, note, noteId, notesApi, notesStore } from './notes-fixtures.js'

const scopes = []
function workspace(api = notesApi(), store = notesStore(), owner = 'learner-test') {
  const scope = effectScope(), student = ref(owner)
  const w = scope.run(() => reactive(useNotesWorkspace(api, student, store)))
  scopes.push(scope)
  return { w, api, store, student }
}
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()) })

describe('personal notes workspace', () => {
  it('creates Markdown with multiple links, edits and restores the saved server version', async () => {
    const { w, api, store } = workspace()
    await w.load(); w.newNote(); w.draft.title = '梯度与损失'; w.draft.content_md = note().content_md
    w.draft.knowledge_point_ids = ['gradient_descent', 'linear_regression_loss']
    await w.save(); const id = w.draft.id
    expect(w.status).toBe('已保存'); expect(w.draft.revision).toBe(1)
    w.draft.content_md += '\n\n$$w := w-\\eta\\nabla L$$'; await w.save()
    expect(w.draft.revision).toBe(2)
    const second = workspace(api, store).w; await second.load()
    expect(second.draft.content_md).toBe(w.draft.content_md)
    expect(second.draft.knowledge_point_ids).toEqual(['gradient_descent', 'linear_regression_loss'])
    expect(second.draft.id).toBe(id); expect(second.dirty).toBe(false)
  })
  it('keeps typing made while a save response is pending as another unsaved edit', async () => {
    const { w, api } = workspace(); w.newNote(); w.draft.content_md = 'first'
    const pending = deferred(); api.createNote.mockReturnValueOnce(pending.promise)
    const saving = w.save(); expect(w.status).toBe('保存中')
    w.draft.content_md = 'second'; pending.resolve(note({ id: w.draft.id, title: w.draft.title, content_md: 'first', knowledge_point_ids: [] }))
    await saving
    expect(w.baseline.content_md).toBe('first'); expect(w.draft.content_md).toBe('second')
    expect(w.dirty).toBe(true); expect(w.pending).toBeNull()
  })
  it('guards navigation, preserves a scope-local draft, and restores it after reload', async () => {
    const { w, api, store } = workspace(); w.newNote(); w.draft.content_md = 'unsaved'
    const destination = vi.fn(); w.navigate(destination)
    expect(w.guard.kind).toBe('leave'); await w.resolveGuard('cancel'); expect(destination).not.toHaveBeenCalled()
    w.navigate(destination); await w.resolveGuard('keep'); expect(destination).toHaveBeenCalledTimes(1)
    const restored = workspace(api, store).w; await restored.load()
    expect(restored.draft.content_md).toBe('unsaved'); expect(restored.dirty).toBe(true)
    expect(api.createNote).not.toHaveBeenCalled()
  })
  it('saves before continuing only after a confirmed server success', async () => {
    const { w, api } = workspace(); w.newNote(); const destination = vi.fn(); w.navigate(destination)
    api.createNote.mockRejectedValueOnce(new ApiError('offline', { uncertain: true }))
    await w.resolveGuard('save'); expect(destination).not.toHaveBeenCalled(); expect(w.guard).not.toBeNull()
    expect(w.pending).not.toBeNull()
  })
  it('does not send a write when local draft persistence fails', async () => {
    const { w, api, store } = workspace(); w.newNote(); store.write.mockReturnValue(false)
    await w.save(); expect(api.createNote).not.toHaveBeenCalled(); expect(w.storageError).toContain('本机草稿保存失败')
    expect(w.pending).toBeNull()
  })
  it('keeps a stale version as a draft and retains a recovery copy when reading the server', async () => {
    const { w, api, store } = workspace(notesApi([note()]))
    await w.load(); await w.open(noteId); w.draft.content_md = 'local edit'
    api.data.set(`learner-test:${noteId}`, note({ revision: 2, content_md: 'server edit' }))
    await w.save(); expect(w.conflict).toBe(true); expect(w.draft.content_md).toBe('local edit')
    await w.save(); expect(api.updateNote).toHaveBeenCalledTimes(1)
    await w.readServer(); await nextTick()
    expect(w.draft.content_md).toBe('server edit'); expect(w.draft.revision).toBe(2)
    const recovery = Object.values(store.read('learner-test').records).find(record => record.draft.content_md === 'local edit')
    expect(recovery.draft.id).not.toBe(noteId); expect(recovery.baseline).toBeNull()
    expect(w.localDrafts.some(value => value.id === recovery.draft.id)).toBe(true)
  })
  it('allows saving a conflicting draft under a fresh identity without overwriting the server', async () => {
    const { w, api } = workspace(notesApi([note()]))
    await w.open(noteId); w.draft.content_md = 'local'; w.conflict = true; w.saveAsNew(); await w.save()
    expect(w.draft.id).not.toBe(noteId); expect(api.createNote).toHaveBeenCalledTimes(1)
    expect(api.data.get(`learner-test:${noteId}`).content_md).toBe(note().content_md)
  })
  it('reconciles a lost create response after reload without another POST', async () => {
    const { w, api, store } = workspace()
    const create = api.createNote.getMockImplementation()
    api.createNote.mockImplementationOnce(async (...args) => { await create(...args); throw new ApiError('lost', { uncertain: true }) })
    w.newNote(); w.draft.content_md = 'committed'; await w.save()
    const next = workspace(api, store).w; await next.load(); expect(next.pending.kind).toBe('create')
    await next.save(); expect(next.status).toBe('已保存'); expect(api.createNote).toHaveBeenCalledTimes(1)
    expect(api.data.size).toBe(1)
  })
  it('retries the exact same create request only after a not-found reconciliation', async () => {
    const { w, api } = workspace(); w.newNote(); w.draft.content_md = 'original'
    api.createNote.mockRejectedValueOnce(new ApiError('lost', { uncertain: true })); await w.save()
    const body = copy(api.createNote.mock.calls[0][1]); w.draft.content_md = 'new typing'
    const destination = vi.fn(); w.navigate(destination); expect(destination).not.toHaveBeenCalled()
    await w.save(); expect(w.pending.retryReady).toBe(true); expect(api.createNote).toHaveBeenCalledTimes(1)
    await w.save(); expect(api.createNote.mock.calls[1][1]).toEqual(body)
    expect(w.draft.content_md).toBe('new typing'); expect(w.dirty).toBe(true)
  })
  it('reconciles a lost update response by reading the committed content', async () => {
    const { w, api } = workspace(notesApi([note()])); await w.open(noteId); w.draft.content_md = 'updated'
    const update = api.updateNote.getMockImplementation()
    api.updateNote.mockImplementationOnce(async (...args) => { await update(...args); throw new ApiError('lost', { uncertain: true }) })
    await w.save(); await w.reconcile()
    expect(w.draft.revision).toBe(2); expect(w.pending).toBeNull(); expect(api.updateNote).toHaveBeenCalledTimes(1)
  })
  it('unblocks an uncertain update when the note was deleted elsewhere, retaining local text', async () => {
    const { w, api } = workspace(notesApi([note()])); await w.open(noteId); w.draft.content_md = 'retain'
    api.updateNote.mockRejectedValueOnce(new ApiError('lost', { uncertain: true })); await w.save()
    api.data.clear(); await w.reconcile(); expect(w.conflict).toBe(true); expect(w.pending).toBeNull()
    w.saveAsNew(); await w.save(); expect(w.draft.content_md).toBe('retain')
  })
  it('confirms deletion and reconciles an already committed DELETE without sending another', async () => {
    const { w, api, store } = workspace(notesApi([note()])); await w.load(); await w.open(noteId)
    const remove = api.deleteNote.getMockImplementation()
    api.deleteNote.mockImplementationOnce(async (...args) => { await remove(...args); throw new ApiError('lost', { uncertain: true }) })
    w.requestDelete(); await w.resolveGuard('cancel'); expect(api.deleteNote).not.toHaveBeenCalled()
    w.requestDelete(); await w.resolveGuard('delete'); expect(w.pending.kind).toBe('delete')
    await w.reconcile(); expect(w.draft).toBeNull(); expect(w.items).toHaveLength(0)
    expect(api.deleteNote).toHaveBeenCalledTimes(1); expect(store.read('learner-test').active_id).toBeNull()
  })
  it('does not relabel a confirmed save as failed when refreshing the list fails', async () => {
    const { w, api } = workspace(); w.newNote(); api.notes.mockRejectedValue(new Error('offline')); await w.save()
    expect(w.status).toBe('已保存'); expect(w.pending).toBeNull(); expect(w.notice).toContain('列表刷新失败')
  })
  it('isolates scope-local drafts and ignores an older learner response even after switching back', async () => {
    const { w, api, store, student } = workspace(); w.newNote(); w.draft.content_md = 'private draft'; await nextTick()
    const waiting = deferred(); api.notes.mockReturnValueOnce(waiting.promise); const loading = w.load()
    student.value = 'other'; await nextTick(); await w.load(); expect(w.draft).toBeNull()
    student.value = 'learner-test'; await nextTick(); await w.load(); expect(w.draft.content_md).toBe('private draft')
    waiting.resolve({ items: [note({ title: 'outdated response' })] }); await loading
    expect(w.items).toHaveLength(0); expect(store.read('other').records || {}).toEqual({})
  })
  it.each(['学习.md', '学习.txt'])('imports UTF-8 %s and preserves Markdown and math', async (name) => {
    const { w, api } = workspace(); const body = '# 标题\r\n\r\n$x^2$'
    await w.importFile(file(name, body)); expect(w.status).toBe('已保存')
    expect(w.draft.content_md).toBe('# 标题\n\n$x^2$'); expect(w.draft.created_via).toBe('import')
    expect(atob(api.importNote.mock.calls[0][1].content_base64).length).toBe(new TextEncoder().encode(body).length)
  })
  it.each([
    ['bad.pdf', new Uint8Array([1]), '只支持'],
    ['large.md', new Uint8Array(65537), '最多'],
    ['encoding.md', new Uint8Array([0xff]), 'UTF-8'],
    ['control.md', new Uint8Array([0]), '控制字符'],
  ])('rejects %s before sending the file', async (name, bytes, message) => {
    const { w, api } = workspace(); await w.importFile(file(name, bytes))
    expect(w.error).toContain(message); expect(api.importNote).not.toHaveBeenCalled()
  })
  it('ignores malformed recovered operations rather than executing unknown local storage', async () => {
    const store = notesStore({ 'learner-test': { active_id: noteId, records: { [noteId]: {
      draft: note(), pending: { kind: 'execute_model', id: noteId, payload: {} } } } } })
    const { w, api } = workspace(notesApi([note()]), store); await w.load()
    expect(w.pending).toBeNull(); expect(w.localDrafts).toHaveLength(0); expect(api.note).toHaveBeenCalledTimes(1)
  })
})

describe('note draft storage', () => {
  it('uses separate learner keys and handles corrupt or inaccessible browser storage', () => {
    const values = new Map(), storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }
    const store = noteStore(storage); store.write('a', { active_id: noteId }); expect(store.read('b')).toEqual({})
    expect(store.read('a').active_id).toBe(noteId)
    expect(noteStore({ getItem: () => 'null' }).read('a')).toEqual({})
    expect(noteStore({ getItem: () => '{broken' }).read('a')).toEqual({})
    expect(noteStore({ setItem: () => { throw Error('quota') } }).write('a', {})).toBe(false)
  })
})
