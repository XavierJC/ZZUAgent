<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import QuestionImportPanel from '../components/QuestionImportPanel.vue'
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { questionTypes } from '../features/questions/types.js'
import { practiceCandidates, topicQuestion } from '../features/learning/journey.js'
const props=defineProps({workspace:Object,documents:Object,context:{type:Object,default:()=>({})},points:{type:Array,default:()=>[]}})
const emit=defineEmits(['navigate'])
const importing=ref(props.context.import==='1'), showList=ref(Boolean(props.context.knowledge || props.context.document || props.context.resource)), query=ref(''), selectedResource=ref('')
const topic=computed(()=>props.points.find(p=>p.id===props.context.knowledge))
const documentResource=computed(()=>props.workspace.resources.find(r=>r.original_source_type==='document' && r.original_source_id===props.context.document))
const scopeResource=computed(()=>selectedResource.value || (props.context.document ? documentResource.value?.resource_id || '__missing_document__' : props.context.resource || ''))
const contextResource=computed(()=>props.workspace.resources.find(r=>r.resource_id===scopeResource.value))
const sourceFilter=computed({get:()=>scopeResource.value==='__missing_document__'?'':scopeResource.value,set:value=>{selectedResource.value=value}})
const ready=computed(()=>practiceCandidates(props.workspace.questions,props.workspace.knowledge,{resource:scopeResource.value,topic:props.context.knowledge || '',query:query.value}))
const attention=computed(()=>props.workspace.questions.filter(q=>q.status==='draft'))
const inSession=computed(()=>props.workspace.session && !showList.value)
const scoped=computed(()=>Boolean(props.context.knowledge || props.context.document || props.context.resource))
const resumable=computed(()=>props.workspace.session && (!scoped.value || ready.value.some(q=>q.id===props.workspace.session.question_id)))
watch(()=>JSON.stringify(props.context),()=>{showList.value=true;selectedResource.value='';query.value='';importing.value=props.context.import==='1'})
async function begin(id=null){
  if(!id && !scoped.value && !selectedResource.value && !query.value.trim()){
    await props.workspace.start()
    if(props.workspace.session)showList.value=false
    return
  }
  const question=id || ready.value.find(q=>q.id!==props.workspace.session?.question_id)?.id || ready.value[0]?.id
  if(!question)return
  await props.workspace.start(question)
  if(props.workspace.session?.question_id===question)showList.value=false
}
onMounted(()=>{props.workspace.filter={q:'',status:'',question_type:'',resource_id:'',chapter_id:'',concept_id:''};props.workspace.load()})
</script>
<template>
  <section class="simple-practice">
    <div class="panel simple-practice-heading"><div><p class="eyebrow">先练一道，再进一步</p><h2>{{inSession?'专注当前练习':'从一道练习开始'}}</h2><p>已有 {{ready.length}} 道可练习题，{{attention.length}} 道需要处理。普通练习独立记录，不更新BKT。</p></div><div class="phase5-actions"><button v-if="inSession" class="button secondary" @click="showList=true">返回题目列表</button><button v-else-if="resumable" class="button secondary" @click="showList=false">继续上次练习</button><button class="button primary" :disabled="Boolean(workspace.busy || workspace.pending || !ready.length)" @click="begin()">{{inSession?'下一道练习':'开始练习'}}</button><button v-if="!ready.length && attention.length" class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.organize()">整理已有题目</button><button class="button secondary" :aria-expanded="importing" @click="importing=!importing">导入习题</button></div></div>
    <div v-if="scoped" class="journey-context" role="status"><strong>{{topic?.name || documentResource?.title || contextResource?.title || '指定资料'}} · 相关普通练习</strong><p>按已保存的知识关联或资料来源筛选，不将题目文字相似视为正式关联。</p><button class="wb-text-button" @click="emit('navigate','practice')">查看全部练习</button></div>
    <QuestionImportPanel v-if="importing" :workspace="workspace" :documents="documents" :initial-resource="scopeResource==='__missing_document__'?'':scopeResource" @ready="importing=false;showList=true;workspace.refreshList()" />
    <section v-if="!inSession" class="panel">
      <div class="practice-filters"><div><label for="practice-search">查找题目</label><input id="practice-search" v-model="query" placeholder="输入题干或资料名称" /></div><div><label for="practice-resource">题目来源</label><select id="practice-resource" v-model="sourceFilter" :disabled="Boolean(context.document || context.resource)"><option value="">全部来源</option><option v-for="r in workspace.resources.filter(r=>r.status==='active')" :key="r.resource_id" :value="r.resource_id">{{r.title}}</option></select></div></div>
      <h3>我的练习题</h3><p v-if="!ready.length">{{scoped?'当前范围没有可用练习；你可以查看全部练习，或导入对应习题。':'未找到可练习题。可以换个筛选条件，或先导入习题。'}}</p>
      <div class="practice-question-list"><article v-for="(q,index) in ready" :key="q.id" class="pb-item practice-question"><span class="practice-number">{{index+1}}</span><div style="min-width:0;flex:1"><MarkdownRenderer :source="q.payload.stem" /><small>{{questionTypes[q.payload.question_type]}} · {{q.review?.automation ? '自动整理 · 未人工核验' : '已人工整理'}} · {{q.source.title || '手工录入'}}</small><button class="wb-text-button" :aria-label="`开始第${index+1}题`" :disabled="Boolean(workspace.busy || workspace.pending)" @click="begin(q.id)">开始练习 →</button></div></article></div>
    </section>
    <template v-if="inSession"><div class="journey-actions"><button class="wb-text-button" @click="emit('navigate','study',{question:topic ? topicQuestion(topic.name) : '请结合我接下来选定的资料，解释练习涉及的概念。'})">选择资料，请助教讲解</button><button class="wb-text-button" @click="emit('navigate','insights')">查看学习进度</button></div><PersonalBankWorkspace compact mode="practice" :workspace="workspace" @navigate="(...args)=>emit('navigate',...args)" /></template>
    <p v-if="workspace.error" class="alert alert-error" role="alert">{{workspace.error}}</p>
    <details class="panel"><summary>需要处理的题目（{{attention.length}}）</summary><p>缺项、识别疑点或答案冲突集中在这里处理。</p><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending || !attention.length)" @click="workspace.organize()">整理已有草稿（每批最多50题）</button><button v-for="q in attention" :key="q.id" class="pb-item" @click="emit('navigate','bank',{question:q.id})">{{q.payload.stem.slice(0,80)}}<small>{{q.review?.automation?.issues?.join('、') || '尚未自动整理'}}</small></button></details>
    <details class="panel"><summary>正式诊断与学习记录</summary><p>正式诊断使用已经准入的题库更新BKT，保留原有规则。</p><button class="button secondary" @click="emit('navigate','learn')">继续正式学习 / 复习已做题</button><button class="button secondary" @click="emit('navigate','history')">查看正式记录</button></details>
  </section>
</template>
