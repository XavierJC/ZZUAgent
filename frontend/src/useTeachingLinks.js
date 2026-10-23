import { ref, watch } from 'vue'
export function useTeachingLinks(client,student,storage=localStorage){
  const items=ref([]),catalog=ref(null),busy=ref(false),error=ref(''),notice=ref(''),pending=ref(null)
  const draft=ref({document_id:'',run_id:'',ordinal:1,architecture_id:'',concept_id:'',start_offset:0,end_offset:1,excerpt_md:''})
  let epoch=0,restored=false
  const key=()=>`eduagent.teaching-links.v1.${student.value}`
  function persist(){if(!student.value)return true;try{storage.setItem(key(),JSON.stringify({draft:draft.value,pending:pending.value}));return true}catch{error.value='无法保留片段审核草稿，暂不提交。';return false}}
  watch(draft,()=>{if(restored)persist()},{deep:true})
  watch(student,()=>{epoch++;items.value=[];catalog.value=null;pending.value=null;restored=false;error.value='';notice.value='';busy.value=false;draft.value={document_id:'',run_id:'',ordinal:1,architecture_id:'',concept_id:'',start_offset:0,end_offset:1,excerpt_md:''}},{flush:'sync'})
  async function load(){
    if(!student.value || !client.teachingLinks)return
    const token=epoch,owner=student.value
    try{
      if(!restored){try{const s=JSON.parse(storage.getItem(key())||'null');if(s){draft.value=s.draft;pending.value=s.pending}}catch{};restored=true}
      if(pending.value){try{await client.courseWorkflow(owner,`teaching-material-links/requests/${pending.value.body.request_id}`);if(token!==epoch)return;pending.value=null;persist();notice.value='已读取原回执，没有重复提交。'}catch{notice.value='原操作待核对，刷新不自动重发。'}}
      const [a,b]=await Promise.all([client.teachingLinks(owner),client.courseBuilder(owner)])
      if(token===epoch){items.value=a.items;catalog.value=b}
    }catch(e){if(token===epoch)error.value=e.message}
  }
  async function execute(){if(!pending.value||busy.value)return;const token=epoch,owner=student.value;busy.value=true;error.value=''
    try{await client.courseWorkflow(owner,pending.value.path,pending.value.method,pending.value.body);if(token!==epoch)return;pending.value=null;persist();notice.value='操作已保存；只有明确核对并确认的片段参与检索。';await load()}
    catch(e){if(token===epoch){error.value=e.message;if(e.status&&e.status<500&&!e.uncertain)pending.value=null;persist()}}
    finally{if(token===epoch)busy.value=false}
  }
  function write(path,method,body){if(pending.value){error.value='请先核对原请求回执。';return}pending.value={path,method,body:{...body,request_id:crypto.randomUUID()}};if(!persist()){pending.value=null;return}return execute()}
  return {items,catalog,busy,error,notice,pending,draft,persist,load,retry:execute,
    create:()=>write('teaching-material-links','POST',draft.value),
    review:(row,version,reviewer,confirmed)=>write(`teaching-material-links/${row.id}/review`,'PUT',{expected_revision:row.revision,architecture_version:version,reviewer,confirmed})}
}
