<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useTeachingWorkspace } from './useTeachingWorkspace.js'
import { useCourseBuilder } from './useCourseBuilder.js'
import CourseBuilderView from './views/CourseBuilderView.vue'
import LearningInsights from './views/LearningInsights.vue'
import LearningResources from './views/LearningResources.vue'
import KnowledgeArchitecture from './components/KnowledgeArchitecture.vue'
import PersonalBankWorkspace from './components/PersonalBankWorkspace.vue'
import './phase5.css'
import { useWorkspace } from './useWorkspace.js'
import { usePageRoute } from './usePageRoute.js'
import LearningOverview from './views/LearningOverview.vue'
import LearningHistory from './views/LearningHistory.vue'
import ResourcesView from './views/ResourcesView.vue'
import QuestionBankView from './views/QuestionBankView.vue'
import Icon from './components/Icon.vue'
import MarkdownRenderer from './components/MarkdownRenderer.vue'
import NotesPanel from './components/NotesPanel.vue'
import NotesDialogs from './components/NotesDialogs.vue'
import { useNotesWorkspace } from './useNotesWorkspace.js'
import { api as defaultApi } from './api.js'
import { useStudyWorkbench } from './useStudyWorkbench.js'
import StudyWorkbench from './components/StudyWorkbench.vue'
import { useSelfAssessments } from './useSelfAssessments.js'
import { useStudyGuidance } from './useStudyGuidance.js'
import { useCourseDocuments } from './useCourseDocuments.js'
import { useKnowledgeArchitecture } from './useKnowledgeArchitecture.js'
import { usePersonalBank } from './usePersonalBank.js'

