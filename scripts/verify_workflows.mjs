// Local engineering checks. Creates synthetic learners; never submits a real
// course question to the provider. No answer keys are part of the web bundle.
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { createApi } from '../frontend/src/api.js'

const client = createApi((path, options) => fetch(`http://127.0.0.1:8000${path}`, options))
const health = await client.health()
assert.equal(health.version, '0.4.1', 'This recorded verification targets server 0.4.1')
const suffix = randomUUID().slice(0, 8)
const completeId = `verify-success-${suffix}`
await client.start(completeId, ['logistic_regression'])
const steps = []
for (const answer of ['B', 'A', 'C', 'D', 'C', 'D']) {
  const decision = await client.next(completeId)
  assert.ok(decision.question && !('answer' in decision.question))
  const payload = { decision_id: decision.decision_id, event_id: randomUUID(), answer }
  const result = await client.submit(completeId, payload)
  assert.equal(result.correct, true)
  if (!steps.length) assert.equal((await client.submit(completeId, payload)).replayed, true)
  steps.push({ question_id: result.question_id, action: decision.action, mastery: result.next_mastery })
}
const finish = await client.next(completeId)
const completeState = await client.mastery(completeId)
assert.equal(finish.action, 'finish')
assert.equal(completeState.revision, 6)
assert.equal((await client.history(completeId)).items.length, 6)

const reviewId = `verify-review-${suffix}`
await client.start(reviewId, ['gradient_descent'])
const first = await client.next(reviewId)
await client.submit(reviewId, { decision_id: first.decision_id, event_id: randomUUID(), answer: 'A' })
const before = await client.mastery(reviewId)
const unsupported = '郑州大学宿舍电费在哪里缴纳？'
assert.deepEqual(await client.search(unsupported), [], 'Evidence rejection must be active before testing the tutor')
const local = await client.tutor(reviewId, unsupported)
assert.equal(local.model_calls, 0)
assert.equal(local.retrieval_policy, 'tfidf-phrase-v2')
assert.equal(local.fallback_reason, 'insufficient_evidence')
assert.deepEqual(await client.mastery(reviewId), before)
assert.equal(local.next_exercise.action, 'review')
await client.submit(reviewId, {
  decision_id: local.next_exercise.decision_id, event_id: randomUUID(), answer: 'A',
})
const stopped = await client.next(reviewId)
assert.equal(stopped.stop_reason, 'insufficient_questions')
assert.equal((await client.mastery(reviewId)).revision, 2)
assert.equal((await client.history(reviewId)).items.length, 2)
assert.equal((await client.tutorRuns(reviewId))[0].run_id, local.run_id)

const report = { version: health.version, synthetic_data: true, new_model_requests: local.model_calls,
  learning_effect_measured: false, success: { student_id: completeId, revision: 6, steps, terminal_action: finish.action },
  review: { student_id: reviewId, wrong_answer_mastery: before.mastery.find(s => s.knowledge_id === 'linear_regression_loss').probability,
    local_feedback_reason: local.fallback_reason, mastery_unchanged_by_question: true,
    terminal_action: stopped.action, stop_reason: stopped.stop_reason, saved_history_count: 2 } }
const output = process.argv[2]
if (output) writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, { flag: 'wx' })
console.log(JSON.stringify(report))
