import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import App from '../App.vue'
import { client, memoryStore } from './fixtures.js'
import { notesApi, notesStore, note } from './notes-fixtures.js'

let wrapper
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.useRealTimers() })
const button = (text, selector = 'button') => wrapper.findAll(selector).find(value => value.text().includes(text))
async function openNotes(api, store) {
  wrapper = mount(App, { attachTo: document.body, props: { client: api,
    store: memoryStore({ student_id: 'learner-test' }), notesStore: store } })
  await flushPromises(); await button('我的笔记', 'nav button').trigger('click'); await flushPromises()
}

describe('notes page integration', () => {
  it('edits, previews safe Markdown/LaTeX, links two topics, saves by keyboard and restores after refresh', async () => {
    vi.useFakeTimers()
    const api = { ...client(), ...notesApi() }, store = notesStore()
    await openNotes(api, store)
    await button('新建笔记').trigger('click'); await wrapper.get('#note-title').setValue('我的梯度笔记')
    const raw = '# 梯度\n\n$x^2$\n\n<script>window.noteExecuted=true</script>\n\n[危险](javascript:alert(1))'
    await wrapper.get('#note-content').setValue(raw)
    await vi.advanceTimersByTimeAsync(310)
    expect(wrapper.get('.note-preview h1').text()).toBe('梯度')
    expect(wrapper.find('.note-preview .katex').exists()).toBe(true)
    expect(wrapper.find('.note-preview script').exists()).toBe(false)
    expect(wrapper.find('.note-preview a[href^="javascript"]').exists()).toBe(false)
    expect(window.noteExecuted).toBeUndefined()
    await wrapper.get('.note-links input[value="linear_regression_loss"]').setValue(true)
    await wrapper.get('.note-links input[value="gradient_descent"]').setValue(true)
    await wrapper.get('#note-content').trigger('keydown', { key: 's', ctrlKey: true }); await flushPromises()
    expect(wrapper.get('.note-editor-heading').text()).toContain('已保存')
    expect(api.createNote.mock.calls[0][1].knowledge_point_ids).toEqual(['gradient_descent', 'linear_regression_loss'])
    expect(api.createNote.mock.calls[0][1].content_md).toBe(raw)
    expect(api.tutor).not.toHaveBeenCalled(); expect(api.submit).not.toHaveBeenCalled(); expect(api.search).not.toHaveBeenCalled()
    wrapper.unmount(); await openNotes(api, store)
    expect(wrapper.get('#note-content').element.value).toBe(raw)
    expect(wrapper.get('#note-title').element.value).toBe('我的梯度笔记')
    expect(wrapper.get('label[for="note-content"]').text()).toContain('Markdown')
    expect(wrapper.get('input[type="file"]').attributes('aria-label')).toContain('UTF-8')
    await button('预览', '.notes-view-switch button').trigger('click')
    expect(wrapper.get('.note-editor-grid').classes()).toContain('mode-preview')
  })
  it('protects unsaved work across pages and identity changes with a keyboard accessible dialog', async () => {
    const api = { ...client(), ...notesApi() }; await openNotes(api, notesStore())
    await button('新建笔记').trigger('click'); await wrapper.get('#note-content').setValue('retain this draft')
    const history = button('学习概览', 'nav button'); history.element.focus(); await history.trigger('click'); await flushPromises()
    const dialog = wrapper.get('[role="dialog"]')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(dialog.get('[data-cancel]').element)
    await dialog.get('[data-cancel]').trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(dialog.findAll('button')[0].element)
    await dialog.trigger('keydown', { key: 'Escape' }); await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(history.element)
    expect(wrapper.get('#note-content').element.value).toBe('retain this draft')
    await history.trigger('click'); await button('保留本机草稿并继续').trigger('click'); await flushPromises()
    expect(wrapper.find('.learning-grid').exists()).toBe(true)
    await button('我的笔记', 'nav button').trigger('click'); await flushPromises()
    // Returning from another tab still acknowledges the retained dirty editor.
    if (wrapper.find('[role="dialog"]').exists()) { await button('保留本机草稿并继续').trigger('click'); await flushPromises() }
    expect(wrapper.get('#note-content').element.value).toBe('retain this draft')
    await wrapper.get('[aria-label="切换学习标识"]').trigger('click'); await flushPromises()
    expect(wrapper.get('[role="dialog"]').text()).toContain('未保存')
    await button('取消', '[role="dialog"] button').trigger('click')
    expect(wrapper.get('.learner-chip').text()).toBe('learner-test')
  })
  it('deletes a saved note only after confirmation and removes it from the list', async () => {
    const api = { ...client(), ...notesApi([note()]) }; await openNotes(api, notesStore())
    await button('损失函数', '.notes-list button').trigger('click'); await flushPromises()
    await button('删除笔记').trigger('click'); expect(api.deleteNote).not.toHaveBeenCalled()
    await button('确认删除').trigger('click'); await flushPromises()
    expect(api.deleteNote).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.notes-list').exists()).toBe(false); expect(wrapper.find('#note-content').exists()).toBe(false)
    expect(wrapper.text()).toContain('笔记已从列表删除')
    expect(api.submit).not.toHaveBeenCalled(); expect(api.tutor).not.toHaveBeenCalled()
  })
  it('imports a UTF-8 file through the labelled file input', async () => {
    const api = { ...client(), ...notesApi() }; await openNotes(api, notesStore())
    const input = wrapper.get('input[type="file"]'), bytes = new TextEncoder().encode('# 导入\n\n$L$')
    const upload = new File([bytes], '课堂.md', { type: 'text/markdown' })
    upload.arrayBuffer = async () => bytes.buffer
    Object.defineProperty(input.element, 'files', { value: [upload], configurable: true })
    await input.trigger('change'); await flushPromises()
    expect(api.importNote).toHaveBeenCalledTimes(1)
    expect(wrapper.get('#note-content').element.value).toBe('# 导入\n\n$L$')
    expect(wrapper.get('.note-editor-heading').text()).toContain('已保存')
  })
})
