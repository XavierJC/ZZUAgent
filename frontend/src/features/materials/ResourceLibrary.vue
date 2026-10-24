<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
import './resource-library.css'
const DocumentManager = defineAsyncComponent(() => import('../../components/DocumentManager.vue'))
const props = defineProps({ workspace: Object, documents: Object })
const emit = defineEmits(['navigate', 'edit-note'])
const query = ref(''), uploadOpen = ref(false)
const types = { teaching_material: '教师课件', reference: '教材与参考资料', personal_note: '个人笔记', exercise_material: '习题资料' }
const parseNames = { ready: '可读解析已保存', partial: '部分提取，需核对', pending: '等待解析', processing: '正在解析', empty: '无可读正文', failed: '解析失败', uncertain: '结果待确认' }
const items = computed(() => props.workspace.resources.filter(r => r.status === 'active' && r.title.includes(query.value)))
const nodes = computed(() => props.workspace.knowledge.flatMap(group => [
  ...group.chapters.map(n => ({ ...n, kind: 'chapter', label: `${group.name} / ${n.title}`, architecture_id: group.architecture_id })),
  ...group.concepts.map(n => ({ ...n, kind: 'concept', label: `${group.name} / ${n.name}`, architecture_id: group.architecture_id })),
]))
function toggle(node, checked) {
  const editor = props.workspace.editor
  editor.links = editor.links.filter(l => !(l.architecture_id === node.architecture_id && l.node_id === node.id && l.kind === node.kind))
  if (checked) editor.links.push({ architecture_id: node.architecture_id, node_id: node.id, kind: node.kind, review_status: 'candidate' })
}
onMounted(() => props.workspace.load())
</script>
<template>
  <section class="resource-library" aria-label="课程资料目录">
    <header class="panel wb-section-heading"><h2>课程资料</h2><div class="phase5-actions"><button class="button secondary" :aria-expanded="uploadOpen" @click="uploadOpen=!uploadOpen; if(!uploadOpen)workspace.load()">{{uploadOpen?'收起解析管理并刷新目录':'上传文件 / 图片，查看解析与版本'}}</button><button class="button secondary" @click="workspace.load()">只读刷新</button></div></header>
    <DocumentManager v-if="uploadOpen && documents?.supported" :workspace="documents" />
    <p v-if="workspace.error" class="alert alert-error" role="alert">{{workspace.error}}</p><p v-if="workspace.notice" role="status">{{workspace.notice}}</p>
    <p v-if="workspace.busy==='save'" role="status">正在保存资料关联…</p><p v-else-if="workspace.pending" role="status">原保存待核对；刷新仅查询回执，不自动重新提交。</p>
    <section v-if="workspace.dirty && !workspace.pending" class="panel"><p>当前资料关联有未保存草稿，切换页面会保留在本机。</p><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.readServer()">保留草稿副本并读取最新资料</button></section>
    <details v-if="workspace.recoveries.length" class="panel"><summary>已保留的关联草稿副本</summary><p v-for="entry in workspace.recoveries" :key="entry.id">{{entry.title}}<button class="wb-text-button" :disabled="workspace.resource?.resource_id!==entry.resource_id || Boolean(workspace.busy || workspace.pending)" @click="workspace.restoreCopy(entry)">恢复到当前资料草稿</button></p></details>
    <div class="phase5-split">
      <aside class="panel"><label for="library-search">查找资料</label><input id="library-search" v-model="query" placeholder="输入资料名称" />
        <button v-for="item in items" :key="item.resource_id" class="pb-item" :aria-pressed="workspace.resource?.resource_id===item.resource_id" :disabled="Boolean(workspace.busy || workspace.dirty || workspace.pending)" @click="workspace.selectResource(item)"><strong>{{item.title}}</strong><small>{{types[item.resource_type]}} · {{item.format}} · {{parseNames[item.parse_status] || '解析状态待核对'}}</small></button>
        <p v-if="!items.length">暂无匹配资料，可以上传文件或查看我的笔记。</p>
      </aside>
      <section class="panel" style="min-width:0">
        <template v-if="workspace.resource"><h3>{{workspace.resource.title}}</h3>
          <div class="phase5-actions"><button class="button secondary" @click="emit('navigate','practice',{resource:workspace.resource.resource_id})">查看相关练习</button><button v-if="workspace.resource.original_source_type==='document'" class="button secondary" @click="emit('navigate','practice',{resource:workspace.resource.resource_id,import:'1'})">提取这份资料的习题</button><button class="button secondary" @click="emit('navigate','study')">到学习页选择资料提问</button><button v-if="workspace.resource.original_source_type==='personal_note'" class="button secondary" @click="emit('edit-note',workspace.resource.original_source_id)">打开笔记编辑器</button></div>
          <a v-if="workspace.resource.original_source_type==='document'" :href="`/api/v1/students/${encodeURIComponent(workspace.owner)}/documents/${encodeURIComponent(workspace.resource.original_source_id)}/original?version_id=${encodeURIComponent(workspace.resource.source_version)}`">查看同一版本原件</a>
          <details v-if="workspace.editor"><summary>资源用途与知识关联{{workspace.dirty?' · 有未保存草稿':''}}</summary><label for="library-type">资源用途</label><select id="library-type" v-model="workspace.editor.resource_type"><option v-for="(label,key) in types" :key="key" :value="key">{{label}}</option></select><fieldset><legend>已发布章节与概念；新增关联默认为候选</legend><label v-for="node in nodes" :key="`${node.architecture_id}:${node.kind}:${node.id}`" class="pb-check"><input type="checkbox" :checked="workspace.editor.links.some(l=>l.architecture_id===node.architecture_id && l.node_id===node.id && l.kind===node.kind)" @change="toggle(node,$event.target.checked)" />{{node.label}}</label></fieldset><ul><li v-for="link in workspace.editor.links" :key="`${link.architecture_id}:${link.kind}:${link.node_id}`">{{link.kind}} · {{link.node_id}}<label>关联状态<select v-model="link.review_status"><option value="candidate">候选</option><option value="confirmed">我已核对并确认</option></select></label></li></ul><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending || !workspace.dirty)" @click="workspace.saveLinks()">保存资源关联</button><p v-if="workspace.dirty" class="small">草稿保留在本机；保存后再选择其他资料。</p></details>
          <article v-for="unit in workspace.sourceUnits" :key="unit.id"><p class="small muted">{{unit.location?.page_number?'第'+unit.location.page_number+'页':unit.location?.slide_number?'幻灯片'+unit.location.slide_number:'原文片段'}}</p><MarkdownRenderer v-if="unit.text?.trim()" :source="unit.text" /><p v-else class="small muted">本页没有可读文本，请查看原件或解析管理；未识别内容不能参与检索。</p><p v-if="unit.warnings?.length" class="small muted">解析提示：{{unit.warnings.join('；')}}</p></article><p v-if="!workspace.sourceUnits.length">暂无可读解析，请查看原件和解析状态。</p>
        </template><p v-else>选择资料查看原文。提取习题进入练习区，问答在学习区完成。</p>
      </section>
    </div>
  </section>
</template>
