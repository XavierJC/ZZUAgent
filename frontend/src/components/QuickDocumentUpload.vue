<script setup>
import { onMounted, onUnmounted, ref, useId } from 'vue'
const props=defineProps({workspace:Object})
const emit=defineEmits(['ready'])
const id=useId(), expanded=ref(false), input=ref(null)
let timer, pendingDoc=null, alive=true
function choose(event){const w=props.workspace;w.file=event.target.files?.[0] || null;if(w.file)w.title=w.file.name.replace(/\.[^.]+$/,'').slice(0,120)}
function ready(){const item=props.workspace.items.find(d=>d.id===pendingDoc);if(item && !['pending','processing'].includes(item.parse.status)){pendingDoc=null;emit('ready',item.id)}}
async function upload(){if(await props.workspace.upload()){pendingDoc=props.workspace.current?.id;if(input.value)input.value.value='';ready()}}
onMounted(async()=>{await props.workspace.load();if(alive)timer=setInterval(async()=>{if(props.workspace.activeJobs && !props.workspace.busy){await props.workspace.load();if(alive)ready()}},1500)})
onUnmounted(()=>{alive=false;clearInterval(timer)})
</script>
<template>
  <div class="quick-upload">
    <button class="button primary" :aria-expanded="expanded" @click="expanded=!expanded">添加学习资料</button>
    <form v-if="expanded" @submit.prevent="upload">
      <label :for="`${id}-file`">选择 PDF、PPTX、Markdown 或 TXT</label><input :id="`${id}-file`" ref="input" type="file" accept=".pdf,.pptx,.md,.txt" :disabled="Boolean(workspace.busy || workspace.pending)" @change="choose" />
      <p v-if="workspace.file" class="small">{{workspace.file.name}}</p>
      <label class="pb-check"><input v-model="workspace.rights" type="checkbox" />我有权在本机保存和处理这份资料</label>
      <p class="small muted">上传仅作本地解析；问答发送片段前会另行征求同意。PDF/PPTX最多20MiB、200页；MD/TXT最多2MiB、UTF-8。</p>
      <button class="button primary" :disabled="Boolean(workspace.busy || workspace.pending || !workspace.file || !workspace.rights)">{{workspace.busy?'正在处理…':'上传并准备问答'}}</button>
    </form>
    <p v-if="workspace.activeJobs" role="status">正在解析资料，可读内容就绪后会出现在来源列表。</p>
    <p v-if="workspace.error" class="alert alert-error" role="alert">{{workspace.error}}</p>
    <p v-if="workspace.notice" class="small" role="status">{{workspace.notice}}</p>
    <div v-if="workspace.pending" role="status"><p>原上传结果待确认，查询不会重新上传或调用模型。</p><button class="button secondary" @click="workspace.load()">查询原上传</button></div>
  </div>
</template>
