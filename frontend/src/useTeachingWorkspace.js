import { ref, computed, watch } from 'vue'

export function useTeachingWorkspace(client,w,storage=localStorage) {
  const enabled=typeof client.courseWorkflow==='function'
  const releases=ref([]), data=ref(null), selectedRelease=ref(''), busy=ref(''), error=ref(''), notice=ref(''), pending=ref(null)
  const session=computed(()=>data.value?.session || null)
  let epoch=0,restored=false,sessionId=null,readSerial=0
  const key=()=>`eduagent.teaching.v1.${w.student}`
  const call=(path,method='GET',body,owner=w.student)=>client.courseWorkflow(owner,path,method,body)
  function persist() {
    if (!w.student)return true
    try {storage.setItem(key(),JSON.stringify({session_id:sessionId,selected_release:selectedRelease.value,pending:pending.value}));return true}
    catch {error.value='无法保留学习会话和请求编号，暂不提交。';return false}
  }
  watch(()=>w.student,()=>{epoch++;restored=false;data.value=null;sessionId=null;pending.value=null;releases.value=[];selectedRelease.value='';error.value='';busy.value='';if(!w.student)publicCourses()}, {flush:'sync'})
  async function publicCourses() {
    if (!enabled)return
    try { const value=await client.publishedCourses();if(!w.student){releases.value=value.items;if(!selectedRelease.value)selectedRelease.value=value.items.find(r=>r.usable)?.id || ''} }
    catch(e){error.value=e.message}
  }
  async function load() {
    if (!enabled || !w.student)return
    const token=epoch,owner=w.student,reading=++readSerial;error.value=''
    try {
      if(!restored){let saved=null;try{saved=JSON.parse(storage.getItem(key()) || 'null')}catch{};sessionId=w.pending?.session_id || saved?.session_id || null;pending.value=saved?.pending || null;selectedRelease.value=saved?.selected_release || selectedRelease.value;restored=true}
      if(pending.value){try {const receipt=await call(`course-workflow/requests/${pending.value.body.request_id}`,'GET',undefined,owner);if(token!==epoch)return;if(receipt.session_id)sessionId=receipt.session_id;if(pending.value.path.endsWith('/answers')){w.pending=null;w.remember?.()}pending.value=null;notice.value='已恢复原请求回执，没有重复提交或分配。'}catch{notice.value='原操作待核对，刷新只读回执，不会自动重试。'}}
      const [catalog,state]=await Promise.all([client.courseReleases(owner),call(sessionId?`teaching-sessions/${sessionId}`:'teaching-sessions','GET',undefined,owner)])
      if(token!==epoch || reading!==readSerial)return
      releases.value=catalog.items;data.value=state
      if(state.session){sessionId=state.session.id;selectedRelease.value=state.session.release_id;w.decision=state.decision;if(!w.pending)w.feedback=!state.decision || state.decision.decision_id===state.last_feedback?.decision_id ? state.last_feedback : null}
      else if(!selectedRelease.value)selectedRelease.value=catalog.items.find(r=>r.usable)?.id || ''
      persist()
    }catch(e){if(token===epoch)error.value=e.message}
  }
  async function execute(operation) {
    if(busy.value)return false
    const token=epoch,owner=w.student;busy.value='working';error.value=''
    try {
      const result=await call(operation.path,'POST',operation.body,owner)
      if(token!==epoch)return false
      pending.value=null;if(result.session_id)sessionId=result.session_id
      if(operation.path.endsWith('/answers')){w.pending=null;w.remember?.()}
      persist();await w.refresh();await load();return true
    }catch(e){if(token===epoch){error.value=e.message;if(e.status && e.status<500 && !e.uncertain)pending.value=null;persist()}return false}
    finally{if(token===epoch)busy.value=''}
  }
  function command(path,body) {
    if(pending.value){error.value='原操作待核对，请查询回执或明确重试原编号。';return false}
    const operation={path,body:{...body,request_id:crypto.randomUUID()}}
    pending.value=operation;if(!persist()){pending.value=null;return false}
    return execute(operation)
  }
  function begin(){if(w.pending){error.value='请先确认上一次正式作答。';return false}return command('teaching-sessions',{release_id:selectedRelease.value,goals:w.snapshot.goals})}
  function allocate(){if(!session.value)return false;return command(`teaching-sessions/${session.value.id}/next`,{expected_learning_revision:w.snapshot.revision})}
  function submit(){
    if(w.pending && !w.pending.session_id)return w.submit()
    if(pending.value)return execute(pending.value)
    if(!session.value || !w.decision?.question || !w.selected)return false
    return command(`teaching-sessions/${session.value.id}/answers`,{decision_id:w.decision.decision_id,answer:w.selected})
  }
  return {enabled,releases,data,session,selectedRelease,busy,error,notice,pending,persist,publicCourses,load,begin,allocate,submit,
    retryPending:()=>pending.value && execute(pending.value),
    releasePending:()=>{if(!pending.value)return;try{storage.setItem(key()+'.unconfirmed.'+pending.value.body.request_id,JSON.stringify(pending.value));pending.value=null;persist();notice.value='原编号另存本机待核对副本。结束等待不表示原操作未执行。'}catch{error.value='未能保留编号，继续等待。'}}}
}
