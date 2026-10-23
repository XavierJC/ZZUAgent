<script setup>
import { onMounted, ref, computed } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
const props=defineProps({workspace:Object,documents:Object,student:String})
const b=props.workspace,checked=ref({}),reviewer=ref('')
const concepts=computed(()=>b.catalog?.architectures.flatMap(a=>a.concepts.map(c=>({...c,architecture_id:a.architecture_id,version:a.version})))||[])
function concept(row){return concepts.value.find(c=>c.id===row.concept_id&&c.architecture_id===row.architecture_id)}
function pick(value){const c=concepts.value.find(c=>c.id===value);b.draft.architecture_id=c?.architecture_id||'';b.draft.concept_id=value}
function fromPage(){const d=props.documents.current,u=props.documents.units.find(u=>u.ordinal===Number(b.draft.ordinal));if(!d||!u)return;b.draft.document_id=d.id;b.draft.run_id=props.documents.run.id;b.draft.start_offset=0;b.draft.end_offset=u.content_md.length;b.draft.excerpt_md=u.content_md}
function image(row){return `/api/v1/students/${encodeURIComponent(props.student)}/documents/${row.document_id}/preview?version_id=${row.version_id}&page=${row.page_number}`}
onMounted(()=>b.load())
</script>
<template>
  <section class="panel phase5-builder" aria-label="课件片段与知识概念审核">
    <h2>试点课件片段与知识概念</h2><p>先在上方打开资料页面。片段与概念确认后才可检索，模型解释和未审核转录不自动成为课程原文。</p>
    <p v-if="b.error" role="alert" class="alert alert-error">{{ b.error }}</p><p v-if="b.notice" role="status">{{ b.notice }}</p>
    <button class="button secondary" @click="b.load()">只读刷新关联与回执</button><button v-if="b.pending" class="button secondary" @click="b.retry()">明确重试原编号</button>
    <details><summary>从当前打开的页面建立候选关联</summary>
      <form @submit.prevent="b.create()"><fieldset :disabled="Boolean(b.busy||b.pending)"><legend>新增候选，不自动确认</legend>
        <label>页面/单位编号<input v-model.number="b.draft.ordinal" type="number" min="1" max="200" /></label><button type="button" class="button secondary" @click="fromPage">读取当前打开资料的该页</button>
        <label>已确认知识概念<select :value="b.draft.concept_id" required @change="pick($event.target.value)"><option value="">请先在知识体系中确认并发布概念</option><option v-for="c in concepts" :key="c.id" :value="c.id">{{ c.name }} · 版本{{ c.version }}</option></select></label>
        <p class="small muted">来自当前文件和所选解析记录；校订转录须对照原页，不能粘贴模型拓展解释。</p><label>检索片段/待审核转录<textarea v-model="b.draft.excerpt_md" rows="6" maxlength="12000" required /></label><button class="button primary" :disabled="!b.draft.document_id">保存为待审核片段</button>
      </fieldset></form>
    </details>
    <label>本机审核说明<input v-model="reviewer" maxlength="120" placeholder="例如：负责人对照原PDF核对" /></label>
    <article v-for="row in b.items" :key="row.id" class="source-card"><h3>第{{ row.page_number }}页 · {{ concept(row)?.name || '知识概念尚未发布' }}</h3><p>{{ row.status==='confirmed'?'已明确确认':row.status==='candidate'?'待负责人审核':'已撤回' }} · {{ row.current?'来源当前有效':'尚未确认或来源/解析已变化' }}</p>
      <details><summary>对照原始页面和提取文本</summary><img :src="image(row)" :alt="`课件原PDF第${row.page_number}页`" loading="lazy" style="max-width:100%" /><pre class="wb-raw">{{ row.original_text }}</pre></details>
      <MarkdownRenderer :source="row.excerpt_md" /><p class="small muted">{{ row.excerpt_origin==='corrected_transcription'?'校订转录，须核对原图':'解析原文片段' }}；确认不等于整份课件已审阅，也不改变BKT。</p>
      <label><input v-model="checked[row.id]" type="checkbox" />我已核对原页、片段完整性及知识概念关联。</label>
      <button class="button primary" :disabled="Boolean(b.busy||b.pending||!checked[row.id]||!reviewer.trim()||!concept(row))" @click="b.review(row,concept(row).version,reviewer,true);checked[row.id]=false">确认此片段可检索</button>
      <button v-if="row.status==='confirmed'" class="button secondary" :disabled="Boolean(b.busy||b.pending)" @click="b.review(row,row.architecture_version,reviewer,false)">撤回检索确认</button>
    </article>
    <p v-if="!b.items.length">尚无页面关联；不会自动为所有课件页面创建知识节点。</p>
  </section>
</template>
