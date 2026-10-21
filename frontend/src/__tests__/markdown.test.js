import { describe, it, expect, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { isSafeLink, renderMarkdown, RENDER_LIMITS } from '../rendering/markdown.js'
import fixtures from '../../../data/evaluation/markdown-fixtures.json'

let wrapper
afterEach(() => wrapper?.unmount())
function tree(source, options) {
  const result = renderMarkdown(source, options)
  const root = document.createElement('div')
  root.innerHTML = result.html
  return { ...result, root }
}
function expectInert(root) {
  expect(root.querySelector('script,iframe,object,embed,img,style,form,input,template,foreignObject')).toBeNull()
  for (const node of root.querySelectorAll('*')) {
    for (const attribute of node.attributes) {
      expect(attribute.name).not.toMatch(/^on/i)
      if (['href', 'xlink:href'].includes(attribute.name)) expect(isSafeLink(attribute.value)).toBe(true)
    }
  }
}

describe('fixed Markdown / LaTeX development fixtures', () => {
  for (const sample of fixtures.cases) {
    it(sample.id, () => {
      const result = tree(sample.source)
      for (const [selector, count] of Object.entries(sample.selectors)) {
        expect(result.root.querySelectorAll(selector), selector).toHaveLength(count)
      }
      if (sample.contains) expect(result.root.textContent).toContain(sample.contains)
      if (sample.notice) expect(result.notices.length).toBeGreaterThan(0)
      expectInert(result.root)
    })
  }
})

describe('renderer boundaries and component contract', () => {
  it('isolates macros across documents and repeated renders', () => {
    const first = tree('$\\gdef\\personalMacro{42}\\personalMacro$')
    expect(first.root.querySelector('.katex')).not.toBeNull()
    const second = tree('$\\personalMacro$')
    expect(second.root.querySelector('.math-raw').textContent).toBe('\\personalMacro')
    expect(second.notices).not.toHaveLength(0)
  })

  it('keeps invalid formula payload inert and omits raw parser errors', () => {
    const log = vi.spyOn(console, 'error')
    const result = tree('$\\notARealCommand{<img src=x onerror=alert(1)>}$')
    expectInert(result.root)
    expect(result.root.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(result.root.querySelector('[title]')).toBeNull()
    expect(log).not.toHaveBeenCalled()
  })

  it('caps individual formula length and preserves its original text', () => {
    const raw = 'x'.repeat(RENDER_LIMITS.formulaChars + 1)
    const result = tree(`$${raw}$`)
    expect(result.root.querySelector('.katex')).toBeNull()
    expect(result.root.querySelector('.math-raw').textContent).toBe(raw)
    expect(result.notices).not.toHaveLength(0)
  })

  it('caps the number of formulas without losing remaining text', () => {
    const result = tree(Array(RENDER_LIMITS.formulas + 2).fill('$x$').join(' '))
    expect(result.root.querySelectorAll('.katex')).toHaveLength(RENDER_LIMITS.formulas)
    expect(result.root.querySelectorAll('.math-raw')).toHaveLength(2)
    expect(result.notices).toHaveLength(1)
  })

  it('bounds macro expansion loops and dimensions', () => {
    const loop = tree('$\\def\\repeat{\\repeat}\\repeat$')
    expect(loop.root.querySelector('.math-raw')).not.toBeNull()
    const large = tree('$\\rule{500em}{500em}$')
    for (const node of large.root.querySelectorAll('*')) {
      for (const attribute of node.attributes) expect(attribute.value).not.toContain('500em')
    }
    expect(large.root.querySelector('[style*="20em"]')).not.toBeNull()
    expectInert(loop.root)
    expectInert(large.root)
  })

  it('renders oversized UTF-8 content as full escaped plain text', () => {
    const source = '中'.repeat(Math.ceil(RENDER_LIMITS.documentBytes / 3)) + '<img src=x onerror=alert(1)>'
    const result = tree(source)
    expect(result.root.textContent).toBe(source)
    expect(result.notices).not.toHaveLength(0)
    expectInert(result.root)
  })

  it('keeps long or unknown-language code readable without highlighting', () => {
    const code = 'return '.repeat(Math.ceil(RENDER_LIMITS.codeChars / 7) + 1)
    const result = tree('```python\n' + code + '\n```\n\n```unknown\n<script>text</script>\n```')
    expect(result.root.querySelectorAll('pre')).toHaveLength(2)
    expect(result.root.querySelector('pre code').textContent).toContain(code)
    expect(result.root.querySelector('.hljs-keyword')).toBeNull()
    expectInert(result.root)
  })

  it('adds safe external link behavior but keeps local anchors in the document', () => {
    const { root } = tree('[外链](https://example.com) [锚点](#section)')
    const [external, anchor] = root.querySelectorAll('a')
    expect(external.getAttribute('target')).toBe('_blank')
    expect(external.getAttribute('rel')).toBe('noopener noreferrer')
    expect(external.getAttribute('referrerpolicy')).toBe('no-referrer')
    expect(anchor.hasAttribute('target')).toBe(false)
    for (const value of ['javascript:alert(1)', 'data:text/html,x', '//example.com', '/api', 'https:\\evil', 'https://e.com\n']) {
      expect(isSafeLink(value)).toBe(false)
    }
  })

  it('provides a focusable table scroll region and a display formula container', () => {
    const { root } = tree('| x | y |\n| --- | --- |\n| 1 | 2 |\n\n$$\nx^2+y^2\n$$')
    expect(root.querySelector('.markdown-table').getAttribute('tabindex')).toBe('0')
    expect(root.querySelector('.markdown-table').getAttribute('role')).toBe('region')
    expect(root.querySelector('.katex-display')).not.toBeNull()
    expect(root.querySelector('math semantics annotation[encoding="application/x-tex"]')).not.toBeNull()
    // jsdom has no layout engine: actual narrow-screen dimensions remain manual QA.
  })

  it('uses inline markup inside options and updates on a source change', async () => {
    wrapper = mount(MarkdownRenderer, { props: { source: '**权重** $w_i$', inline: true } })
    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.find('p,div,h1,table').exists()).toBe(false)
    expect(wrapper.find('.katex').exists()).toBe(true)
    await wrapper.setProps({ source: '修改后的 `w`' })
    expect(wrapper.find('.katex').exists()).toBe(false)
    expect(wrapper.get('code').text()).toBe('w')
  })

  it('shows a readable fallback notice without inserting error markup', () => {
    wrapper = mount(MarkdownRenderer, { props: { source: '$\\invalidCommand{x}$' } })
    expect(wrapper.get('[role="status"]').text()).toContain('保留公式原文')
    expect(wrapper.find('.math-raw').exists()).toBe(true)
  })
})
