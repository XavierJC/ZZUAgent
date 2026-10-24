<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import '../documents.css'
const props = defineProps({ workspace: Object })
const deleting = ref(false), input = ref(null)
const names = { pending: '排队中', processing: '正在解析', ready: '文字提取完成', partial: '部分提取 · 需核对', empty: '未提取到有效文字',
  failed: '解析失败', superseded: '已被新版本取代', uncertain: '模型执行待确认' }
const warnings = { pdf_layout_and_math_unverified: 'PDF版面及复杂公式尚未核验', image_content_not_extracted: '包含未提取的图像内容',
  image_resource_inspection_incomplete: '图片资源结构复杂，未完成全部检查', possible_inline_image_not_extracted: '可能包含未提取的内联图像',
  possible_scan_or_image_content: '疑似扫描页或图片页', text_encoding_needs_review: '字符编码需要核对',
  pptx_reading_order_and_math_unverified: '幻灯片阅读顺序和公式需核对', equation_needs_review: '公式原始结构已保留，需人工核对',
  image_or_complex_object_not_extracted: '图片、图表或复杂对象未作视觉识别', hidden_slide_not_for_retrieval: '隐藏幻灯片，未用于检索',
  speaker_notes_not_extracted: '演讲者备注未提取', model_extraction_unverified: '模型提取结果，尚未核验', model_extraction_requires_review: '视觉识别结果需对照原件' }
const errors = { parse_timeout: '本地解析超时', parser_unavailable: '解析依赖或资源限制不可用', parse_resource_limit: '达到资源限额或进程异常退出',
  original_unavailable: '原件缺失或指纹变化', parse_failed: '本地解析失败', invalid_document: '文件损坏或格式不匹配', encrypted_document: '不支持加密文件',
  derived_unavailable: '派生文件缺失或损坏，请显式重新本地解析', parse_memory_limit: '达到解析内存限额',
  too_many_pages: '超过200页/幻灯片限制', unsafe_document: '文件含不支持的宏、嵌入对象或XML', archive_limits_exceeded: '文件解压资源超过限额',
  invalid_vision_output: '模型转录格式不完整，未覆盖本地提取', execution_unconfirmed: '无法确认模型是否执行，不自动重发', parse_interrupted: '解析中断，请显式重试' }
let timer, alive = true
onMounted(async () => {
  props.workspace.visible = true; await props.workspace.load()
  if (alive) timer = setInterval(() => { if (props.workspace.activeJobs) props.workspace.load() }, 2500)
})
onUnmounted(() => { alive = false; clearInterval(timer); props.workspace.visible = false })
async function upload() { if (await props.workspace.upload() && input.value) input.value.value = '' }
function choose(event) {
  props.workspace.file = event.target.files?.[0] || null
  if (props.workspace.file && !props.workspace.title) props.workspace.title = props.workspace.file.name.replace(/\.[^.]+$/, '').slice(0, 120)
}
</script>

