<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import '../architecture.css'
const props = defineProps({ workspace: { type: Object, required: true } })
const emit = defineEmits(['navigate'])
const name = ref(''), expanded = ref(new Set()), relation = ref({ id: null, source_id: '', target_id: '', kind: 'related_to', description: '' })
const w = computed(() => props.workspace)
const editable = computed(() => w.value.mode === 'draft' && w.value.current?.draft.status === 'editing')
const disabled = computed(() => Boolean(w.value.busy || w.value.pending || !editable.value))
const filteredConcepts = computed(() => (w.value.graph?.concepts || []).filter(c => (c.name + c.summary).toLowerCase().includes(w.value.search.toLowerCase())))
const rows = computed(() => {
  const chapters = w.value.graph?.chapters || [], output = [], query = w.value.search.toLowerCase()
  function walk(parent, depth) {
    for (const c of chapters.filter(c => c.parent_id === parent).sort((a,b) => a.order-b.order || a.id.localeCompare(b.id))) {
      if (!query || c.title.toLowerCase().includes(query)) output.push({ ...c, depth, children: chapters.some(x => x.parent_id === c.id) })
      if (query || expanded.value.has(c.id)) walk(c.id, depth+1)
    }
  }
  walk(null, 0); return output
})
const relationNames = { contains: '包含（整体 → 组成）', related_to: '相关（双向）', prerequisite_candidate: '候选先修（先修 → 后续，未确认）' }
const sourceNames = { current: '当前', modified: '文件已更新', metadata_modified: '资料信息已修改', reparsed: '已重新解析', unavailable: '解析不可用', deleted: '资料已删除（快照仍保留）' }
const selectedOrigins = computed(() => (w.value.node?.origins || []).map(ref => w.value.sources.find(s => s.batch_id === ref.batch_id && s.item_id === ref.item_id)).filter(Boolean))
function toggle(id) { const next = new Set(expanded.value); next.has(id) ? next.delete(id) : next.add(id); expanded.value = next }
function newRelation() { relation.value = { id: null, source_id: w.value.selected?.kind === 'concept' ? w.value.selected.id : '', target_id: '', kind: 'related_to', description: '' } }
function saveRelation() {
  if (!relation.value.source_id || !relation.value.target_id) return
  const value = { ...relation.value, id: relation.value.id || crypto.randomUUID() }
  const index = w.value.draft.relations.findIndex(r => r.id === value.id)
  if (index < 0) w.value.draft.relations.push(value); else w.value.draft.relations[index] = value
  newRelation()
}
function eraseOrigin(index) {
  w.value.node.origins.splice(index, 1)
  w.value.notice = '已解除该来源关联，保留内容转为人工编辑内容；历史来源快照仍保留，发布前需自行核对。'
}
onMounted(() => { w.value.visible = true; w.value.load() })
onUnmounted(() => { w.value.persist(); w.value.visible = false })
</script>