const props = defineProps({ client: Object, store: Object, notesStore: Object })
const w = reactive(useWorkspace(props.client, props.store))
const n = reactive(useNotesWorkspace(props.client || defaultApi, computed(() => w.student), props.notesStore))
const flow = reactive(useTeachingWorkspace(props.client || defaultApi,w))
const builder = reactive(useCourseBuilder(props.client || defaultApi,computed(() => w.student)))
const study = reactive(useStudyWorkbench(props.client || defaultApi, computed(() => w.student),undefined,{session:()=>flow.session,scope:()=>flow.data?.release?.retrieval_scope || null,contexts:()=>flow.data?.explanations || [],revision:()=>w.snapshot?.revision,refresh:()=>flow.load()}))
const documents = reactive(useCourseDocuments(props.client || defaultApi, computed(() => w.student)))
const bank = reactive(usePersonalBank(props.client || defaultApi, computed(() => w.student)))
const architecture = reactive(useKnowledgeArchitecture(props.client || defaultApi, computed(() => w.student)))
const self = reactive(useSelfAssessments(props.client || defaultApi, computed(() => w.student)))
const guides = reactive(useStudyGuidance(props.client || defaultApi, computed(() => w.student), computed(() => self.overview), computed(() => study.chosen), computed(() => self.canGenerate)))
const { route, go } = usePageRoute(() => { if (builder.editor && !builder.persist()) return false; if (flow.pending && !flow.persist()) return false; if ((n.dirty || n.pending) && !n.persist()) return false; if ((bank.dirty || bank.pending) && !bank.persist()) return false; if (self.dirty && !self.persist()) return false; if (architecture.dirty && !architecture.persist()) return false; return true })
const tab = computed(() => route.value.page)
const formMode = ref('new'), learnerId = ref(`learner-${crypto.randomUUID().slice(0, 8)}`)
const goals = ref(['logistic_regression']), query = ref(''), searched = ref(false)
const builderPages=['builder','materials','architecture','bank','publish']
const isBuilder=computed(()=>builderPages.includes(tab.value))
const studentTabs=[{id:'learn',name:'我的学习',icon:'home'},{id:'insights',name:'学情与目标',icon:'target'},{id:'study',name:'AI伴学',icon:'book'},{id:'history',name:'学习记录',icon:'history'}]
const builderTabs=[{id:'builder',name:'课程概览',icon:'home'},{id:'materials',name:'课程资料',icon:'book'},{id:'architecture',name:'知识体系',icon:'book'},{id:'bank',name:'习题管理',icon:'book'},{id:'publish',name:'课程审核与发布',icon:'check'}]
const tabs=computed(()=>isBuilder.value?builderTabs:studentTabs)
const auxiliary=[{id:'notes',name:'我的笔记',icon:'book'},{id:'resources',name:'学习资料',icon:'book'},{id:'practice',name:'普通练习与错题',icon:'book'}]
const pageTitle=computed(()=>[...studentTabs,...builderTabs,...auxiliary].find(i=>i.id===tab.value)?.name || '我的学习')
const goalsText = computed(() => w.snapshot?.goals.map(w.topicName).join('、'))
async function start() { const chosenCourse=flow.selectedRelease; await w.start(learnerId.value, goals.value, formMode.value === 'restore',flow.enabled);if(w.active && flow.enabled){await flow.load();if(formMode.value!=='restore' && flow.releases.some(r=>r.id===chosenCourse)){flow.selectedRelease=chosenCourse;await flow.begin();if(flow.session)await flow.allocate()}} }
async function search() { searched.value = true; await w.search(query.value) }
function goTab(id, params = {}) { if (id !== tab.value || Object.keys(params).length) n.navigate(() => go(id, params)) }
function leaveStudent() { n.navigate(() => { if (go('learn')) w.leave() }) }
function refreshCurrent() { if (['builder','publish'].includes(tab.value)) return builder.load(); if(tab.value==='architecture')return architecture.load(); if(tab.value==='insights')return Promise.all([self.load(),guides.load()]); if(['resources','practice'].includes(tab.value))return bank.load(); return tab.value === 'notes' ? n.load() : ['materials','bank'].includes(tab.value) ? bank.load() : tab.value === 'study' ? Promise.all([study.load(), self.load(), guides.load()]) : w.active ? w.refresh().then(()=>flow.load()) : w.boot() }
function editStudyNote(id) { goTab('notes', { note: id }) }
async function restoreRoute() {
  if (!w.active) return
  const params = route.value.params
  if(tab.value==='bank' && params.view==='practice'){go('practice',params,true);return}
  if (['materials','bank','practice','resources'].includes(tab.value)) {
    if (tab.value === 'bank' && params.resource) bank.filter.resource_id=params.resource
    await bank.load()
    if (['materials','resources'].includes(tab.value)) { bank.section = 'resources'; const item = bank.resources.find(r => r.resource_id === params.resource); if (item && item.resource_id !== bank.resource?.resource_id) await bank.selectResource(item) }
    else { bank.section = tab.value === 'practice' ? 'practice' : 'bank'; if (params.question && params.question !== bank.current?.id) await bank.open(params.question) }
  }
  if (tab.value === 'notes' && params.note) { await n.load(); await n.open(params.note) }
}
watch([route, () => w.active], restoreRoute)
watch(()=>w.active,active=>{if(active)flow.load()})
watch(()=>flow.data?.guidance,g=>{if(g)self.overview=g})
async function explainNext(){await study.load();const scope=flow.data?.release?.retrieval_scope;if(scope)study.selected=scope.filter(r=>study.sources.some(s=>s.source_type===r.source_type && s.source_id===r.source_id && s.source_version===r.source_version));study.query=`请围绕${w.topicName(flow.data?.next_task?.knowledge_id || w.decision?.knowledge_id)}解释关键概念，举一个例子，并说明怎样准备下一次正式练习。`;goTab('study')}
watch(() => bank.current?.id, id => { if (tab.value === 'bank' && id && route.value.params.question !== id) go('bank', { ...route.value.params, question: id, view: bank.section }, true) })
watch(() => bank.section, value => { if (tab.value === 'bank' && ['bank','practice'].includes(value) && route.value.params.view !== value) go('bank',{...route.value.params,view:value},true) })
watch(() => bank.resource?.resource_id, id => { if (tab.value === 'materials' && id && route.value.params.resource !== id) go('materials', { resource: id }, true) })
function protectDraft(event) { if (n.dirty || n.pending || builder.dirty || builder.pending || flow.pending || self.dirty || self.pending || documents.file || documents.pending || bank.dirty || bank.pending || architecture.dirty || architecture.pending) { event.preventDefault(); event.returnValue = '' } }
onMounted(w.boot)
onMounted(flow.publicCourses)
onMounted(() => window.addEventListener('beforeunload', protectDraft))
onUnmounted(() => window.removeEventListener('beforeunload', protectDraft))
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="goTab('learn')"><span class="brand-symbol"><Icon name="cap" :size="27" /></span><span><strong>智学郑大</strong><small>EduAgent</small></span></a>
      <div class="workspace-switch" aria-label="工作区切换"><button :aria-pressed="!isBuilder" @click="goTab('learn')">学生学习</button><button :aria-pressed="isBuilder" @click="goTab('builder')">课程构建</button></div><p class="sidebar-label">{{ isBuilder ? '本机内容维护' : '学生学习主线' }}</p>
      <nav aria-label="学习导航"><button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :aria-current="tab === item.id ? 'page' : undefined" @click="goTab(item.id)"><Icon :name="item.icon" /><span>{{ item.name }}</span><span v-if="tab === item.id" class="nav-dot" /></button></nav><p v-if="!isBuilder" class="sidebar-label">学习辅助</p><nav v-if="!isBuilder" aria-label="学习辅助"><button v-for="item in auxiliary" :key="item.id" :class="{active:tab===item.id}" @click="goTab(item.id)"><Icon :name="item.icon" />{{ item.name }}</button></nav>
      <div class="sidebar-course"><span class="course-art"><Icon name="book" :size="25" /></span><p class="eyebrow">CURRENT COURSE</p><h3>机器学习</h3><p>5 个知识点，从理解到应用。</p><div class="course-line" /><span>诊断 · 学习 · 练习 · 反馈</span></div>
      <div class="sidebar-bottom"><span class="status-dot" :class="{ online: w.health?.status === 'ok' }" />{{ w.health ? '本地学习服务' : '连接学习服务中' }}<small>校园创新应用 · 演示原型</small></div>
    </aside>

    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb">机器学习 <span>/</span><strong>{{ pageTitle }}</strong></div><div class="topbar-actions"><span v-if="w.active" class="learner-chip">{{ w.student }}</span><button class="icon-button" :disabled="Boolean(w.busy || n.busy)" :aria-label="tab === 'notes' ? '刷新笔记列表' : '刷新学习记录'" title="刷新学习记录，不调用模型" @click="refreshCurrent()"><Icon name="refresh" :size="18" /></button><button v-if="w.active" class="icon-button" :disabled="Boolean(w.busy || w.pending || n.busy)" aria-label="切换学习标识" title="切换学习标识，保留学习记录" @click="leaveStudent()"><Icon name="logout" :size="18" /></button></div></header>
      <main id="main-content" class="workspace">
        <NotesDialogs :workspace="n" />
        <div v-if="tab !== 'notes' && n.error" class="alert alert-error" role="alert">{{ n.error }}</div>
        <div v-if="w.error" class="alert alert-error" role="alert">{{ w.error }}<span v-if="w.pending">原提交编号已保留，请重试原提交。</span></div>
        <div v-if="w.notice" class="alert alert-info" role="status">{{ w.notice }}</div>
        <div v-if="w.busy === 'boot'" class="loading-state" role="status">正在准备你的学习空间…</div>

        <template v-else-if="!w.active">
          <section class="welcome-hero"><div><span class="hero-kicker"><span class="tiny-dot" />从理解开始，让学习有方向</span><h1>先找到起点，<br />再走好<span>每一步。</span></h1><p>用一次诊断发现薄弱点，<br />让讲解、练习和反馈围绕你的学习状态展开。</p><div class="hero-pills"><span>个性化学习路径</span><span>有依据的课程讲解</span><span>持续记录与反馈</span></div></div><div class="learning-orbit" aria-hidden="true"><div class="orbit-ring ring-one" /><div class="orbit-ring ring-two" /><div class="orbit-center"><Icon name="cap" :size="46" /><span>LEARN & GROW</span></div><span class="orbit-node node-one">01<span>学情诊断</span></span><span class="orbit-node node-two">02<span>知识讲解</span></span><span class="orbit-node node-three">03<span>针对练习</span></span><span class="orbit-node node-four">04<span>反馈与规划</span></span></div></section>
          <section class="panel onboarding-panel" aria-labelledby="start-title"><div class="onboarding-intro"><span class="section-number">01 / START HERE</span><h2 id="start-title">从一个学习目标开始</h2><p>选择想理解的知识点，我们会把必要的先修内容一起安排好。</p><div class="intro-footnote"><Icon name="target" :size="18" /><span>每次作答，都会留下可以回看的学习记录。</span></div></div><form class="start-form" @submit.prevent="start"><div class="segmented"><button type="button" :class="{ chosen: formMode === 'new' }" @click="formMode = 'new'">新建学习</button><button type="button" :class="{ chosen: formMode === 'restore' }" @click="formMode = 'restore'">恢复已有记录</button></div><label v-if="flow.enabled" for="onboarding-release">选择已发布课程</label><select v-if="flow.enabled" id="onboarding-release" v-model="flow.selectedRelease"><option value="">请选择课程版本</option><option v-for="r in flow.releases" :key="r.id" :value="r.id" :disabled="!r.usable">{{ r.title }} · {{ r.kind==='demo'?'工程演示，内容待审核':'已审核课程' }}</option></select><p v-if="flow.error" role="alert">{{ flow.error }}</p><label class="field-label" for="learner-id">学习标识<span>使用演示昵称即可</span></label><input id="learner-id" v-model="learnerId" maxlength="128" autocomplete="off" required placeholder="例如 learner-01" :disabled="Boolean(w.busy)" /><fieldset v-if="formMode === 'new'" class="goal-fieldset" :disabled="Boolean(w.busy)"><legend class="field-label">这次想学什么？<span>可多选</span></legend><div class="goal-options"><label v-for="point in w.knowledge" :key="point.id" :class="{ chosen: goals.includes(point.id) }"><input v-model="goals" type="checkbox" :value="point.id" /><span>{{ point.name }}</span><Icon v-if="goals.includes(point.id)" name="check" :size="15" /></label></div></fieldset><p v-else class="restore-note">输入之前使用的标识即可恢复原目标、答题记录和助教讲解。</p><button class="button primary start-button" :disabled="Boolean(w.busy || !w.health || (formMode === 'new' && (!goals.length || (flow.enabled && !flow.selectedRelease))))">{{ w.busy === 'start' ? '正在准备…' : formMode === 'restore' ? '继续我的学习' : '开始学情诊断' }}<Icon name="arrow" :size="19" /></button></form></section>
        </template>

        <template v-else>
          <section class="page-heading"><div><p class="eyebrow">{{ tab === 'learn' ? 'YOUR NEXT SMALL STEP' : tab === 'history' ? 'EVERY ANSWER COUNTS' : tab === 'notes' ? 'MY LEARNING NOTES' : 'FOLLOW THE SOURCE' }}</p><h1>{{ tab === 'learn' ? '把理解，再向前推进一步。' : tab === 'history' ? '回看走过的每一步。' : tab === 'notes' ? '把理解，写成自己的笔记。' : tab === 'bank' ? '识别、校对，再开始练习。' : tab === 'materials' ? '把课程资料放在一起。' : '围绕资料，理解课程。' }}</h1><p>{{ tab === 'learn' ? `学习目标：${goalsText}` : tab === 'history' ? '从答题反馈中发现变化，而不是只看一个分数。' : tab === 'notes' ? '记录自己的理解，让原文、公式与知识点关联一起保存。' : tab === 'bank' ? '保留原题型与来源，普通练习独立保存。' : tab === 'materials' ? '上传、查看原件和解析，整理课程知识结构。' : '选择资料，再结合模型解释和可追溯引用。' }}</p></div><span class="course-badge"><Icon name="book" :size="17" />机器学习</span></section>
          <LearningOverview v-if="tab === 'learn'" :w="w" :self-workspace="self" :flow="flow" @navigate="goTab" @explain="explainNext" />
          <CourseBuilderView v-else-if="['builder','publish'].includes(tab)" :workspace="builder" :overview="tab==='builder'" @navigate="goTab" />
          <KnowledgeArchitecture v-else-if="tab==='architecture'" :workspace="architecture" @navigate="goTab" />
          <LearningInsights v-else-if="tab==='insights'" :self-workspace="self" :guide-workspace="guides" :goals="goalsText" @navigate="goTab" />
          <LearningResources v-else-if="tab==='resources'" :workspace="bank" @navigate="goTab" @edit-note="editStudyNote" />
          <PersonalBankWorkspace v-else-if="tab==='practice'" mode="practice" :workspace="bank" @navigate="goTab" />
          <LearningHistory v-else-if="tab === 'history'" :w="w" @navigate="goTab" />
          <section v-else-if="tab==='study'" class="phase5-builder"><div class="phase5-context"><h2>AI伴学</h2><p>当前目标：{{ goalsText }}；{{ flow.data?.release ? `课程版本${flow.data.release.release_version}（${flow.data.release.kind==='demo'?'演示版':'已审核内容'}）` : '尚未绑定课程发布版本，可先返回我的学习建立会话。' }}</p><p>{{ flow.data?.next_task?.reason }}</p><div class="phase5-actions"><button class="button secondary" @click="goTab('learn')">返回学情与正式练习</button><button class="button secondary" @click="goTab('practice')">进入普通练习（不更新BKT）</button></div></div>
          <StudyWorkbench v-if="tab === 'study'" :workspace="study" :bank-workspace="bank" :document-workspace="documents" :architecture-workspace="architecture" :snapshot="w.snapshot" :goal-names="goalsText" :current-topic="w.decision?.knowledge_id" :self-workspace="self" :guide-workspace="guides" @navigate="goTab" @edit-note="editStudyNote" /></section>
          <QuestionBankView v-else-if="tab === 'bank'" :workspace="bank" @navigate="goTab" />
          <NotesPanel v-else-if="tab === 'notes'" :workspace="n" :knowledge="w.knowledge" />
          <ResourcesView v-else :bank="bank" :documents="documents" :architecture="architecture" @navigate="goTab" @edit-note="editStudyNote"><section class="panel materials-panel"><div class="panel-heading"><div><p class="eyebrow">COURSE NOTES</p><h2>从课程资料中寻找依据</h2></div><span class="badge">5 个知识点</span></div><form class="search-form" @submit.prevent="search"><label class="sr-only" for="material-query">检索课程资料</label><input id="material-query" v-model="query" maxlength="1000" required placeholder="例如：为什么学习率过大会发散？" /><button class="button primary" :disabled="Boolean(w.searchBusy || !w.health?.retrieval_available)">{{ w.searchBusy ? '正在检索…' : '检索资料' }}<Icon name="arrow" :size="17" /></button></form><p class="small muted">从本地课程说明中检索，不调用模型生成。资料待审阅，检索结果的关联仍需核对。</p><div v-if="w.sources.length" class="source-list"><article v-for="source in w.sources" :key="source.citation_id" class="source-card"><div><span class="badge badge-blue">{{ source.title }}</span><span class="small muted">[{{ source.citation_id }}]</span></div><h3>{{ source.section }}</h3><MarkdownRenderer :source="source.content" /><small class="muted">{{ source.source }} · {{ source.review_status === 'pending' ? '待内容审阅' : '已审阅' }}</small></article></div><div v-else class="empty-state"><Icon name="book" :size="36" /><h3>{{ searched ? '没有找到足够相关的课程片段。' : '先从一个具体问题开始。' }}</h3><p>{{ searched ? '试试课程中的术语，或换一种表述。' : '目前覆盖线性回归、梯度下降、逻辑回归、正则化与模型评估。' }}</p></div></section></ResourcesView>
        </template>
        <footer class="workspace-footer"><span><span class="tiny-dot" />{{ w.reviewNotice }}</span><span>EduAgent · 让学习有迹可循</span></footer>
      </main>
    </div>
  </div>
</template>
