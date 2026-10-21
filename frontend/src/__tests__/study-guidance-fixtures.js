import { vi } from 'vitest'
import { points } from './fixtures.js'
import { ApiError } from '../api.js'

export const copy = v => JSON.parse(JSON.stringify(v))
export const course = { source_type: 'course_material', source_id: 'linear', source_version: 'c1', title: '线性回归', index_status: 'ready' }
export const personal = { source_type: 'personal_note', source_id: 'n1', source_version: 'r1-hash', title: '个人合成笔记', index_status: 'ready' }
export function guidance(assessmentRevision = 0, reports = {}, learningRevision = 0) {
  const items = points.map(p => ({ knowledge_id: p.id, name: p.name, prerequisites: p.prerequisites, in_goal_path: true,
    objective: { has_evidence: false, probability: null, prior_probability: .2, attempts: 0, last_correct: null, meets_progress_condition: false },
    self_report: reports[p.id] || null, recent_attempts: [], blocked_by: p.prerequisites, available_questions: 2, round_limit_reached: false,
    reason_codes: ['pending_diagnosis'], reasons: ['尚无正式答题证据，先诊断，先验不是诊断。'], status: 'pending_diagnosis',
    actions: [{ kind: 'open_formal_practice', knowledge_id: p.id }, { kind: 'open_learning_history', knowledge_id: p.id }] }))
  return { course_id: 'machine_learning', learning_revision: learningRevision, assessment_revision: assessmentRevision, rule_version: 'guidance-rules-v1',
    threshold: .8, goals: ['logistic_regression'], goal_names: ['逻辑回归'], versions: { bkt: 'bkt-demo-v1', knowledge: 'ml-knowledge-v1', policy: 'rules-v1', catalog: 'hash', bank: 'bank' },
    snapshot_hash: `l${learningRevision}-s${assessmentRevision}`, items, recommendations: [{ ...items[0], priority: 1 }] }
}
export function guideRun(snapshot = guidance(), id = 'guide-1') {
  return { request_id: id, course_id: 'machine_learning', status: 'local', snapshot: copy(snapshot), rules_md: '# 本地规则指南\n\n待诊断。$w$',
    explanation_md: '', citations: [], sources: [], source_statuses: [], stale_reasons: [], reason: 'rules_requested', model: null, model_calls: 0,
    usage: {}, tools_used: [], created_at: '2026-10-21T08:00:00Z', updated_at: '2026-10-21T08:00:00Z' }
}
export function storage() { const data = new Map(); return { getItem: k => data.get(k) || null, setItem: (k,v) => data.set(k,v) } }
export function api() {
  let snapshot = guidance(), records = [], runs = []
  const receipts = new Map()
  return {
    setSnapshot: v => { snapshot = v },
    learningGuidance: vi.fn(async () => copy(snapshot)), selfAssessmentHistory: vi.fn(async () => ({ items: copy(records) })),
    saveSelfAssessments: vi.fn(async (owner, body) => {
      if (body.expected_revision !== snapshot.assessment_revision) throw new ApiError('自评版本冲突', { status: 409 })
      const revision = snapshot.assessment_revision + 1
      const values = body.items.map((p,i) => ({ ...p, id: `${body.request_id}-${i}`, batch_id: body.request_id,
        student_id: owner, assessment_revision: revision, learning_revision_at_save: snapshot.learning_revision, created_at: '2026-10-21T08:00:00Z' }))
      const reportMap = Object.fromEntries(snapshot.items.filter(p => p.self_report).map(p => [p.knowledge_id, p.self_report]))
      for (const value of values) reportMap[value.knowledge_id] = value
      snapshot = guidance(revision, reportMap, snapshot.learning_revision); records = [...values, ...records]
      const receipt = { request_id: body.request_id, committed_revision: revision, current_revision: revision, learning_revision_at_save: snapshot.learning_revision,
        items: values, replayed: false, created_at: '2026-10-21T08:00:00Z' }
      receipts.set(body.request_id, receipt); return copy(receipt)
    }),
    selfAssessmentReceipt: vi.fn(async (_, id) => { if (!receipts.has(id)) throw new ApiError('没有回执', { status: 404 }); return copy(receipts.get(id)) }),
    studyGuides: vi.fn(async () => copy(runs)), studyGuide: vi.fn(async (_, id) => {
      const value = runs.find(r => r.request_id === id); if (!value) throw new ApiError('未找到', { status: 404 }); return copy(value)
    }),
    generateStudyGuide: vi.fn(async (_, body) => { const value = guideRun(snapshot, body.request_id); runs.unshift(value); return copy(value) }),
    next: vi.fn(), tutor: vi.fn(), workbenchAsk: vi.fn(),
  }
}
