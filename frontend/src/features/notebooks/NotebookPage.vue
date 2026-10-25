<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import Icon from '../../components/Icon.vue'
import SourceDrawer from '../../components/SourceDrawer.vue'
import QuickDocumentUpload from '../../components/QuickDocumentUpload.vue'
import ProductDialog from '../../shared/ProductDialog.vue'
import ExerciseDesk from '../practice/ExerciseDesk.vue'
import NotebookSources from './NotebookSources.vue'
import NotebookChat from './NotebookChat.vue'
import NotebookNotes from './NotebookNotes.vue'
import { questionTypes } from '../questions/types.js'
import { sourceKey } from '../chat/useStudyWorkbench.js'
import './notebook.css'
const space=useCurrentCourseSpace(), books=space.features.notebooks
const entry=computed(()=>books.current?.detail.id===space.route.params.book?books.current:null)
const tab=ref('chat'), mobilePanel=ref('chat'), picker=ref(false), pickerMode=ref('sources'), sourceQuery=ref(''), chosen=ref([]), questions=ref([]), editing=ref(false), title=ref(''), description=ref(''), editNoteId=ref(null)
const noteWorkspace=ref(null), questionBusy=ref(false)
let opening=0
const wide=ref(false)
let media
const resize=()=>{wide.value=media.matches}
onMounted(()=>{media=window.matchMedia?.('(min-width:1500px)');if(media){resize();media.addEventListener('change',resize)}})
onUnmounted(()=>{opening++;media?.removeEventListener('change',resize)})
watch(()=>space.route.params.book,async id=>{const token=++opening;tab.value=['chat','practice','notes'].includes(space.route.params.task)?space.route.params.task:'chat';mobilePanel.value='chat';editNoteId.value=null;noteWorkspace.value=null;if(!id){books.error='请选择要打开的笔记本。';return}const e=await books.open(id);if(e && token===opening){await e.chat.load();if(token!==opening)return;if(tab.value==='practice')books.practice(e);if(tab.value==='notes')noteWorkspace.value=space.registry.use('notes')}},{immediate:true})
const options=computed(()=>pickerMode.value==='questions'?questions.value.map(q=>({source_type:'personal_question',source_id:q.id,source_version:`r${q.revision}`,title:q.payload.stem.slice(0,150),index_status:q.status==='practice'?'ready':'failed',question_type:q.payload.question_type})):books.catalog)
const filtered=computed(()=>options.value.filter(s=>s.title.toLowerCase().includes(sourceQuery.value.toLowerCase())))
const kind=s=>({course_material:'课程资料',uploaded_document:'上传资料 · 未核验',teaching_material:'已确认课件片段',personal_note:'个人笔记',personal_question:questionTypes[s.question_type] || '练习题'}[s.source_type])
const pickerKeys=computed(()=>new Set(chosen.value.map(sourceKey)))
const missing=computed(()=>entry.value?.detail.sources.filter(s=>(pickerMode.value==='questions')===(s.source_type==='personal_question') && !options.value.some(o=>sourceKey(o)===sourceKey(s))) || [])
async function chooseTab(value, updateRoute=true){
  const apply=async()=>{tab.value=value;if(updateRoute)space.replaceRoute?.('notebook',{...space.route.params,task:value});if(value==='chat')await entry.value.chat.load();if(value==='practice')books.practice(entry.value);if(value==='notes')noteWorkspace.value=space.registry.use('notes')}
  const notes=space.registry.peek('notes');return notes && tab.value==='notes' && value!=='notes'?notes.navigate(apply):apply()
}
watch(()=>space.route.params.task,value=>{if(entry.value && ['chat','practice','notes'].includes(value) && value!==tab.value)chooseTab(value,false)})
async function openPicker(mode='sources'){
  if(!entry.value)return
  pickerMode.value=mode;sourceQuery.value='';picker.value=true;chosen.value=entry.value.detail.sources.filter(s=>(mode==='questions')===(s.source_type==='personal_question'))
  if(mode==='questions'){questionBusy.value=true;const owner=space.w.student,id=entry.value.detail.id;try{const result=await space.client.bank(owner,'personal-bank/questions?');if(owner===space.w.student && entry.value?.detail.id===id)questions.value=result.items}catch(e){books.error=e.message}finally{questionBusy.value=false}}
  else await books.loadCatalog()
}
function toggle(source,checked){chosen.value=chosen.value.filter(s=>sourceKey(s)!==sourceKey(source));if(checked)chosen.value.push(source)}
async function saveSources(){
  const preserved=entry.value.detail.sources.filter(s=>(pickerMode.value==='questions')!==(s.source_type==='personal_question'))
  const result=await books.setSources([...preserved,...chosen.value]);if(result){picker.value=false;await entry.value.chat.load();if(entry.value.bank)await entry.value.bank.load()}
}
async function uploaded(id){await books.loadCatalog();const item=books.catalog.find(s=>s.source_type==='uploaded_document' && s.source_id===id);if(item){toggle(item,true);books.notice='资料已解析，请点击“保存资料范围”加入当前笔记本。'}}
async function editNote(id){const n=space.registry.use('notes');await n.load();await n.open(id,()=>{editNoteId.value=id;books.rememberNote(id);noteWorkspace.value=n;tab.value='notes'})}
function rename(){title.value=entry.value.detail.title;description.value=entry.value.detail.description;editing.value=true}
async function saveTitle(){if(await books.update(title.value.trim(),description.value.trim(),entry.value.detail.archived))editing.value=false}
async function archive(){const d=entry.value.detail;if(await books.update(d.title,d.description,!d.archived)){editing.value=false;space.navigate('notebooks')}}
function page(number){const s=entry.value?.chat.drawer;if(s?.preview)entry.value.chat.open(s,number)}
</script>
<template>
  <section v-if="entry" class="notebook-workspace" :class="{'is-practicing':tab==='practice'}">
    <header class="notebook-page-toolbar"><div><button class="product-icon-button" aria-label="返回笔记本列表" @click="space.navigate('notebooks')">←</button><span class="notebook-title-icon"><Icon name="book" :size="20" /></span><div><h1>{{entry.detail.title}}</h1><p>{{entry.detail.sources.length}} 项内容 · {{entry.detail.archived?'已归档 · 只读':'机器学习'}}</p></div></div><div><button class="product-text-button" @click="rename"><Icon name="settings" :size="16" />笔记本设置</button></div></header>
    <p v-if="books.error" class="product-message error" role="alert">{{books.error}}</p><p v-if="books.notice" class="product-message" role="status">{{books.notice}}</p><p v-if="books.pending" class="product-message">原修改结果待核对。<button class="product-text-button" @click="books.load()">查询回执</button><button class="product-text-button" :disabled="Boolean(books.busy)" @click="books.retry()">重试原操作（同一编号）</button></p><p v-if="entry.detail.archived" class="product-message">笔记本已归档。资料和历史保留，可在设置中恢复后继续学习。</p>
    <div class="notebook-context"><strong>当前学习主题</strong><span>{{entry.detail.description || entry.detail.title}}</span><span>本轮问答已选 {{entry.chat.chosen.length}} 份资料 · 外发同意逐轮确认</span></div>
    <nav class="notebook-task-tabs" aria-label="笔记本任务"><button class="notebook-mobile-source-tab" :class="{active:mobilePanel==='sources'}" @click="mobilePanel=mobilePanel==='sources'?'chat':'sources'">资料</button><button v-for="item in [['chat','助教问答','spark'],['practice','练习','check'],['notes','学习笔记','note']]" :key="item[0]" :class="{active:tab===item[0] && mobilePanel!=='sources'}" @click="mobilePanel='chat';chooseTab(item[0])"><Icon :name="item[2]" :size="16" />{{item[1]}}</button><span>围绕资料，形成自己的理解</span></nav>
    <div class="notebook-layout" :data-mobile-panel="mobilePanel" :class="{'has-preview':Boolean(entry.chat.drawer)}"><NotebookSources v-if="tab==='chat' || mobilePanel==='sources'" :entry="entry" :archived="entry.detail.archived" @add="openPicker()" /><div class="notebook-task-content"><NotebookChat v-if="tab==='chat'" :key="entry.detail.id" :workspace="entry.chat" :archived="entry.detail.archived" @edit-note="editNote" @practice="chooseTab('practice')" /><ExerciseDesk v-else-if="tab==='practice' && entry.bank" :key="entry.detail.id+'practice'" :workspace="entry.bank" :notebook="entry.detail" :points="space.w.knowledge" @navigate="space.navigate" @add-questions="openPicker('questions')" /><NotebookNotes v-else-if="tab==='notes' && noteWorkspace" :key="entry.detail.id+'notes'" :books="books" :entry="entry" :workspace="noteWorkspace" :initial-note="editNoteId" /></div><SourceDrawer :embedded="wide" :source="entry.chat.drawer" :loading="entry.chat.opening" @close="entry.chat.closePreview()" @page="page" /></div>
    <ProductDialog :open="picker" :title="pickerMode==='questions'?'添加已有习题':'管理笔记本资料'" @close="picker=false"><div class="notebook-source-picker"><p>{{pickerMode==='questions'?'关联现有题目，作答记录独立保存在此笔记本。':'加入笔记本与参与本轮问答分开控制；保存仅关联明确选择的当前版本。'}}</p><QuickDocumentUpload v-if="pickerMode==='sources' && space.features.documents?.supported" :workspace="space.features.documents" @ready="uploaded" /><label class="product-search"><Icon name="search" :size="16" /><input v-model="sourceQuery" :aria-label="pickerMode==='questions'?'搜索可添加习题':'搜索可添加资料'" placeholder="搜索已有内容…" /></label><p v-if="questionBusy" role="status">正在读取题库…</p><p v-if="missing.length" class="product-message">{{missing.length}} 项原关联已不可用。取消选择后可移除；不会自动替换版本。<button v-for="s in missing" :key="sourceKey(s)" class="product-text-button" @click="toggle(s,false)">移除 {{s.title}}</button></p><label v-for="source in filtered" :key="sourceKey(source)" class="notebook-picker-row"><input type="checkbox" :checked="pickerKeys.has(sourceKey(source))" :disabled="!['ready','empty'].includes(source.index_status)" @change="toggle(source,$event.target.checked)" /><span><strong>{{source.title}}</strong><small>{{kind(source)}} · {{source.index_status==='ready'?'已就绪':source.index_status==='empty'?'暂无正文':'未就绪'}} · 版本 {{source.source_version.slice(0,14)}}</small><small v-if="chosen.some(s=>sourceKey(s)===sourceKey(source) && s.source_version!==source.source_version)">原关联已过期。重新勾选可选择当前版本。</small></span></label><p v-if="!filtered.length && !questionBusy">暂时没有对应内容。</p><p v-if="books.error" class="product-message error" role="alert">{{books.error}}</p><footer><span>已选 {{chosen.length}} 项</span><button class="product-secondary" @click="picker=false">取消</button><button class="product-primary" :disabled="Boolean(books.busy || books.pending)" @click="saveSources">保存{{pickerMode==='questions'?'题目':'资料范围'}}</button></footer></div></ProductDialog>
    <ProductDialog :open="editing" title="笔记本设置" @close="editing=false"><form class="product-form" @submit.prevent="saveTitle"><label for="edit-notebook-title">名称</label><input id="edit-notebook-title" v-model="title" maxlength="120" required /><label for="edit-notebook-description">说明</label><textarea id="edit-notebook-description" v-model="description" maxlength="1000" rows="3" /><p>归档保留资料、笔记和历史，不删除原始内容。</p><p v-if="books.error" role="alert">{{books.error}}</p><footer><button type="button" class="product-text-button" :disabled="Boolean(books.busy || books.pending)" @click="archive">{{entry.detail.archived?'恢复笔记本':'归档笔记本'}}</button><button class="product-primary" :disabled="Boolean(books.busy || books.pending || !title.trim())">保存设置</button></footer></form></ProductDialog>
  </section><section v-else class="product-empty"><p v-if="books.error" role="alert">{{books.error}}</p><p v-else role="status">正在打开笔记本…</p><button class="product-secondary" @click="space.navigate('notebooks')">返回笔记本列表</button></section>
</template>
