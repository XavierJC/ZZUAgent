<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Icon from '../../components/Icon.vue'
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
import QuestionImportPanel from '../../components/QuestionImportPanel.vue'
import ExerciseCard from './ExerciseCard.vue'
import PracticeFeedback from './PracticeFeedback.vue'
import PageHeader from '../../shared/PageHeader.vue'
import LearningProgress from '../../shared/LearningProgress.vue'
import { questionTypes } from '../questions/types.js'
import { practiceCandidates, topicQuestion } from '../learning/journey.js'
import './practice-desk.css'
const props = defineProps({ workspace: Object, documents: Object, notebook: Object, points: {type:Array,default:()=>[]}, context: {type:Object,default:()=>({})} })
const emit = defineEmits(['navigate', 'add-questions'])
const w = props.workspace
if (!w.desk) w.desk = reactive({ query:'', kind:'', category:'all', focus:false, importOpen:false, resource:'' })
const desk = w.desk
const topic = computed(() => props.points.find(p => p.id === props.context.knowledge))
const resource = computed(() => props.context.document ? w.resources.find(r=>r.original_source_id===props.context.document)?.resource_id || '__missing__' : props.context.resource || desk.resource)
const valid = computed(() => new Set(practiceCandidates(w.questions, w.knowledge, {resource:resource.value,topic:props.context.knowledge || ''}).map(q=>q.id)))
const wrong = computed(() => new Set(w.sessions.filter(s=>s.result?.correct===false).map(s=>s.question_id)))
const needsReview = computed(() => new Set(w.sessions.filter(s=>s.result?.needs_review).map(s=>s.question_id)))
const visible = computed(() => w.questions.filter(q => (!resource.value || q.source?.resource_id===resource.value) && (!props.context.knowledge || valid.value.has(q.id)) && (!desk.kind || q.payload.question_type===desk.kind) && (!desk.query || `${q.payload.stem} ${q.source?.title || ''}`.toLowerCase().includes(desk.query.toLowerCase())) && (desk.category==='all' || desk.category==='ready' && valid.value.has(q.id) || desk.category==='wrong' && wrong.value.has(q.id) || desk.category==='review' && needsReview.value.has(q.id) || desk.category==='attention' && q.status==='draft')))
const ready = computed(() => visible.value.filter(q => valid.value.has(q.id)))
const currentIndex = computed(() => ready.value.findIndex(q=>q.id===w.session?.question_id))
const completedIds = computed(() => new Set(w.sessions.filter(s=>s.result).map(s=>s.question_id)))
const completed = computed(() => ready.value.filter(q=>completedIds.value.has(q.id)).length)
const question = computed(() => w.session?.question)
const answered = computed(() => w.sessions.filter(s => s.result).length)
const resumable=computed(()=>w.session && ((!resource.value && !props.context.knowledge) || valid.value.has(w.session.question_id)))
const resourceOptions=computed(()=>w.resources.filter(r=>r.status==='active' && (!props.notebook || w.questions.some(q=>q.source?.resource_id===r.resource_id))))
const date = value => new Date(value).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'})
const preview = value => value.replace(/[#*$`]/g,'').slice(0,130)
watch(() => JSON.stringify(props.context), () => {desk.focus=false;desk.resource='';if(props.context.import==='1')desk.importOpen=true})
onMounted(async () => { await w.load(); if(props.context.import==='1')desk.importOpen=true; if(w.session && !props.context.resource && !props.context.document && !props.context.knowledge)desk.focus=true })
async function begin(id) {
  const target = id || ready.value.find(q=>q.id!==w.session?.question_id)?.id || ready.value[0]?.id
  if(!target || props.notebook?.archived)return
  if(!await preserveResponse())return
  await w.start(target)
  if(w.session?.question_id===target)desk.focus=true
}
async function preserveResponse(){
  if(props.notebook?.archived)return true
  if(w.session && !w.session.result && w.selected.trim() && (w.session.draft?.response_text!==w.selected || w.session.draft?.needs_review!==w.needsReview)){
    await w.saveResponseDraft()
    if(w.error || w.pending)return false
  }
  return true
}
async function viewSession(item){if(await preserveResponse())await w.viewSession(item)}
async function goToQuestion(index) {
  const row=ready.value[index]
  if(!row || row.id===w.session?.question_id)return
  const saved=w.sessions.find(s=>s.question_id===row.id)
  if(saved) { await viewSession(saved); return }
  await begin(row.id)
}
function explain() {
  if(props.notebook){emit('navigate','notebook',{book:props.notebook.id});return}
  emit('navigate','study',{question:topicQuestion(topic.value?.name || props.context.knowledge || '当前题目'),...(props.context.knowledge?{knowledge:props.context.knowledge}:{})})
}
</script>
<template>
  <section class="practice-desk">
    <PageHeader v-if="!notebook || !desk.focus" :level="notebook?2:1" :eyebrow="notebook?'这个笔记本里的练习':'从理解，到应用'" :title="desk.focus && w.session?'专注这一题':'我的练习题库'" :description="notebook?notebook.title:topic?.name || '整理好习题，留出时间给思考。'"><button v-if="notebook && !notebook.archived" class="product-secondary" @click="emit('add-questions')"><Icon name="plus" :size="16" />从题库添加</button><button v-else-if="!notebook" class="product-secondary" @click="desk.importOpen=!desk.importOpen"><Icon name="plus" :size="16" />导入习题</button><button v-if="!desk.focus" class="product-primary" :disabled="Boolean(notebook?.archived || w.busy || w.pending || !ready.length)" @click="begin()">开始练习<Icon name="arrow" :size="16" /></button></PageHeader>
    <p v-if="w.error" class="product-message error" role="alert">{{w.error}}</p><p v-if="w.notice" class="product-message" role="status">{{w.notice}}</p><section v-if="w.pending" class="product-message" role="status">原操作待确认，刷新只查询回执。<button class="product-text-button" @click="w.load()">核对原操作</button></section>
    <QuestionImportPanel v-if="desk.importOpen && !notebook" :workspace="w" :documents="documents" :initial-resource="resource==='__missing__'?'':resource" @ready="desk.importOpen=false;desk.focus=false;w.refreshList()" />
    <template v-if="desk.focus && w.session">
      <nav class="practice-focus-toolbar"><button class="product-text-button" @click="desk.focus=false">← 返回题库</button><span>普通练习 · {{questionTypes[question?.question_type]}}</span><button class="product-text-button" @click="explain">选择资料，请助教讲解<Icon name="spark" :size="15" /></button></nav>
      <section class="practice-range-progress" aria-label="当前练习范围进度"><LearningProgress :value="completed" :total="ready.length" label="当前筛选范围 · 已记录作答的题目" /><p>{{currentIndex>=0?`第 ${currentIndex+1} 题 / 共 ${ready.length} 题`:'历史题目 · 不在当前筛选范围'}} · 重复作答按一题计数，未提交草稿不计入。</p><nav class="practice-number-nav" aria-label="练习题号"><button v-for="(row,i) in ready" :key="row.id" :aria-label="`第${i+1}题${completedIds.has(row.id)?'，已作答':'，未作答'}`" :aria-current="row.id===w.session.question_id?'step':undefined" :class="{answered:completedIds.has(row.id)}" :disabled="Boolean(w.busy || w.pending)" @click="goToQuestion(i)">{{i+1}}<span v-if="completedIds.has(row.id)" class="sr-only">已作答</span></button></nav></section>
      <div class="practice-focus-grid"><div><ExerciseCard :workspace="w" :readonly="Boolean(notebook?.archived)" /><PracticeFeedback :result="w.session.result" /><div class="practice-next-actions"><button class="product-secondary" :disabled="Boolean(w.busy || w.pending || currentIndex<=0)" @click="goToQuestion(currentIndex-1)">上一题</button><button class="product-secondary" :disabled="Boolean(notebook?.archived || w.busy || w.pending)" @click="begin(w.session.question_id)">再练一次</button><button class="product-primary" :disabled="Boolean(notebook?.archived || w.busy || w.pending || currentIndex<0 || currentIndex>=ready.length-1)" @click="goToQuestion(currentIndex+1)">下一题<Icon name="arrow" :size="16" /></button></div><details class="practice-evidence"><summary>本题来源与原文</summary><p>{{w.session.source.title || '手工录入'}} · 第{{w.session.question_revision}}版</p><MarkdownRenderer v-for="(unit,i) in w.session.source.evidence || []" :key="i" :source="unit.raw_md" /></details></div><aside class="practice-session-aside"><h3>普通练习记录</h3><p>独立保存作答与反馈，<br />不改变正式BKT掌握度。</p><div class="practice-aside-metric"><strong>{{answered}}</strong><span>已记录的作答次数</span></div><h3>最近练习</h3><button v-for="item in w.sessions.slice(0,8)" :key="item.id" :class="{active:w.session.id===item.id}" :aria-label="`${item.result?.correct===true?'答对':item.result?.correct===false?'答错':item.result?'已记录':'草稿'}：${preview(item.question.stem).slice(0,38)}`" :disabled="Boolean(w.busy || w.pending)" @click="viewSession(item)"><span :class="item.result?.correct===true?'correct':item.result?.correct===false?'incorrect':'neutral'">{{item.result?.correct===true?'✓':item.result?.correct===false?'×':'·'}}</span><span>{{preview(item.question.stem).slice(0,38)}}</span></button></aside></div>
    </template>
    <template v-else>
      <div class="practice-overview-stats"><div><span class="practice-stat-icon lavender"><Icon name="book" :size="20" /></span><strong>{{w.questions.length}}</strong><span>已保存题目</span></div><div><span class="practice-stat-icon blue"><Icon name="check" :size="20" /></span><strong>{{valid.size}}</strong><span>当前范围可练</span></div><div><span class="practice-stat-icon peach"><Icon name="refresh" :size="20" /></span><strong>{{wrong.size}}</strong><span>经确认的错题</span></div><div><span class="practice-stat-icon mint"><Icon name="history" :size="20" /></span><strong>{{answered}}</strong><span>已记录作答</span></div></div>
      <div class="practice-library"><aside class="practice-bank-filter"><h3>题目分类</h3><button v-for="item in [['all','全部题目'],['ready','可以练习'],['wrong','客观错题'],['review','我标记的复习'],['attention','待处理'] ]" :key="item[0]" :class="{active:desk.category===item[0]}" @click="desk.category=item[0]">{{item[1]}}</button><h3>按资料来源</h3><label class="sr-only" for="desk-resource">筛选题目来源</label><select id="desk-resource" v-model="desk.resource" :disabled="Boolean(context.resource || context.document)"><option value="">全部来源</option><option v-for="r in resourceOptions" :key="r.resource_id" :value="r.resource_id">{{r.title}}</option></select><p>未核验答案仅供参考对照。<br />普通练习不更新BKT。</p><button v-if="resumable" class="product-text-button" @click="desk.focus=true">继续上次练习 →</button></aside><div class="practice-question-area"><div class="practice-question-toolbar"><label class="product-search"><Icon name="search" :size="16" /><input v-model="desk.query" placeholder="搜索题目或资料…" aria-label="搜索题目" /></label><label><span class="sr-only">题型</span><select v-model="desk.kind" aria-label="按题型筛选"><option value="">全部题型</option><option v-for="(name,key) in questionTypes" :key="key" :value="key">{{name}}</option></select></label></div><div v-if="!visible.length" class="product-empty"><Icon name="book" :size="33" /><h2>这个范围还没有题目</h2><p>{{notebook?'从题库添加习题，或为笔记本关联对应的习题资料。':'导入一份习题，或换一个筛选条件。'}}</p><button v-if="notebook && !notebook.archived" class="product-secondary" @click="emit('add-questions')">从题库添加</button><button v-else class="product-secondary" @click="desk.importOpen=true">导入我的习题</button></div><article v-for="(row,index) in visible" :key="row.id" class="practice-question-row"><span class="practice-row-number">{{String(index+1).padStart(2,'0')}}</span><div><div class="practice-row-tags"><span>{{questionTypes[row.payload.question_type]}}</span><span :class="{pending:row.status!=='practice'}">{{row.status==='practice'?'可练习':'待处理'}}</span><small>{{row.review?.reviewed?'人工核对':'未人工核验'}}</small></div><MarkdownRenderer :source="row.payload.stem" /><footer>{{row.source?.title || '手工录入'}}<span>{{date(row.updated_at)}}</span></footer></div><button v-if="valid.has(row.id)" class="product-text-button" :aria-label="`练习第${index+1}题`" :disabled="Boolean(w.busy || w.pending)" @click="begin(row.id)">练习<Icon name="arrow" :size="16" /></button><button v-else class="product-text-button" @click="emit('navigate','bank',{question:row.id})">处理</button></article></div></div>
    </template>
  </section>
</template>