<template>
  <section class="document-manager" aria-labelledby="documents-title">
    <header class="panel doc-header"><div><h2 id="documents-title">课程课件解析</h2><p class="small muted">原件与提取文本分别保存在本机。可读解析内容可直接问答；知识树和审核关联可在管理区进一步整理。</p></div><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.load()">刷新资料与任务</button></header>
    <p v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</p>
    <p v-if="workspace.notice" class="alert alert-info" role="status">{{ workspace.notice }}</p>
    <div v-if="workspace.pending" class="panel" role="status"><p>操作 {{ workspace.pending.request_id }} 待核对，刷新只查询回执。</p><button class="button secondary" @click="workspace.load()">查询原操作</button><button class="wb-text-button" @click="workspace.releasePending()">结束等待（新视觉请求可能再次计费）</button></div>
    <div class="doc-grid">
      <aside class="panel doc-list" aria-label="课件列表与上传">
        <h3>上传资料</h3>
        <form @submit.prevent="upload">
          <label for="doc-file">PDF / PPTX / Markdown / TXT / 图片</label><input id="doc-file" ref="input" type="file" accept=".pdf,.pptx,.md,.txt,.png,.jpg,.jpeg,.webp" @change="choose" />
          <p v-if="workspace.file" class="small">已选：{{ workspace.file.name }}</p>
          <label for="doc-title">资料标题</label><input id="doc-title" v-model="workspace.title" maxlength="120" required />
          <label for="doc-source">来源说明（可选）</label><textarea id="doc-source" v-model="workspace.sourceNote" maxlength="500" rows="2" />
          <label class="doc-check"><input v-model="workspace.rights" type="checkbox" />我确认有权在本机保存和处理这份资料。</label>
          <p class="small muted">PDF/PPTX/图片最多20MiB（图片≤1600万像素且单帧）、200页；MD/TXT最多2MiB且须UTF-8。上传不授权模型外发。</p>
          <button class="button primary" :disabled="Boolean(workspace.busy || workspace.pending || !workspace.file || !workspace.rights || !workspace.title.trim())">{{ workspace.busy === 'upload' ? '正在保存原件…' : '上传并本地解析' }}</button>
        </form>
        <h3>已保存资料</h3><p v-if="!workspace.items.length" class="small muted">尚无课件。资料按当前本机演示学习标识隔离，该标识不是账号认证。</p>
        <ul><li v-for="item in workspace.items" :key="item.id"><button class="doc-item" :aria-pressed="workspace.current?.id === item.id" :disabled="Boolean(workspace.busy)" @click="deleting = false; workspace.select(item.id)"><strong>{{ item.title }}</strong><small>{{ item.version.format.toUpperCase() }} · 文件v{{ item.version.file_revision }} · {{ names[item.parse.status] }}</small></button></li></ul>
      </aside>
      <section v-if="workspace.current" class="panel doc-detail" aria-label="资料解析详情">
        <h3>{{ workspace.current.title }}</h3><p class="small muted">导入资料 · 内容未核验 · 元数据r{{ workspace.current.revision }} · 文件v{{ workspace.current.version.file_revision }}</p>
        <div class="doc-actions"><a class="button secondary" :href="workspace.download">下载当前原件</a><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.retry()">重新本地解析</button></div>
        <div class="doc-metadata"><label for="doc-version">上传新版本（文件替换后重新解析）</label><input id="doc-version" type="file" accept=".pdf,.pptx,.md,.txt,.png,.jpg,.jpeg,.webp" :disabled="Boolean(workspace.busy || workspace.pending)" @change="workspace.updateVersion($event.target.files?.[0]); $event.target.value = ''" /></div>
        <form class="doc-metadata" @submit.prevent="workspace.saveMetadata()"><label for="doc-edit-title">修改标题</label><input id="doc-edit-title" v-model="workspace.editTitle" maxlength="120" required /><label for="doc-edit-source">修改来源说明</label><textarea id="doc-edit-source" v-model="workspace.editSource" maxlength="500" rows="2" /><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)">保存资料信息</button></form>
        <p role="status">本地解析：{{ names[workspace.current.parse.status] }} · {{ workspace.current.parse.unit_count }}个页面/文本单位</p>
        <p v-if="workspace.current.parse.error_code" class="wb-run-notice">{{ errors[workspace.current.parse.error_code] || '资料处理失败，请检查原件后显式重试。' }}</p>
        <details class="doc-vision"><summary>可选：DeepSeek PDF / 图片识别</summary><p class="small muted">仅发送本轮指定页的图片，可能包含该页全部文字和图像；服务为 {{ workspace.capabilities?.vision_provider }} / {{ workspace.capabilities?.vision_model }}。最多3页，每页最多{{ workspace.capabilities?.vision_max_output_tokens }}输出token，按量计费，失败不自动重发。本轮授权与聊天、笔记外发分开。</p>
          <p v-if="!workspace.capabilities?.vision_enabled" role="status">视觉解析通道尚未启用；真实调用预算与教师资料外发授权需另行确认。本地解析可继续使用。</p>
          <form @submit.prevent="workspace.vision()"><label for="doc-pages">PDF页码或图片编号1，例如1,2</label><input id="doc-pages" v-model="workspace.pages" placeholder="1,2" :disabled="!workspace.capabilities?.vision_enabled || !['pdf','png','jpg','jpeg','webp'].includes(workspace.current.version.format)" /><label class="doc-check"><input v-model="workspace.consent" type="checkbox" :disabled="!workspace.capabilities?.vision_enabled" />我有权外发，并同意本轮将上述PDF页或图片发送至DeepSeek。</label><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending || workspace.activeJobs || !workspace.consent || !workspace.capabilities?.vision_enabled || !['pdf','png','jpg','jpeg','webp'].includes(workspace.current.version.format))">发起本轮页面识别</button></form>
        </details>
        <label for="doc-run">查看已保存解析记录（不重新调用模型）</label><select id="doc-run" :value="workspace.run?.id" :disabled="Boolean(workspace.busy)" @change="workspace.selectRun($event.target.value)"><option v-for="job in workspace.runs" :key="job.id" :value="job.id">{{ job.mode === 'vision' ? 'DeepSeek页面识别' : '本地解析' }} · {{ names[job.status] }} · {{ job.created_at }}</option></select>
        <p v-if="workspace.run" class="small muted">{{ names[workspace.run.status] }} · 模型调用{{ workspace.run.model_calls }}次 · {{ workspace.run.parser_version }}</p>
        <p v-if="workspace.run?.current_status !== 'current'" class="wb-run-notice">这是旧版本解析记录，不代表当前资料。</p>
        <p v-if="workspace.run?.error_code" class="wb-run-notice" role="status">{{ errors[workspace.run.error_code] || '解析或模型服务未完成，请检查本轮状态；不会自动重发。' }}</p>
        <article v-for="item in workspace.units" :key="item.id" class="doc-unit"><h4>{{ item.title || '文本内容' }}</h4><p class="small muted">{{ item.location.page_number ? `PDF第${item.location.page_number}页` : item.location.slide_number ? `第${item.location.slide_number}张幻灯片` : `原文行${item.location.start_line}–${item.location.end_line}` }} · {{ item.origin === 'deepseek_vision' ? '模型转录 · 待核验' : '本地文本提取' }}</p>
          <ul v-if="item.warnings.length" class="doc-warnings"><li v-for="warning in item.warnings" :key="warning">{{ warnings[warning] || warning }}</li></ul>
          <MarkdownRenderer :source="item.content_md" /><section v-if="item.interpretation_md"><h5>模型图示解释（非原文转录）</h5><MarkdownRenderer :source="item.interpretation_md" /></section>
          <details><summary>查看提取原文、位置和公式原始结构</summary><pre>{{ item.text }}</pre><pre>{{ JSON.stringify({ location: item.location, blocks: item.blocks }, null, 2) }}</pre></details>
        </article>
        <div v-if="workspace.total > 10" class="doc-actions"><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.offset === 0)" @click="workspace.page(-1)">上一组</button><span>{{ workspace.offset + 1 }}–{{ Math.min(workspace.offset + 10, workspace.total) }} / {{ workspace.total }}</span><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.offset + 10 >= workspace.total)" @click="workspace.page(1)">下一组</button></div>
        <div class="doc-delete"><button v-if="!deleting" class="wb-text-button" @click="deleting = true">删除资料</button><template v-else><p>软删除后正常列表和原件入口不再可用；本机原件、历史版本和备份仍保留。</p><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.remove(); deleting = false">确认软删除</button><button class="wb-text-button" @click="deleting = false">取消</button></template></div>
      </section>
      <section v-else class="panel empty-state"><h3>选择一份资料查看解析结果</h3><p>保留原件、页码/幻灯片号和提取质量提示。</p></section>
    </div>
  </section>
</template>
