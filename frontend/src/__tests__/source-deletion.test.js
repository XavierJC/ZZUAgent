import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NotebookSourceRow from '../features/notebooks/NotebookSourceRow.vue'

const failed = { source_type: 'uploaded_document', source_id: 'failed', title: '解析失败的合成资料', index_status: 'failed' }
describe('source deletion in the notebook picker', () => {
  it('allows deleting a failed upload with one inline confirmation and cancellation', async () => {
    const ui = mount(NotebookSourceRow, { props: { source: failed, deletable: true } })
    expect(ui.text()).toContain('解析失败')
    expect(ui.findAll('button').find(b => b.text() === '加入主题').attributes('disabled')).toBeDefined()
    const remove = ui.get('[aria-label="删除资料：解析失败的合成资料"]')
    expect(remove.attributes('disabled')).toBeUndefined()
    await remove.trigger('click'); expect(ui.emitted('delete')).toBeUndefined()
    await ui.findAll('button').find(b => b.text() === '取消').trigger('click')
    expect(ui.emitted('delete')).toBeUndefined()
    await ui.get('[aria-label="删除资料：解析失败的合成资料"]').trigger('click')
    await ui.get('[aria-label="确认删除资料：解析失败的合成资料"]').trigger('click')
    expect(ui.emitted('delete')).toHaveLength(1); ui.unmount()
  })
  it('lets a checked unavailable source be removed from the theme in bulk mode', async () => {
    const ui = mount(NotebookSourceRow, { props: { source: failed, bulk: true, checked: true, deletable: true } })
    expect(ui.get('input').attributes('disabled')).toBeUndefined()
    await ui.get('input').setValue(false); expect(ui.emitted('toggle')).toEqual([[false]])
    expect(ui.get('[aria-label="删除资料：解析失败的合成资料"]').exists()).toBe(true)
    await ui.setProps({ busy: true }); expect(ui.get('input').attributes('disabled')).toBeDefined(); ui.unmount()
  })
  it('does not offer uploaded-file deletion for course materials or notes', () => {
    for (const source_type of ['course_material', 'personal_note', 'personal_question']) {
      const ui = mount(NotebookSourceRow, { props: { source: { ...failed, source_type }, deletable: true } })
      expect(ui.find('.source-delete-button').exists()).toBe(false); ui.unmount()
    }
  })
})
