import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { settleCoursePage as flushPromises } from './course-page-testing.js'
import App from '../App.vue'
import TutorPanel from '../components/TutorPanel.vue'
import QuestionPanel from '../components/QuestionPanel.vue'
import { client, memoryStore, state, assignment, receipt, savedReply } from './fixtures.js'

let wrapper
beforeEach(() => history.replaceState(null,'','/#/learn'))
afterEach(() => wrapper?.unmount())

describe('Vue learning interface', () => {
  it('creates a goal, submits a selected option, shows server feedback and history', async () => {
    const api = client()
    wrapper = mount(App, { props: { client: api, store: memoryStore() } })
    await flushPromises()
    expect(wrapper.text()).toContain('先找到起点')
    expect(api.tutor).not.toHaveBeenCalled()
    await wrapper.get('#learner-id').setValue('learner-test')
    await wrapper.get('.start-form').trigger('submit'); await flushPromises()
    expect(api.start).toHaveBeenCalledWith('learner-test', ['logistic_regression'])
    expect(wrapper.findAll('.mastery-list li')).toHaveLength(5)
    expect(wrapper.get('.mastery-list').text()).toContain('尚无答题证据')
    await wrapper.get('input[name="answer"][value="B"]').setValue(true)
    api.mastery.mockResolvedValue(state(1))
    api.history.mockResolvedValue({ revision: 1, items: [receipt()] })
    await wrapper.get('.question-panel form').trigger('submit'); await flushPromises()
    expect(api.submit).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.feedback').text()).toContain('答对了')
    expect(wrapper.get('.feedback').text()).toContain('52.6%')
    const historyTab = wrapper.findAll('button').find(button => button.text().includes('查看正式学习记录'))
    await historyTab.trigger('click'); await flushPromises()
    expect(wrapper.get('.history-list').text()).toContain('lr_01')
    expect(api.tutor).not.toHaveBeenCalled()
  })

  it('restores saved explanations with fallback and citations, without calling the model', async () => {
    const api = client()
    api.tutorRuns.mockResolvedValue([savedReply()])
    wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test' }) } })
    await flushPromises()
    expect(wrapper.get('.tutor-reply').text()).toContain('已降级为离线反馈')
    expect(wrapper.get('.citation').text()).toContain('均方误差定义')
    await wrapper.get('button[aria-label="刷新学习记录"]').trigger('click'); await flushPromises()
    expect(api.tutor).not.toHaveBeenCalled()
  })

  it('renders model text and source content as escaped text', () => {
    const reply = savedReply()
    reply.answer = '<img src=x onerror="alert(1)">'
    reply.citations[0].content = '<script>window.executed = true</script>'
    wrapper = mount(TutorPanel, { props: { reply, runs: [reply], busy: '', enabled: true, topic: 'MSE' } })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.get('.answer-text').text()).toBe(reply.answer)
  })

  it('explains evidence rejection without claiming a model failed or inventing a source', () => {
    const reply = { ...savedReply(), fallback_reason: 'insufficient_evidence', citations: [],
      answer: '当前资料没有足够依据。当前学习安排：先诊断线性回归。' }
    wrapper = mount(TutorPanel, { props: { reply, runs: [reply], busy: '', enabled: true, topic: 'MSE' } })
    expect(wrapper.get('.tutor-reply').text()).toContain('本次未调用模型')
    expect(wrapper.get('.reply-heading').text()).toContain('课程依据不足')
    expect(wrapper.find('.citation').exists()).toBe(false)
  })

  it('searches course material only after explicit action', async () => {
    const api = client()
    wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test' }) } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '课程构建').trigger('click'); await flushPromises()
    await wrapper.findAll('nav button').find(button => button.text().includes('课程资料')).trigger('click'); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '课程片段检索').trigger('click')
    expect(api.search).not.toHaveBeenCalled()
    await wrapper.get('#material-query').setValue('MSE 定义')
    await wrapper.get('.search-form').trigger('submit'); await flushPromises()
    expect(api.search).toHaveBeenCalledWith('MSE 定义')
    expect(wrapper.get('.source-list').text()).toContain('MSE 是平方残差的平均值')
    expect(api.tutor).not.toHaveBeenCalled()
  })

  it('does not paint a recovered old answer onto a newer exercise after reload', async () => {
    const api = client()
    api.mastery.mockResolvedValue(state(1)); api.next.mockResolvedValue(assignment(1)); api.currentDecision.mockResolvedValue(assignment(1))
    api.submit.mockResolvedValue({ ...receipt(), replayed: true })
    wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test',
      pending: { student_id: 'learner-test', decision_id: 'decision-0', event_id: 'receipt-1', answer: 'B' } }) } })
    await flushPromises()
    expect(wrapper.get('.question-panel').text()).toContain('先确认上一次答题')
    expect(wrapper.find('.question-panel form').exists()).toBe(false)
    await wrapper.findAll('.question-panel button').find(button => button.text().includes('重试原提交')).trigger('click')
    await flushPromises()
    expect(wrapper.get('.feedback').text()).toContain(receipt().explanation)
    expect(wrapper.find('.question-stem').exists()).toBe(false)
  })

  it('renders question, options and feedback with the shared component and keeps the fieldset labelled', async () => {
    const decision = assignment()
    decision.question.stem = '**平方损失** $L=(y-\\hat y)^2$'
    decision.question.options.B = '$2.5$'
    wrapper = mount(QuestionPanel, { props: { decision, selected: '', busy: '', topic: '损失函数' } })
    expect(wrapper.get('.question-stem strong').text()).toBe('平方损失')
    expect(wrapper.find('.question-stem .katex').exists()).toBe(true)
    expect(wrapper.get('fieldset').attributes('aria-labelledby')).toBe(wrapper.get('.question-stem').attributes('id'))
    expect(wrapper.find('.option .katex').exists()).toBe(true)
    expect(wrapper.find('legend div').exists()).toBe(false)
    await wrapper.get('input[value="B"]').setValue(true)
    expect(wrapper.emitted('select')[0]).toEqual(['B'])
    await wrapper.setProps({ feedback: { ...receipt(), explanation: '**先平方**，结果为 $2.5$。' } })
    expect(wrapper.get('.feedback strong').text()).toContain('答对了')
    expect(wrapper.find('.feedback .katex').exists()).toBe(true)
    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
  })

  it('renders saved tutor, citations, history and material results without generating a model answer', async () => {
    const api = client()
    const reply = savedReply()
    reply.answer = '## 更新方向\n\n沿负梯度更新 $w$。[linear:2]'
    reply.citations[0].content = '**课程原文** $L=x^2$'
    api.tutorRuns.mockResolvedValue([reply])
    api.history.mockResolvedValue({ revision: 1, items: [{ ...receipt(), explanation: '**解析** $L=2.5$' }] })
    api.search.mockResolvedValue(reply.citations)
    wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test' }) } })
    await flushPromises()
    expect(wrapper.get('.answer-text h2').text()).toBe('更新方向')
    expect(wrapper.find('.answer-text .katex').exists()).toBe(true)
    expect(wrapper.find('.citation .katex').exists()).toBe(true)
    await wrapper.findAll('button').find(button => button.text().includes('查看正式学习记录')).trigger('click'); await flushPromises()
    expect(wrapper.find('.history-detail .katex').exists()).toBe(true)
    await wrapper.findAll('button').find(button => button.text() === '课程构建').trigger('click'); await flushPromises()
    await wrapper.findAll('nav button').find(button => button.text().includes('课程资料')).trigger('click'); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '课程片段检索').trigger('click')
    await wrapper.get('#material-query').setValue('平方损失')
    await wrapper.get('.search-form').trigger('submit'); await flushPromises()
    expect(wrapper.get('.source-card strong').text()).toBe('课程原文')
    expect(wrapper.find('.source-card .katex').exists()).toBe(true)
    expect(api.tutor).not.toHaveBeenCalled()
    expect(api.submit).not.toHaveBeenCalled()
  })
})
