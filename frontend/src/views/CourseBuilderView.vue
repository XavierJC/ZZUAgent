<script setup>
import { onMounted } from 'vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
const props=defineProps({workspace:Object,overview:Boolean})
defineEmits(['navigate'])
const b=props.workspace
onMounted(()=>b.load())
function toggleSource(s,checked,type=s.source_type,id=s.source_id,version=s.source_version){
  b.editor.sources=b.editor.sources.filter(r=>!(r.source_type===type && r.source_id===id))
  if(checked)b.editor.sources.push({source_type:type,source_id:id,source_version:version})
}
function architecture(id){const g=b.catalog.architectures.find(a=>a.architecture_id===id);b.editor.architecture_id=g?.architecture_id || null;b.editor.architecture_version=g?.version || null}
</script>
<template>
  <section class="phase5-builder" aria-label="课程内容构建">
    <p class="alert alert-info">这是本机内容维护工作区。与学生端共享数据，不是教师账号或真实权限隔离；切换工作区不改变学习事实。</p>
    <p v-if="b.error" class="alert alert-error" role="alert">{{ b.error }}</p><p v-if="b.notice" role="status">{{ b.notice }}</p>
    <section v-if="b.pending" class="panel"><p>原保存或发布操作待核对；刷新不会自动重发。</p><button class="button secondary" @click="b.load()">只读查询回执</button><button class="button secondary" @click="b.retryPending()">明确重试原编号</button></section>
    <template v-if="overview">
      <section class="panel"><h2>准备课程内容，再发布可追溯版本</h2><p>资料上传 → 知识体系确认 → 原题审核 → 课程审核与发布。后台编辑不会静默改变已发布版本。</p><div class="phase5-actions"><button class="button secondary" @click="$emit('navigate','materials')">管理课程资料</button><button class="button secondary" @click="$emit('navigate','architecture')">编辑知识体系</button><button class="button secondary" @click="$emit('navigate','bank')">提取和审核习题</button><button class="button primary" @click="$emit('navigate','publish')">审核与发布课程</button></div></section>
      <section v-if="b.catalog" class="panel"><h3>当前内容范围</h3><p>运行题库 {{ b.catalog.formal_questions.length }}题；候选池 {{ b.catalog.candidate_count }}题，其中已包含原运行题{{ b.catalog.shared_formal_count }}题，额外候选{{ b.catalog.additional_candidate_count }}题。不会自动启用候选或个人题。</p><p>已确认知识体系 {{ b.catalog.architectures.length }}份；课件 {{ b.catalog.documents.length }}份。教师课件尚未全面接入RAG。</p></section>
    </template>
    <template v-else>
      <header class="panel phase5-actions"><h2>课程草稿、审核与发布</h2><button class="button secondary" :disabled="Boolean(b.busy || b.pending)" @click="b.fresh()">新建课程草稿</button><button class="button secondary" @click="b.load()">只读刷新</button></header>
      <div class="phase5-split">
        <aside class="panel"><h3>草稿</h3><button v-for="d in b.catalog?.drafts || []" :key="d.id" class="pb-item" :aria-pressed="b.current===d.id" @click="b.open(d.id)">{{ d.payload.title }} · 修订{{ d.revision }}</button><p v-if="!b.catalog?.drafts.length">尚无构建草稿，预置演示课程仍可直接学习。</p></aside>
        <form v-if="b.editor" class="panel pb-form" @submit.prevent="b.save()">
          <p role="status">{{ b.dirty ? '有本机未保存修改' : '已与服务器同步' }}</p><p v-if="b.conflict" class="alert alert-error">服务器草稿已有新版本，本机内容保留。</p><button v-if="b.conflict" type="button" class="button secondary" @click="b.reloadServer()">保留冲突副本并读取服务器版本</button>
          <button v-for="id in b.recoveries || []" :key="id" type="button" class="button secondary" @click="b.restoreCopy(id)">恢复本机构建草稿副本 {{ id.slice(-8) }}</button>
          <fieldset :disabled="Boolean(b.busy || b.pending)"><legend>课程草稿（不改变正式题库、BKT配置）</legend><label for="release-title">课程标题</label><input id="release-title" v-model="b.editor.title" maxlength="120" required />
            <label for="release-architecture">已确认知识体系</label><select id="release-architecture" :value="b.editor.architecture_id || ''" @change="architecture($event.target.value)"><option value="">未选择（仅可发布演示版）</option><option v-for="g in b.catalog?.architectures || []" :key="g.architecture_id" :value="g.architecture_id">{{ g.name }} · 发布版本{{ g.version }}</option></select>
            <fieldset><legend>明确选择参与发布的课程资料</legend><label v-for="s in b.catalog?.course_sources || []" :key="s.source_id" class="pb-check"><input type="checkbox" :checked="b.editor.sources.some(r=>r.source_type===s.source_type && r.source_id===s.source_id)" @change="toggleSource(s,$event.target.checked)" />{{ s.title }} · 本地课程检索</label><label v-for="s in b.catalog?.documents || []" :key="s.resource_id" class="pb-check"><input type="checkbox" :disabled="!['ready','partial','empty'].includes(s.parse_status)" :checked="b.editor.sources.some(r=>r.source_type==='teaching_material' && r.source_id===s.resource_id)" @change="toggleSource(s,$event.target.checked,'teaching_material',s.resource_id,s.source_version)" />{{ s.title }} · 课件引用 · 尚无RAG</label></fieldset>
            <label for="release-reviewer">本机内容审核人说明（不是账号认证）</label><input id="release-reviewer" v-model="b.editor.reviewer" maxlength="120" />
            <details><summary>逐题审核原运行题（{{ b.editor.reviewed_question_ids.length }}/{{ b.catalog?.formal_questions.length }}）</summary><article v-for="q in b.catalog?.formal_questions || []" :key="q.id" class="source-card"><h4>{{ q.knowledge_id }} · {{ q.id }}</h4><MarkdownRenderer :source="q.stem" /><div v-for="(text,key) in q.options" :key="key"><strong>{{ key }}</strong><MarkdownRenderer :source="text" /></div><p>运行标准答案：{{ q.answer }}</p><MarkdownRenderer :source="q.explanation" /><p class="small muted">{{ q.source }}</p><label class="pb-check"><input v-model="b.editor.reviewed_question_ids" type="checkbox" :value="q.id" />我已核对这道题的题干、选项、答案及解析；此确认不等于BKT参数统计标定。</label></article></details>
            <button class="button primary" :disabled="b.conflict">保存草稿</button>
          </fieldset>
          <div class="phase5-actions"><button type="button" class="button secondary" :disabled="Boolean(b.dirty || !b.current || b.pending)" @click="b.review()">重新检查发布条件</button></div>
          <section v-if="b.check" aria-live="polite"><h3>发布检查</h3><ul><li v-for="reason in b.check.formal_blockers" :key="reason">{{ reason }}</li></ul><p>{{ b.check.formal_allowed ? '内容审核条件已满足，仍需明确发布。' : '尚不能发布为已审核课程，可明确发布演示版。' }}</p><p>原{{ b.check.question_count }}题；教师课件仅定位引用，不宣称已接入检索。BKT参数未统计标定。</p><label for="release-kind">发布类型</label><select id="release-kind" v-model="b.kind"><option value="demo">工程演示版 · 未完成全部审核</option><option value="reviewed" :disabled="!b.check.formal_allowed">已审核课程版本</option></select><label class="pb-check"><input v-model="b.confirmed" type="checkbox" />确认发布当前检查的不可变内容快照，保留旧版本和原学习事实。</label><button type="button" class="button primary" :disabled="Boolean(b.dirty || b.pending || b.busy || !b.confirmed || b.conflict)" @click="b.publish()">明确发布此版本</button></section>
        </form><section v-else class="panel"><p>选择或新建课程草稿；学生端可直接使用明确标注的预置演示课程。</p></section>
      </div>
    </template>
    <section v-if="b.catalog" class="panel"><h3>已发布版本（不可变）</h3><article v-for="r in b.catalog.releases" :key="r.id" class="source-card"><h4>{{ r.title }} · 版本{{ r.release_version }} · {{ r.kind==='demo'?'工程演示':'已审核内容' }}</h4><p>{{ r.review_warning }}</p><p>{{ r.usable ? '当前引用有效' : '来源/配置已变化，历史快照仍保留' }}</p><ul><li v-for="s in r.source_statuses" :key="s.source_id">{{ s.title }} · {{ s.current_status }} · {{ s.rag_available?'已有检索':'仅来源定位' }}</li></ul><details><summary>发布指纹和版本引用</summary><p>{{ r.id }} · {{ r.content_hash }} · {{ r.published_at }}</p><p>知识体系：{{ r.architecture ? 'v'+r.architecture.version : '演示版未绑定' }}</p><p>正式题目：{{ r.question_versions.map(q=>q.id+'@'+q.version).join('、') }}</p></details></article></section>
  </section>
</template>
