import { describe, it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../api.js'
import { browserStore } from '../storage.js'

describe('HTTP adapter', () => {
  it('uses encoded learner paths and sends only answer event fields', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const api = createApi(fetcher), body = { decision_id: 'd', event_id: 'e', answer: 'B' }
    await api.submit('learner/a?', body)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/students/learner%2Fa%3F/answers')
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(body)
    expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty('Authorization')
  })
  it('retains error codes for confirmed conflicts and does not retry automatically', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 409,
      json: async () => ({ error: { code: 'submission_conflict', message: '已提交' } }) })
    await expect(createApi(fetcher).submit('a', {})).rejects.toMatchObject({ status: 409, code: 'submission_conflict', uncertain: false })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('treats transport errors and invalid POST responses as uncertain without printing upstream data', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('upstream private headers'))
    await expect(createApi(fetcher).tutor('a', 'why')).rejects.toMatchObject({ uncertain: true, code: 'network_error' })
    fetcher.mockResolvedValue({ ok: true, status: 200, json: async () => { throw new Error('upstream raw body') } })
    await expect(createApi(fetcher).submit('a', {})).rejects.toMatchObject({ uncertain: true, code: 'invalid_response' })
  })
  it('handles an empty successful DELETE and encodes note filters and paths', async () => {
    const json = vi.fn(), fetcher = vi.fn().mockResolvedValue({ ok: true, status: 204, json })
    const api = createApi(fetcher)
    await expect(api.deleteNote('a/b', 'note/id', 2)).resolves.toBeUndefined()
    expect(json).not.toHaveBeenCalled()
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/students/a%2Fb/notes/note%2Fid?expected_revision=2')
    expect(fetcher.mock.calls[0][1].method).toBe('DELETE')
    fetcher.mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) })
    await api.notes('a', 'loss & x', 'gradient_descent')
    const path = new URL(fetcher.mock.calls[1][0], 'http://test')
    expect(path.searchParams.get('q')).toBe('loss & x')
    expect(path.searchParams.get('knowledge_id')).toBe('gradient_descent')
  })
  it('marks failed PATCH and DELETE transport responses as uncertain without retrying', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('private transport details'))
    const api = createApi(fetcher)
    await expect(api.updateNote('a', 'n', {})).rejects.toMatchObject({ uncertain: true })
    await expect(api.deleteNote('a', 'n', 1)).rejects.toMatchObject({ uncertain: true })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})

describe('local workspace receipt', () => {
  it('recovers from malformed data and blocked browser storage', () => {
    expect(browserStore({ getItem: () => '{invalid' }).read()).toEqual({})
    const blocked = browserStore({ getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('quota') } })
    expect(blocked.read()).toEqual({})
    expect(blocked.write({ student_id: 'a' })).toBe(false)
  })
})