<template>
  <section class="knowledge-architecture" aria-labelledby="architecture-title">
    <header class="panel ka-header"><div><h2 id="architecture-title">课程知识体系</h2><p class="small muted">章节与概念独立。仅明确发布的版本进入正式导航；新概念不自动获得BKT、题库或自评。</p></div><button class="button secondary" :disabled="Boolean(w.busy)" @click="w.load()">刷新结构与版本</button></header>
    <p v-if="w.error" class="alert alert-error" role="alert">{{ w.error }}</p><p v-if="w.notice" class="alert alert-info" role="status">{{ w.notice }}</p>
    <div v-if="w.guard" class="panel ka-guard" role="alert" aria-label="未保存知识结构"><p>当前有未保存修改。</p><button class="button secondary" @click="w.resolveGuard('keep')">保留本机草稿并继续</button><button class="button secondary" @click="w.resolveGuard('discard')">放弃本机修改并继续</button><button class="button secondary" @click="w.resolveGuard('cancel')">取消切换</button></div>
    <div v-if="w.pending" class="panel" role="status"><p>原操作待确认，刷新只查询回执，不自动重发。</p><button class="button secondary" @click="w.load()">查询原回执</button><button class="wb-text-button" @click="w.releasePending()">结束等待</button></div>
    <div v-if="w.conflict" class="panel"><p>服务器版本或候选来源发生变化，本机修改已保留，不能覆盖新版本。</p><button class="button secondary" @click="w.acceptServer()">保留恢复副本并读取服务器版本</button></div>
    <div class="ka-grid">
      <aside class="panel ka-nav" aria-label="知识结构导航">
        <form @submit.prevent="w.create(name)"><label for="ka-new-name">新体系名称</label><input id="ka-new-name" v-model="name" maxlength="120" required /><button class="button secondary" :disabled="Boolean(w.busy || w.pending)">新建课程知识体系</button></form>
        <h3>我的知识体系</h3><ul class="ka-list"><li v-for="item in w.items" :key="item.id"><button :aria-pressed="w.current?.id === item.id" :disabled="Boolean(w.busy)" @click="w.select(item.id)">{{ item.title }}<small>{{ item.published_version ? `已发布v${item.published_version}` : '未发布' }} · {{ item.draft_status === 'editing' ? '有草稿' : '已锁定' }}</small></button></li></ul>
        <template v-if="w.current"><div class="doc-actions"><button class="button secondary" :aria-pressed="w.mode === 'published'" :disabled="!w.published" @click="w.mode = 'published'; w.selected = null; w.learning = null">正式导航</button><button class="button secondary" :aria-pressed="w.mode === 'draft'" @click="w.mode = 'draft'; w.selected = null; w.learning = null">草稿编辑</button></div>
          <p role="status">{{ w.mode === 'published' ? `已确认v${w.published?.version}` : w.current.draft.status === 'locked' ? '发布快照已锁定，请另开草稿' : '草稿 · 未正式发布' }}</p>
          <label for="ka-search">搜索章节与概念</label><input id="ka-search" v-model="w.search" type="search" />
          <h3>章节树</h3><p v-if="!w.graph?.chapters.length" class="small muted">暂无章节；未发布候选不会出现在正式导航。</p>
          <ul class="ka-tree"><li v-for="row in rows" :key="row.id" :style="{ paddingInlineStart: `${row.depth * 14}px` }"><button v-if="row.children" class="ka-expand" :aria-expanded="expanded.has(row.id)" :aria-label="`${expanded.has(row.id) ? '折叠' : '展开'}${row.title}`" @click="toggle(row.id)" @keydown.right.prevent="expanded = new Set([...expanded, row.id])" @keydown.left.prevent="expanded = new Set([...expanded].filter(id => id !== row.id))">{{ expanded.has(row.id) ? '−' : '+' }}</button><button class="ka-node" :aria-pressed="w.selected?.id === row.id" @click="w.selectNode('chapter', row.id)">{{ row.title }}</button></li></ul>
          <h3>知识概念</h3><ul class="ka-list"><li v-for="concept in filteredConcepts" :key="concept.id"><button :aria-pressed="w.selected?.id === concept.id" @click="w.selectNode('concept', concept.id)">{{ concept.name }}<small>{{ concept.chapter_ids.length }}个所属章节 · {{ concept.review_status === 'confirmed' ? '已审阅' : '候选待审' }}</small></button></li></ul>
        </template>
      </aside>
      <section class="panel ka-detail" aria-label="结构与概念详情">
        <template v-if="w.current">
          <button v-if="editable && w.recoveries.some(r => r.architecture_id === w.current.id)" class="button secondary" :disabled="Boolean(w.busy)" @click="w.restoreRecovery()">恢复最近的本机冲突副本（不会自动保存）</button><h3>{{ w.graph?.name }}</h3><p class="small muted">独立结构revision {{ w.current.revision }} · {{ w.dirty ? '本机修改未保存' : '已保存' }}</p>
          <div class="doc-actions"><label for="ka-version">已发布版本</label><select id="ka-version" :value="w.published?.version || ''" :disabled="Boolean(w.busy)" @change="w.version($event.target.value)"><option value="" disabled>尚未发布</option><option v-for="v in w.current.versions" :key="v.version" :value="v.version">v{{ v.version }} · {{ v.published_at }}</option></select><button v-if="w.current.draft.status === 'locked'" class="button secondary" :disabled="Boolean(w.busy || w.pending)" @click="w.fork()">基于所示版本另开草稿</button></div>
          <fieldset v-if="w.mode === 'draft'" :disabled="disabled"><legend>体系与节点编辑</legend>
            <label for="ka-name">体系名称</label><input id="ka-name" v-model="w.draft.name" maxlength="120" /><label for="ka-description">体系简介</label><textarea id="ka-description" v-model="w.draft.description" maxlength="2000" rows="2" />
            <div class="doc-actions"><button type="button" class="button secondary" @click="w.addNode('chapter')">增加章节/小节</button><button type="button" class="button secondary" @click="w.addNode('concept')">增加独立概念</button></div>
          </fieldset>
          <MarkdownRenderer v-else :source="w.graph?.description || ''" />
          <template v-if="w.node"><h3>{{ w.selected.kind === 'chapter' ? '章节详情' : '概念详情' }}</h3><p class="small muted">稳定ID {{ w.node.id }}</p>
            <fieldset v-if="w.mode === 'draft'" :disabled="disabled"><legend>修改当前节点</legend>
              <label for="ka-node-name">名称</label><input v-if="w.selected.kind === 'chapter'" id="ka-node-name" v-model="w.node.title" maxlength="120" /><input v-else id="ka-node-name" v-model="w.node.name" maxlength="120" />
              <label for="ka-summary">简介（Markdown）</label><textarea id="ka-summary" v-model="w.node.summary" maxlength="2000" rows="4" />
              <template v-if="w.selected.kind === 'chapter'"><label for="ka-parent">父章节</label><select id="ka-parent" v-model="w.node.parent_id"><option :value="null">顶层章节</option><option v-for="chapter in w.draft.chapters.filter(c => c.id !== w.node.id)" :key="chapter.id" :value="chapter.id">{{ chapter.title }}</option></select><label for="ka-order">同级顺序（较小在前）</label><input id="ka-order" v-model.number="w.node.order" type="number" min="0" max="10000" /></template>
              <template v-else><fieldset><legend>所属章节（可多选）</legend><label v-for="chapter in w.draft.chapters" :key="chapter.id" class="ka-check"><input v-model="w.node.chapter_ids" type="checkbox" :value="chapter.id" />{{ chapter.title }}</label></fieldset><fieldset><legend>正式知识点只读关联</legend><label v-for="point in w.formal" :key="point.id" class="ka-check"><input v-model="w.node.formal_knowledge_ids" type="checkbox" :value="point.id" />{{ point.name }}</label><p class="small muted">仅展示已有测评状态；不会为新概念创建掌握概率或题目。</p></fieldset></template>
              <button type="button" class="wb-text-button" @click="w.removeNode()">删除当前节点（有引用时拒绝）</button>
            </fieldset>
            <template v-else><h4>{{ w.node.title || w.node.name }}</h4><MarkdownRenderer :source="w.node.summary" /><p v-if="w.selected.kind === 'concept'">所属章节：{{ w.graph.chapters.filter(c => w.node.chapter_ids.includes(c.id)).map(c => c.title).join('、') || '未归入章节' }}</p></template>
            <details v-for="(source, index) in selectedOrigins" :key="`${source.batch_id}:${source.item_id}`" class="ka-evidence"><summary>{{ source.source_title }} · {{ source.location.page_number ? `第${source.location.page_number}页` : source.location.slide_number ? `第${source.location.slide_number}张` : '文本位置' }} · {{ sourceNames[source.current_status] }}</summary><p class="small muted">{{ source.method }} · 文件v{{ source.file_revision }} · 解析{{ source.parser_version }}</p><a v-if="source.current_status !== 'deleted'" :href="w.sourceDownload(source)">下载此来源版本原件</a><pre>{{ source.raw_text }}</pre><p class="small muted">字符{{ source.start_offset }}–{{ source.end_offset }}，原文快照；软删除不会物理清除快照。</p><button v-if="editable" type="button" class="wb-text-button" :disabled="Boolean(w.busy || w.pending)" @click="eraseOrigin(index)">解除来源，转为人工编辑内容</button></details>
          </template>
          <h3>概念关系</h3><p class="small muted">contains是概念包含，不是章节归属；所有候选先修均未确认，不改变正式教学先修图。</p>
          <ul class="ka-relations"><li v-for="r in w.graph?.relations" :key="r.id"><strong>{{ w.graph.concepts.find(c => c.id === r.source_id)?.name }}</strong> {{ r.kind === 'related_to' ? '↔' : '→' }} <strong>{{ w.graph.concepts.find(c => c.id === r.target_id)?.name }}</strong><p>{{ relationNames[r.kind] }} {{ r.description }}</p><template v-if="editable"><button class="wb-text-button" :disabled="Boolean(w.busy || w.pending)" @click="relation = { ...r }">编辑关系</button><button class="wb-text-button" :disabled="Boolean(w.busy || w.pending)" @click="w.draft.relations = w.draft.relations.filter(x => x.id !== r.id)">删除关系</button></template></li></ul>
          <form v-if="editable" @submit.prevent="saveRelation"><fieldset :disabled="disabled"><legend>增加/编辑概念关系</legend><label for="ka-rel-source">起点概念</label><select id="ka-rel-source" v-model="relation.source_id" required><option value="" disabled>请选择</option><option v-for="c in w.draft.concepts" :key="c.id" :value="c.id">{{ c.name }} · {{ c.id.slice(0,6) }}</option></select><label for="ka-rel-target">终点概念</label><select id="ka-rel-target" v-model="relation.target_id" required><option value="" disabled>请选择</option><option v-for="c in w.draft.concepts" :key="c.id" :value="c.id">{{ c.name }} · {{ c.id.slice(0,6) }}</option></select><label for="ka-rel-type">关系类型</label><select id="ka-rel-type" v-model="relation.kind"><option v-for="(label, type) in relationNames" :key="type" :value="type">{{ label }}</option></select><label for="ka-rel-note">关系说明</label><input id="ka-rel-note" v-model="relation.description" maxlength="500" /><button class="button secondary">{{ relation.id ? '更新关系到草稿' : '增加关系到草稿' }}</button><button type="button" class="wb-text-button" @click="newRelation">重置关系表单</button></fieldset></form>
          <section v-if="editable" class="ka-publish"><button class="button primary" :disabled="Boolean(w.busy || w.pending || w.conflict || !w.dirty)" @click="w.save()">保存草稿</button><label class="ka-check"><input v-model="w.publishConsent" type="checkbox" :disabled="Boolean(w.dirty || w.busy)" />我已审阅已保存草稿的全部章节、概念和关联，确认发布；候选先修仍未确认。</label><button class="button secondary" :disabled="Boolean(w.busy || w.pending || w.dirty || w.conflict || !w.publishConsent)" @click="w.publish()">确认并发布新版本</button></section>
        </template><p v-else class="muted">创建或选择一个课程知识体系。不同体系和同名概念不会自动合并。</p>
      </section>
      <aside class="panel ka-state" aria-label="已有正式学习状态与候选提取">
        <h3>已有学习状态</h3><p class="small muted">下面展示关联正式知识点的状态，不是对当前新概念的独立测量。</p>
        <template v-if="w.learning"><p v-if="!w.learning.items.length">未关联正式知识点，没有本概念的BKT/自评数据。</p><article v-for="p in w.learning.items" :key="p.knowledge_id"><h4>{{ p.name }}</h4><p>{{ p.status === 'pending_diagnosis' ? '待诊断（无客观答题证据）' : `BKT掌握概率 ${(p.objective.probability * 100).toFixed(1)}%` }}</p><p>正式作答{{ p.objective.attempts }}次{{ p.objective.attempts ? `，最近${p.objective.last_correct ? '答对' : '答错'}` : '' }}</p><p>自评：{{ p.self_report ? `等级${p.self_report.level}，信心${p.self_report.confidence ?? '未填'}` : '未填写' }}</p><p v-if="p.self_report" class="small muted">自评时间 {{ p.self_report.created_at }}</p></article><p class="small muted">答题版本{{ w.learning.learning_revision }} · 自评版本{{ w.learning.assessment_revision }}</p></template><p v-else class="muted">选择并保存概念后，可读取已有正式学情。</p>
        <button v-if="w.selected?.kind === 'concept'" class="button secondary" :disabled="Boolean(w.busy || (w.mode === 'draft' && w.dirty))" @click="w.readState()">读取已保存关联的学情</button><div class="doc-actions"><button class="wb-text-button" @click="emit('navigate','learn')">正式练习入口</button><button class="wb-text-button" @click="emit('navigate','history')">已有学习历史</button></div>
        <template v-if="w.current"><h3>从已解析课件生成候选</h3><p class="small muted">本地规则提取，不调用模型。仅明确标题/术语生成候选，不推断先修关系。最多3份资料。</p><fieldset :disabled="Boolean(w.busy || w.pending)"><legend>选择当前本地解析资料</legend><label v-for="d in w.documents" :key="d.id" class="ka-check"><input v-model="w.chosenDocuments" type="checkbox" :value="d.id" :disabled="!['ready','partial','empty'].includes(d.parse.status)" />{{ d.title }} · 文件v{{ d.version.file_revision }}</label><button class="button secondary" :disabled="!w.chosenDocuments.length || w.chosenDocuments.length > 3" @click="w.candidates()">生成候选预览</button></fieldset>
          <section v-if="w.preview" class="ka-preview"><h4>候选预览（尚未导入）</h4><p class="small muted">名称可修改。未选中的所属章节/父节点关联会移除，之后可手动关联。</p><label v-for="c in [...w.preview.graph.chapters, ...w.preview.graph.concepts]" :key="c.id" class="ka-candidate"><input v-model="w.chosenCandidates" type="checkbox" :value="c.id" :aria-label="`导入候选${c.title || c.name}`" /><span>{{ 'title' in c ? '章节' : '概念' }}</span><input v-if="'title' in c" v-model="c.title" :aria-label="`候选章节名称${c.id.slice(0,6)}`" maxlength="120" /><input v-else v-model="c.name" :aria-label="`候选概念名称${c.id.slice(0,6)}`" maxlength="120" /></label><details><summary>查看候选提取依据与未分类位置</summary><article v-for="e in w.preview.evidence" :key="e.item_id"><p>{{ e.source_title }} · {{ sourceNames[e.current_status] }} · {{ e.method }}</p><pre>{{ e.raw_text }}</pre><p class="small muted">{{ JSON.stringify(e.location) }}</p></article><p>未分类单位 {{ w.preview.unclassified.length }} 个；保留原资料，不强行关联。</p></details><button class="button secondary" :disabled="Boolean(w.busy || w.pending || !editable || !w.chosenCandidates.length)" @click="w.importCandidates()">将选中候选加入本机草稿</button></section>
        </template>
      </aside>
    </div>
  </section>
</template>
