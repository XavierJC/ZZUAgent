<script setup>
import { ref } from 'vue'
import Icon from '../../components/Icon.vue'
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
const props = defineProps({ workspace: Object })
const query = ref(''), searched = ref(false)
async function search() { searched.value = true; await props.workspace.search(query.value) }
</script>
<template>
  <section class="panel materials-panel">
    <div class="panel-heading"><div><p class="eyebrow">COURSE NOTES</p><h2>从课程资料中寻找依据</h2></div><span class="badge">5 个知识点</span></div>
    <form class="search-form" @submit.prevent="search"><label class="sr-only" for="material-query">检索课程资料</label><input id="material-query" v-model="query" maxlength="1000" required placeholder="例如：为什么学习率过大会发散？" /><button class="button primary" :disabled="Boolean(workspace.searchBusy || !workspace.health?.retrieval_available)">{{ workspace.searchBusy ? '正在检索…' : '检索资料' }}<Icon name="arrow" :size="17" /></button></form>
    <p class="small muted">从本地课程说明中检索，不调用模型生成。资料待审阅，关联仍需核对。</p>
    <div v-if="workspace.sources.length" class="source-list"><article v-for="source in workspace.sources" :key="source.citation_id" class="source-card"><div><span class="badge badge-blue">{{source.title}}</span><span class="small muted">[{{source.citation_id}}]</span></div><h3>{{source.section}}</h3><MarkdownRenderer :source="source.content" /><small class="muted">{{source.source}} · {{source.review_status==='pending'?'待内容审阅':'已审阅'}}</small></article></div>
    <div v-else class="empty-state"><Icon name="book" :size="36" /><h3>{{searched?'没有找到足够相关的课程片段。':'先从一个具体问题开始。'}}</h3><p>{{searched?'试试课程中的术语，或换一种表述。':'目前覆盖线性回归、梯度下降、逻辑回归、正则化与模型评估。'}}</p></div>
  </section>
</template>
