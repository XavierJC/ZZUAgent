import { vi } from 'vitest'

export const points = [
  { id: 'linear_regression_loss', name: '线性回归与损失函数', prerequisites: [], review_tip: '复习 MSE' },
  { id: 'gradient_descent', name: '梯度下降', prerequisites: ['linear_regression_loss'], review_tip: '复习负梯度' },
  { id: 'logistic_regression', name: '逻辑回归', prerequisites: ['gradient_descent'], review_tip: '复习 sigmoid' },
  { id: 'overfitting_regularization', name: '过拟合与正则化', prerequisites: ['model_evaluation'], review_tip: '复习验证' },
  { id: 'model_evaluation', name: '模型评估', prerequisites: [], review_tip: '复习指标' },
]
export function state(revision = 0) {
  return { student_id: 'learner-test', revision, goals: ['logistic_regression'], threshold: 0.8,
    parameter_version: 'bkt-v1', mode: 'offline_rules', mastery: points.map((item, index) => ({
      knowledge_id: item.id, name: item.name, probability: index === 0 && revision ? 10 / 19 : 0.2,
      attempts: index === 0 ? revision : 0, has_evidence: index === 0 && revision > 0,
      last_correct: index === 0 && revision ? true : null,
    })) }
}
export function assignment(revision = 0) {
  return { decision_id: `decision-${revision}`, student_id: 'learner-test', revision, action: revision ? 'practice' : 'diagnose',
    knowledge_id: 'linear_regression_loss', reason: '先用一道题取得答题证据。', evidence: {}, stop_reason: null,
    question: { id: `lr_0${revision + 1}`, version: '1', difficulty: 'easy', knowledge_id: 'linear_regression_loss',
      stem: '两条样本的 MSE 是多少？', options: { A: '1.5', B: '2.5', C: '5', D: '0.5' },
      source: '自建题', review_status: 'pending' } }
}
export function receipt() {
  return { event_id: 'receipt-1', student_id: 'learner-test', decision_id: 'decision-0', question_id: 'lr_01',
    knowledge_id: 'linear_regression_loss', selected_answer: 'B', correct_answer: 'B', correct: true,
    explanation: '先平方再求平均，结果为 2.5。', prior: 0.2, posterior: 9 / 19, next_mastery: 10 / 19,
    created_at: '2026-10-20T08:00:00Z', replayed: false }
}
export function savedReply() {
  return { run_id: 'run-saved', student_id: 'learner-test', mode: 'offline_fallback', model: null,
    model_calls: 0, usage: {}, state_revision: 0, answer: '均方误差需要对残差平方后取平均。[linear:2]',
    citations: [{ citation_id: 'linear:2', title: '线性回归', section: '均方误差定义', source: 'materials/linear_regression.md',
      content: 'MSE 是平方残差的平均值。', review_status: 'pending', score: 0.5 }],
    tools_used: [{ name: 'retrieve_course_material', status: 'ok', citation_ids: ['linear:2'] }],
    fallback_reason: 'model_timeout', next_exercise: assignment() }
}
export function memoryStore(initial = {}) {
  let data = JSON.parse(JSON.stringify(initial))
  return { read: () => JSON.parse(JSON.stringify(data)), write: vi.fn((value) => {
    data = JSON.parse(JSON.stringify(value)); return true
  }) }
}
export function client() {
  return { health: vi.fn().mockResolvedValue({ status: 'ok', version: '0.4.0', question_count: 10,
    pending_review_count: 10, agent_enabled: true, retrieval_available: true }),
  knowledge: vi.fn().mockResolvedValue(points), start: vi.fn().mockResolvedValue(state()),
  mastery: vi.fn().mockResolvedValue(state()), currentDecision: vi.fn().mockResolvedValue(assignment()), next: vi.fn().mockResolvedValue(assignment()),
  history: vi.fn().mockResolvedValue({ student_id: 'learner-test', revision: 0, items: [] }),
  tutorRuns: vi.fn().mockResolvedValue([]), submit: vi.fn().mockResolvedValue(receipt()),
  tutor: vi.fn().mockResolvedValue(savedReply()), search: vi.fn().mockResolvedValue(savedReply().citations) }
}
