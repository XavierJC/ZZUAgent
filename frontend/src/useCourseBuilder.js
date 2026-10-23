import { computed, ref, watch } from 'vue'
const copy=v=>JSON.parse(JSON.stringify(v))
export function useCourseBuilder(client,student,storage=localStorage) {
  const catalog=ref(null),current=ref(null),editor=ref(null),baseline=ref(''),revision=ref(0),check=ref(null),confirmed=ref(false),kind=ref('demo'),busy=ref(''),error=ref(''),notice=ref(''),pending=ref(null),conflict=ref(false)
  const dirty=computed(()=>editor.value && JSON.stringify(editor.value)!==baseline.value),recoveries=ref([])
  let epoch=0,restored=false,drafts={},restoreId=null
  const cacheKey=()=>`eduagent.course-builder.v1.${student.value}`
  const api=(path,method='GET',body,owner=student.value)=>client.courseWorkflow(owner,path,method,body)
  function persist(){if(!student.value)return true;if(editor.value)drafts[current.value || 'new']={payload:copy(editor.value),baseline:baseline.value,revision:revision.value};recoveries.value=Object.keys(drafts).filter(k=>k.startsWith('recovery-'));try{storage.setItem(cacheKey(),JSON.stringify({current:current.value,drafts,pending:pending.value}));return true}catch{error.value='无法保留课程构建草稿，请勿离开。';return false}}
  watch(editor,()=>{check.value=null;confirmed.value=false;if(restored)persist()}, {deep:true,flush:'sync'})
  watch(student,()=>{epoch++;restored=false;catalog.value=null;current.value=null;editor.value=null;drafts={};restoreId=null;pending.value=null;busy.value='';error.value='';notice.value='';check.value=null;recoveries.value=[];conflict.value=false;confirmed.value=false}, {flush:'sync'})
  async function open(id,token=epoch){
    if(!persist())return
    const value=await api(`course-builder/drafts/${id}`);if(token!==epoch)return
    current.value=id;const local=drafts[id];revision.value=local?.revision || value.revision;baseline.value=local?.baseline || JSON.stringify(value.payload);editor.value=copy(local?.payload || value.payload)
    conflict.value=Boolean(local && local.revision!==value.revision);check.value=dirty.value ? null:value;confirmed.value=false;persist()
  }
  async function load(){
    if(!student.value || !client.courseBuilder)return
    const token=epoch,owner=student.value;error.value=''
    try{
      if(!restored){let saved=null;try{saved=JSON.parse(storage.getItem(cacheKey()) || 'null')}catch{};drafts=saved?.drafts || {};pending.value=saved?.pending || null;restoreId=saved?.current || null;restored=true}
      if(pending.value){try{const receipt=await api(`course-workflow/requests/${pending.value.body.request_id}`,'GET',undefined,owner);if(token!==epoch)return;if(receipt.draft_id){restoreId=receipt.draft_id;delete drafts[restoreId];delete drafts.new}pending.value=null;notice.value='已恢复原回执，未重复保存/发布。'}catch{notice.value='原操作待核对；刷新不会自动重发。'}}
      const value=await client.courseBuilder(owner);if(token!==epoch)return;catalog.value=value
      const id=restoreId || current.value;restoreId=null
      if(id && value.drafts.some(d=>d.id===id))await open(id,token)
      else if(drafts.new){current.value=null;editor.value=copy(drafts.new.payload);baseline.value=drafts.new.baseline;revision.value=0}
    }catch(e){if(token===epoch)error.value=e.message}
  }
  function fresh(){if(!persist() || !catalog.value)return;current.value=null;revision.value=0;editor.value=copy(drafts.new?.payload || {title:'机器学习课程',sources:catalog.value.course_sources.map(s=>({source_type:s.source_type,source_id:s.source_id,source_version:s.source_version})),reviewer:'',reviewed_question_ids:[],architecture_id:null,architecture_version:null});baseline.value=drafts.new?.baseline || '';conflict.value=false;check.value=null;confirmed.value=false;persist()}
  async function execute(op){
    if(busy.value)return
    const token=epoch,owner=student.value;busy.value='write';error.value=''
    try{const r=await api(op.path,op.method,op.body,owner);if(token!==epoch)return;pending.value=null;if(r.draft_id){delete drafts[current.value || 'new'];current.value=r.draft_id;editor.value=null;restoreId=r.draft_id}notice.value=r.release_id?'已发布不可变课程版本。旧学习事实保持。':'已保存草稿，尚未发布。';persist();await load()}
    catch(e){if(token===epoch){error.value=e.message;if(e.status && e.status<500 && !e.uncertain)pending.value=null;if(e.code==='revision_conflict')conflict.value=true;persist()}}
    finally{if(token===epoch)busy.value=''}
  }
  function write(path,method,body){if(pending.value){error.value='请先核对原请求。';return}pending.value={path,method,body:{...body,request_id:crypto.randomUUID()}};if(!persist()){pending.value=null;return}return execute(pending.value)}
  function save(){if(conflict.value){error.value='请保留本机副本并读取新版本后再合并。';return}return write(`course-builder/drafts${current.value?'/'+current.value:''}`,current.value?'PUT':'POST',{payload:copy(editor.value),...(current.value?{expected_revision:revision.value}:{})})}
  async function review(){if(dirty.value || !current.value)return;check.value=null;confirmed.value=false;try{check.value=await api(`course-builder/drafts/${current.value}`);confirmed.value=false}catch(e){error.value=e.message}}
  function publish(){if(!check.value || dirty.value || !confirmed.value || conflict.value)return;return write(`course-builder/drafts/${current.value}/publish`,'POST',{expected_revision:revision.value,snapshot_hash:check.value.snapshot_hash,kind:kind.value,confirmed:true})}
  function reloadServer(){if(!current.value || !persist())return;drafts['recovery-'+Date.now()]=copy(drafts[current.value]);delete drafts[current.value];editor.value=null;return open(current.value)}
  function restoreCopy(id){if(!persist() || !drafts[id])return;editor.value=copy(drafts[id].payload);check.value=null;notice.value='已恢复本机副本，请与服务器内容手工对照并重新检查发布条件。'}
  return {catalog,current,editor,revision,check,confirmed,kind,busy,error,notice,pending,conflict,dirty,load,open,fresh,persist,save,review,publish,reloadServer,recoveries,restoreCopy,retryPending:()=>pending.value && execute(pending.value)}
}
