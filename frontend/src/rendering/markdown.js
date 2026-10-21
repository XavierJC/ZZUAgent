// Only this module produces HTML for MarkdownRenderer. Original text remains
// authoritative; formulas, code and links cannot execute actions or fetch files.
import MarkdownIt from 'markdown-it'
import { tex } from '@mdit/plugin-tex'
import { renderToString } from 'katex'
import createDOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import cpp from 'highlight.js/lib/languages/cpp'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'

for (const [name, grammar] of Object.entries({ python, cpp, javascript, json, bash })) {
  hljs.registerLanguage(name, grammar)
}
const aliases = { py: 'python', 'c++': 'cpp', js: 'javascript', sh: 'bash', shell: 'bash' }
export const RENDER_LIMITS = Object.freeze({ documentBytes: 65536, formulaChars: 2000, formulas: 128, codeChars: 8192 })
const escapeHtml = (text) => text.replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character])

export function isSafeLink(value) {
  if (typeof value !== 'string' || /[\s\u0000-\u001f\u007f]/u.test(value)) return false
  if (value.startsWith('#')) return true
  if (!/^https?:\/\//i.test(value)) return false
  try { return ['http:', 'https:'].includes(new URL(value).protocol) } catch { return false }
}

// An instance owned by this renderer avoids changing another component's hooks.
const purifier = createDOMPurify(window)
purifier.addHook('uponSanitizeAttribute', (node, attribute) => {
  if (['href', 'xlink:href'].includes(attribute.attrName)
      && (node.nodeName.toLowerCase() !== 'a' || !isSafeLink(attribute.attrValue))) {
    attribute.keepAttr = false
  }
})
const SANITIZE_OPTIONS = {
  // Keep default namespace/mXSS protection and the MathML/SVG needed by KaTeX.
  // Raw HTML is disabled at parsing; inline layout styles come only from KaTeX.
  FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed', 'form', 'input', 'button',
    'textarea', 'select', 'option', 'img', 'audio', 'video', 'source', 'link', 'meta',
    'base', 'template', 'foreignobject', 'annotation-xml'],
  FORBID_ATTR: ['id', 'name'], ALLOW_DATA_ATTR: false,
  ADD_ATTR: ['target', 'rel', 'referrerpolicy', 'encoding'],
  ADD_TAGS: ['semantics', 'annotation'],
}

export function renderMarkdown(source, { inline = false, citationIds = [] } = {}) {
  const text = typeof source === 'string' ? source : ''
  const notices = new Set()
  if (new TextEncoder().encode(text).length > RENDER_LIMITS.documentBytes) {
    return { html: purifier.sanitize(`<span class="markdown-raw">${escapeHtml(text)}</span>`, SANITIZE_OPTIONS),
      notices: ['内容较长，暂以纯文本显示，原文保持完整。'] }
  }
  const md = new MarkdownIt({ html: false, linkify: false, typographer: false, breaks: true,
    maxNesting: 20,
    highlight(code, language) {
      const name = aliases[language] || language
      if (code.length <= RENDER_LIMITS.codeChars && hljs.getLanguage(name)) {
        return hljs.highlight(code, { language: name, ignoreIllegals: true }).value
      }
      return escapeHtml(code)
    },
  })
  md.validateLink = isSafeLink
  const allowedCitations = new Set(citationIds.filter(id => typeof id === 'string' && /^[a-zA-Z0-9_-]+:\d+$/.test(id)))
  if (allowedCitations.size) {
    md.renderer.rules.text = (tokens, index) => escapeHtml(tokens[index].content).replace(/\[([a-zA-Z0-9_-]+:\d+)\]/g,
      (text, id) => allowedCitations.has(id) ? `<a href="#eduagent-citation/${encodeURIComponent(id)}" class="workbench-inline-citation" aria-label="查看引用 ${escapeHtml(id)}">${text}</a>` : text)
  }
  md.renderer.rules.image = (tokens, index) => escapeHtml(tokens[index].content || '图片')
  md.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
    const token = tokens[index]
    if (!token.attrGet('href').startsWith('#')) token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
    token.attrSet('referrerpolicy', 'no-referrer')
    return renderer.renderToken(tokens, index, options)
  }
  md.renderer.rules.table_open = () => '<div class="markdown-table" tabindex="0" role="region" aria-label="表格，可横向滚动"><table>\n'
  md.renderer.rules.table_close = () => '</table></div>\n'
  let formulas = 0
  const macros = {}
  // Use the maintained delimiter parser without the wrapper that logs parse
  // errors. Catch rendering errors here so private source never reaches logs.
  md.use(tex, { delimiters: 'dollars', mathFence: false,
    render(raw, displayMode) {
      const fallback = () => `<span class="math-raw">${escapeHtml(raw)}</span>`
      if (++formulas > RENDER_LIMITS.formulas || raw.length > RENDER_LIMITS.formulaChars) {
        notices.add('部分公式较长或数量较多，已保留公式原文。')
        return fallback()
      }
      try {
        const html = renderToString(raw, { displayMode, trust: false, throwOnError: true,
          maxExpand: 1000, maxSize: 20, output: 'htmlAndMathml', macros, strict: 'ignore' })
        return displayMode ? `<div class="katex-block">${html}</div>\n` : html
      } catch {
        notices.add('部分公式无法显示，已保留公式原文。')
        return fallback()
      }
    },
  })
  // A fresh parser/macro environment on every call prevents one note's \gdef
  // from altering another note. The final sanitizer always runs after plugins.
  const generated = inline ? md.renderInline(text) : md.render(text)
  return { html: purifier.sanitize(generated, SANITIZE_OPTIONS), notices: [...notices] }
}
