import { describe, it, expect, vi } from 'vitest'
import { useWorkspace } from '../useWorkspace.js'
import { ApiError } from '../api.js'
import { client, memoryStore, state, assignment, receipt, savedReply } from './fixtures.js'

describe('learning workspace', () => {
  it('rejects identifiers that cannot be used as a single API path segment', async () => {
    const api = client(), w = useWorkspace(api, memoryStore())
    await w.start('learner/a', ['logistic_regression'])
    expect(api.start).not.toHaveBeenCalled()
    expect(w.error.value).toContain('斜杠')
  })

  it('restores saved state and answers without generating a model response', async () => {
    const api = client(), store = memoryStore({ student_id: 'learner-test' })
    api.tutorRuns.mockResolvedValue([savedReply()])
    const w = useWorkspace(api, store)
    await w.boot(); await w.refresh(); await w.next()
    expect(w.snapshot.value.revision).toBe(0)
    expect(w.tutor.value.run_id).toBe('run-saved')
    expect(api.tutor).not.toHaveBeenCalled()
    expect(api.submit).not.toHaveBeenCalled()
    expect(api.start).not.toHaveBeenCalled()
  })

  it('keeps the same event across a lost response, reload, and changed current assignment', async () => {
    const api = client(), store = memoryStore({ student_id: 'learner-test' })
    const first = useWorkspace(api, store)
    await first.boot(); first.selected.value = 'B'
    api.submit.mockRejectedValueOnce(new ApiError('lost response', { uncertain: true }))
    await first.submit()
    const body = api.submit.mock.calls[0][1]
    expect(store.read().pending.event_id).toBe(body.event_id)
    expect(first.pending.value).not.toBeNull()
    // Simulate the server having committed despite the lost HTTP response.
    api.mastery.mockResolvedValue(state(1)); api.next.mockResolvedValue(assignment(1)); api.currentDecision.mockResolvedValue(assignment(1))
    api.history.mockResolvedValue({ revision: 1, items: [receipt()] })
    api.submit.mockResolvedValue({ ...receipt(), event_id: body.event_id, replayed: true })
    const restored = useWorkspace(api, store)
    await restored.boot()
    expect(restored.decision.value.decision_id).toBe('decision-1')
    await restored.submit()
    expect(api.submit.mock.calls[1][1]).toEqual(body)
    expect(restored.feedback.value.replayed).toBe(true)
    expect(restored.decision.value).toBeNull()
    expect(restored.snapshot.value.revision).toBe(1)
    expect(store.read().pending).toBeNull()
  })

  it('prevents overlapping submissions', async () => {
    const api = client(), w = useWorkspace(api, memoryStore({ student_id: 'learner-test' }))
    await w.boot(); w.selected.value = 'B'
    let finish
    api.submit.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const waiting = w.submit()
    await w.submit()
    expect(api.submit).toHaveBeenCalledTimes(1)
    finish(receipt()); await waiting
    expect(w.pending.value).toBeNull()
  })

  it('does not send an answer when the event id cannot be persisted', async () => {
    const api = client(), store = memoryStore({ student_id: 'learner-test' })
    store.write.mockReturnValue(false)
    const w = useWorkspace(api, store)
    await w.boot(); w.selected.value = 'B'; await w.submit()
    expect(api.submit).not.toHaveBeenCalled()
    expect(w.error.value).toContain('保存提交编号')
  })

  it('reconciles a confirmed stale assignment without changing scores locally', async () => {
    const api = client(), w = useWorkspace(api, memoryStore({ student_id: 'learner-test' }))
    await w.boot(); w.selected.value = 'B'
    api.submit.mockRejectedValue(new ApiError('题目已过期', { status: 409 }))
    api.mastery.mockResolvedValue(state(1)); api.next.mockResolvedValue(assignment(1)); api.currentDecision.mockResolvedValue(assignment(1))
    await w.submit()
    expect(w.pending.value).toBeNull()
    expect(w.feedback.value).toBeNull()
    expect(w.decision.value.revision).toBe(1)
    expect(w.error.value).toContain('过期')
  })

  it('only calls the tutor on an explicit ask and never retries an uncertain request', async () => {
    const api = client(), w = useWorkspace(api, memoryStore({ student_id: 'learner-test' }))
    await w.boot()
    api.tutor.mockRejectedValue(new ApiError('timeout', { uncertain: true }))
    await w.ask('解释 MSE')
    expect(api.tutor).toHaveBeenCalledTimes(1)
    expect(w.notice.value).toContain('再次发送')
    await w.refresh()
    expect(api.tutor).toHaveBeenCalledTimes(1)
  })

  it('clears prior learner data when restoring another identity even if a subsequent read fails', async () => {
    const api = client(), w = useWorkspace(api, memoryStore({ student_id: 'learner-test' }))
    api.history.mockResolvedValue({ items: [receipt()] })
    await w.boot()
    api.start.mockResolvedValue({ ...state(), student_id: 'another' })
    api.history.mockRejectedValue(new Error('offline'))
    await w.start('another', [], true)
    expect(w.student.value).toBe('another')
    expect(w.history.value).toEqual([])
    expect(w.tutorRuns.value).toEqual([])
  })
})
