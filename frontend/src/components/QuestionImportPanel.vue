<script setup>
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
const props=defineProps({workspace:Object,documents:Object})
const emit=defineEmits(['ready'])
const id=useId(), entry=ref('file'), resourceId=ref(''), pages=ref(''), consent=ref(false), working=ref(false), error=ref(''), images=ref(true)
const stage=ref('')
let alive=true, ownerAtMount, timer
const available=computed(()=>props.workspace.resources.filter(r=>r.status==='active' && r.original_source_type==='document'))
async function refresh(){if(working.value || props.workspace.busy)return;try{await props.workspace.loadTasks();await props.workspace.refreshList()}catch(e){error.value=e.message}}
onMounted(async()=>{ownerAtMount=props.workspace.owner;if(!props.documents?.supported)entry.value='text';await props.workspace.load();if(props.documents?.supported)await props.documents.load();await refresh();if(alive)timer=setInterval(()=>{if(props.workspace.tasks.some(t=>t.status==='running'))refresh()},1500)})
onUnmounted(()=>{alive=false;clearInterval(timer)})
function choose(event){const d=props.documents;d.file=event.target.files?.[0] || null;if(d.file)d.title=d.file.name.replace(/\.[^.]+$/,'').slice(0,120);consent.value=false}
async function submit(){
  if(working.value || props.workspace.pending)return
  const w=props.workspace,d=props.documents,owner=w.owner,kind=entry.value,allowed=consent.value,model=w.extractionMode==='model',raw=w.paste,original=available.value.find(r=>r.resource_id===resourceId.value)
  const requested=pages.value.trim()?pages.value.split(/[,，\s]+/).map(Number):null
  const useImages=images.value
  if(model && !allowed){error.value='请同意本轮识别选定的原文或页面。';return}
  if(requested && (requested.length>3 || requested.some(v=>!Number.isInteger(v)||v<1) || requested.some((v,i)=>i && v!==requested[i-1]+1))){error.value='每轮请选择最多3个相邻页，例如1,2,3。';return}
  const current=()=>alive && owner===w.owner && ownerAtMount===owner
  working.value=true;error.value='';consent.value=false;stage.value='准备选定的习题原文'
  try{
    if(kind==='text'){if(!raw.trim())throw Error('请粘贴习题原文。');w.paste=raw;w.includeImages=false}
    else{
      let item=original
      if(kind==='file'){
        stage.value='上传并在本地解析文件'
        if(!d?.file || !d.rights)throw Error('请选择文件，并确认有权在本机处理。')
        if(!await d.upload())throw Error(d.error || '上传结果待确认，请查询原请求。')
        if(!current())return
        const docId=d.current.id,version=d.current.version.id
        for(let i=0;i<30 && ['pending','processing'].includes(d.current?.parse.status);i++){await new Promise(resolve=>setTimeout(resolve,500));if(!current())return;await d.load()}
        if(!current())return
        if(d.current?.id!==docId || d.current.version.id!==version)throw Error('资料版本已变化，请重新选择后识别。')
        if(!['ready','partial','empty'].includes(d.current.parse.status))throw Error('本地解析尚未完成。文件已保存，可稍后从已有资料继续，不会自动发送模型。')
        await w.refreshList();if(!current())return
        item=available.value.find(r=>r.original_source_id===docId && r.source_version===version)
      }
      if(!item)throw Error('请选择已保存的资料。')
      const version=item.source_version
      await w.selectResource(item);if(!current())return
      if(w.resource.source_version!==version)throw Error('资料版本已变化，请重新选择。')
      const ordinals=requested || w.sourceUnits.slice(0,3).map(u=>u.ordinal || u.location?.page_number || u.location?.slide_number)
      if(!ordinals.length)throw Error('资料没有可识别的页面，请查看原件和解析状态。')
      w.ordinals=ordinals.join(',');w.includeImages=model && useImages && ['pdf','png','jpg','jpeg','webp'].includes(item.format)
    }
    if(!current())return
    stage.value=model?'提交选定内容，等待AI识别整理':'在本地识别和检查题目结构'
    w.autoImport=true;w.extractionConsent=model && allowed
    const ok=kind==='text'?await w.extractText():await w.extractResource()
    if(!ok)throw Error(w.error || '处理结果待确认，请查询原请求。')
    if(current()){await refreshAfterSubmit();stage.value=model?'识别任务已登记，结果将在下方显示':'本地整理已完成，请查看可练与待处理题目'}
  }catch(e){if(current())error.value=e.message}finally{if(current())working.value=false}
}
async function refreshAfterSubmit(){try{await props.workspace.loadTasks();await props.workspace.refreshList()}catch(e){error.value=e.message}}
</script>
<template>
  <section class="panel simple-import" aria-label="导入并整理习题">
    <h2>导入习题，准备练习</h2><p>完整题目自动入库，缺项和冲突留待处理；AI整理不代表人工核验。</p>
    <form @submit.prevent="submit"><fieldset :disabled="working || Boolean(workspace.pending || workspace.busy)">
      <label :for="`${id}-entry`">习题来源</label><select :id="`${id}-entry`" v-model="entry" @change="consent=false"><option v-if="documents?.supported" value="file">上传文件或图片</option><option value="existing">已有资料</option><option value="text">粘贴文字</option></select>
      <template v-if="entry==='file' && documents?.supported"><label :for="`${id}-file`">PDF / PPTX / MD / TXT / 图片</label><input :id="`${id}-file`" type="file" accept=".pdf,.pptx,.md,.txt,.png,.jpg,.jpeg,.webp" @change="choose" /><p v-if="documents.file">{{documents.file.name}}</p><label class="pb-check"><input v-model="documents.rights" type="checkbox" />我有权在本机保存和处理该文件</label></template>
      <template v-else-if="entry==='existing'"><label :for="`${id}-source`">选择文件</label><select :id="`${id}-source`" v-model="resourceId" @change="consent=false"><option value="">请选择</option><option v-for="r in available" :key="r.resource_id" :value="r.resource_id">{{r.title}}</option></select></template>
      <template v-else-if="entry==='text'"><label :for="`${id}-text`">习题原文</label><textarea :id="`${id}-text`" v-model="workspace.paste" rows="6" maxlength="18000" @input="consent=false" /></template>
      <template v-if="entry!=='text'"><label :for="`${id}-pages`">本轮页码（默认前3页）</label><input :id="`${id}-pages`" v-model="pages" placeholder="例如 1,2,3" @input="consent=false" /><p class="small muted">每轮最多3个相邻页；其余页面不会发送。图片按第1页处理。</p></template>
      <details><summary>识别设置</summary><label :for="`${id}-mode`">识别方式</label><select :id="`${id}-mode`" v-model="workspace.extractionMode" @change="consent=false"><option value="model">AI识别 · DeepSeek</option><option value="local">本地规则 · 不外发</option></select><label v-if="entry!=='text'" class="pb-check"><input v-model="images" type="checkbox" @change="consent=false" />PDF/图片同时识别原页图</label><p class="small muted">PDF/PPTX/图片≤20MiB，PDF/PPTX≤200页；MD/TXT≤2MiB。每轮最多2次模型调用，不自动重发执行不明的请求。</p></details>
      <label v-if="workspace.extractionMode==='model'" class="pb-check"><input v-model="consent" type="checkbox" />我有权外发，并同意本轮将上述选定页（默认前3页）的原文和勾选原图，或粘贴的文字发送至DeepSeek识别，按量计费</label>
      <button class="button primary" :disabled="workspace.extractionMode==='model' && !consent">{{working?'正在导入整理…':'导入并自动整理'}}</button>
    </fieldset></form>
    <p v-if="stage" class="import-stage" role="status">{{stage}}</p><p v-if="error" class="alert alert-error" role="alert">{{error}}</p><p v-if="workspace.notice" role="status">{{workspace.notice}}</p>
    <div v-if="workspace.pending" role="status"><p>原操作待确认，刷新只查询，不重新识别。</p><button class="button secondary" @click="workspace.load()">查询原操作</button></div>
    <div v-for="task in workspace.tasks.slice(0,5)" :key="task.request_id" class="source-card"><strong>{{task.source.title}}</strong><p>{{task.status==='running'?'正在识别并检查原题，离开页面后任务仍可查询':task.status==='complete'?'整理完成':task.status==='uncertain'?'执行待确认，不自动重发':'识别未完成，请查看原记录'}}</p><p v-if="task.result.intake">可练 {{task.result.intake.ready}} · 待处理 {{task.result.intake.needs_attention}} · 重复 {{task.result.intake.duplicate}}</p><button v-if="task.result.intake?.ready" class="button primary" @click="emit('ready')">查看已整理题目</button><p v-if="task.result.error_code">{{task.result.message}}</p></div>
  </section>
</template>
