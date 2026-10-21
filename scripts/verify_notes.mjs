// Real localhost HTTP checks with synthetic learners; no browser or model calls.
import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { createApi } from '../frontend/src/api.js'

const client = createApi((path, options) => fetch(`http://127.0.0.1:8000${path}`, options))
const suffix = randomUUID().slice(0, 8), owner = `verify-notes-${suffix}`, other = `verify-notes-other-${suffix}`
const checks = [], pass = name => checks.push({ name, passed: true })
const failure = async (operation, status) => assert.rejects(operation, error => error.status === status)
const health = await client.health()
await client.start(owner, ['logistic_regression']); await client.start(other, ['gradient_descent'])
const before = await client.mastery(owner), historyBefore = await client.history(owner)
const links = ['gradient_descent', 'linear_regression_loss']
const body = { id: randomUUID(), title: '合成笔记：梯度与损失', knowledge_point_ids: links,
  content_md: '# 我的理解\n\n$$w := w-\\eta\\nabla L$$\n\n<script>window.notesShouldNotExecute=true</script>' }
const first = await client.createNote(owner, body)
assert.equal(first.revision, 1); assert.equal(first.content_md, body.content_md)
assert.equal(first.content_hash, createHash('sha256').update(body.content_md).digest('hex'))
assert.deepEqual(first.knowledge_point_ids, links); assert.equal(first.index_status, 'disabled')
assert.equal((await client.createNote(owner, body)).id, first.id)
assert.equal((await client.notes(owner)).total, 1)
pass('create Markdown/LaTeX, multiple links, hash and duplicate replay')

const changed = await client.updateNote(owner, first.id, { expected_revision: 1, content_md: `${body.content_md}\n\n补充理解。` })
assert.equal(changed.revision, 2)
assert.deepEqual(await client.note(owner, first.id), changed)
await failure(() => client.updateNote(owner, first.id, { expected_revision: 1, title: 'stale' }), 409)
assert.deepEqual(await client.note(owner, first.id), changed)
pass('save, restore and stale revision protection')

const versions = await Promise.allSettled(['并发A', '并发B'].map(title => client.updateNote(owner, first.id,
  { expected_revision: 2, title })))
assert.equal(versions.filter(result => result.status === 'fulfilled').length, 1)
assert.equal(versions.find(result => result.status === 'rejected').reason.status, 409)
const current = await client.note(owner, first.id); assert.equal(current.revision, 3)
pass('concurrent update has exactly one winner')

assert.equal((await client.notes(other)).total, 0)
await failure(() => client.note(other, first.id), 404)
await failure(() => client.updateNote(other, first.id, { expected_revision: 3, title: 'other' }), 404)
await failure(() => client.deleteNote(other, first.id, 3), 404)
pass('cross-learner read, update and delete isolation')

for (const extension of ['md', 'txt']) {
  const content = '\ufeff# 导入\r\n\r\n$x^2$\r\n'
  const imported = await client.importNote(owner, { id: randomUUID(), file_name: `自建测试.${extension}`,
    content_base64: Buffer.from(content, 'utf8').toString('base64'), knowledge_point_ids: links })
  assert.equal(imported.content_md, '# 导入\n\n$x^2$\n')
  assert.equal(imported.created_via, 'import'); assert.equal(imported.import_warnings.length, 2)
  await client.deleteNote(owner, imported.id, 1)
}
pass('UTF-8 Markdown/TXT import with BOM/LF normalization and delete')

await failure(() => client.importNote(owner, { id: randomUUID(), file_name: '../invalid.md', content_base64: 'eA==' }), 422)
await failure(() => client.importNote(owner, { id: randomUUID(), file_name: 'invalid.pdf', content_base64: 'eA==' }), 422)
await failure(() => client.importNote(owner, { id: randomUUID(), file_name: 'encoding.md', content_base64: '/w==' }), 422)
await failure(() => client.createNote(owner, { ...body, id: randomUUID(), content_md: 'x'.repeat(65537) }), 413)
await failure(() => client.createNote(owner, { ...body, id: randomUUID(), content_md: 'x'.repeat(262145) }), 413)
await failure(() => client.createNote(owner, { ...body, id: randomUUID(), content_html: '<b>invalid field</b>' }), 422)
pass('invalid file path/format/encoding, oversized content/request and forbidden fields')

await client.deleteNote(owner, first.id, 3)
await failure(() => client.note(owner, first.id), 404)
await failure(() => client.createNote(owner, body), 409)
assert.equal((await client.notes(owner)).total, 0)
pass('soft delete hides note and blocks delayed create replay')

assert.deepEqual(await client.mastery(owner), before)
assert.deepEqual(await client.history(owner), historyBefore)
assert.equal((await client.tutorRuns(owner)).length, 0)
pass('notes do not change BKT, scores, history or tutor runs')

const report = { date: new Date().toISOString(), manifest_version: health.version, phase: 'v0.5.0 Phase 2',
  synthetic_data: true, student_ids: [owner, other], new_model_requests: 0, learning_effect_measured: false,
  browser_checks_performed: false, checks, bkt_revision_before: before.revision, bkt_revision_after: before.revision,
  note_ids_retained_as_deleted: true }
if (process.argv[2]) writeFileSync(process.argv[2], `${JSON.stringify(report, null, 2)}\n`, { flag: 'wx' })
console.log(JSON.stringify(report))
