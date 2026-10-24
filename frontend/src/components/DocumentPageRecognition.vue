<script setup>
import { onMounted,onUnmounted,ref,useId } from 'vue'
const props=defineProps({workspace:Object,source:Object})
const emit=defineEmits(['ready','close'])
const id=useId(),error=ref(''),job=ref(null)
let timer,alive=true
async function refresh(){
  if(props.workspace.busy)return
  await props.workspace.load()
  if(!alive)return
  if(props.workspace.current?.id!==props.source.source_id)await props.workspace.select(props.source.source_id)
  if(!alive)return
  const run=props.workspace.runs.find(r=>r.id===job.value)
  if(run && !['pending','processing'].includes(run.status)){
    job.value=null
    if(['ready','partial'].includes(run.status))emit('ready',props.source.source_id)
    else error.value=run.status==='uncertain'?'原识别执行待确认，不自动重新发送。':'本轮未取得可用转录，原件保留。'
  }
}
async function identify(){
  if(props.workspace.current?.id!==props.source.source_id || props.workspace.current?.version?.id!==props.source.version_id || props.workspace.current?.revision!==props.source.source_revision){error.value='当前资料版本已经变化，请刷新来源并重新同意。';return}
  if(await props.workspace.vision())job.value=props.workspace.run?.id
}
onMounted(async()=>{props.workspace.pages='';props.workspace.consent=false;await props.workspace.select(props.source.source_id);if(alive)timer=setInterval(()=>{if(job.value)refresh()},1500)})
onUnmounted(()=>{alive=false;clearInterval(timer)})
</script>
<template>
  <section class="wb-consent" aria-label="识别资料缺失页面"><strong>{{source.title}} · 页面识别</strong>
    <p>只发送本轮指定页的整页图片到DeepSeek，可能包含该页全部文字和图像。按量计费，每轮最多3页、每页最多3000输出token；不自动重发。</p>
    <label :for="`${id}-pages`">本轮PDF页码</label><input :id="`${id}-pages`" v-model="workspace.pages" placeholder="例如 11,12" :disabled="Boolean(job || workspace.busy)" />
    <label><input v-model="workspace.consent" type="checkbox" :disabled="Boolean(job || workspace.busy)" />我有权外发，并同意仅本轮将上述页面发送至DeepSeek识别</label>
    <p v-if="!workspace.capabilities?.vision_enabled">页面识别尚未启用；本地解析内容仍可使用。</p>
    <p v-if="workspace.error || error" role="alert">{{workspace.error || error}}</p><p v-if="job" role="status">正在识别所选页面，查询进度不会重新调用模型。</p>
    <button class="button primary" :disabled="Boolean(job || workspace.busy || workspace.pending || !workspace.consent || !workspace.pages.trim() || !workspace.capabilities?.vision_enabled)" @click="identify">识别选定页面</button><button class="wb-text-button" @click="emit('close')">收起页面识别</button>
  </section>
</template>
