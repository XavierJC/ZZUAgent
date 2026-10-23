<script setup>
import { onMounted } from 'vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import Icon from '../components/Icon.vue'
import QuestionPanel from '../components/QuestionPanel.vue'
import TutorPanel from '../components/TutorPanel.vue'
import MasteryPanel from '../components/MasteryPanel.vue'
const props=defineProps({ w: Object, selfWorkspace: Object, flow:Object })
onMounted(() => props.selfWorkspace?.load())
defineEmits(['navigate','explain'])
</script>
          <template>
            <section v-if="flow?.enabled" class="panel phase5-builder" aria-label="当前学习任务">
              <h2>当前课程与下一步</h2><p v-if="flow.error" class="alert alert-error" role="alert">{{ flow.error }}</p><p v-if="flow.notice" role="status">{{ flow.notice }}</p>
              <label for="learning-release">已发布课程版本</label><select id="learning-release" v-model="flow.selectedRelease"><option v-for="r in flow.releases" :key="r.id" :value="r.id" :disabled="!r.usable">{{ r.title }} · v{{ r.release_version }} · {{ r.kind==='demo'?'工程演示':'已审核内容' }}</option></select>
              <p v-if="flow.data?.release">{{ flow.data.release.review_warning }}</p>
              <button class="button secondary" :disabled="Boolean(flow.busy || flow.pending || w.pending || flow.data?.decision?.question)" @click="flow.begin()">{{ flow.session ? '明确开始所选版本的新会话' : '进入课程并绑定学习目标' }}</button>
              <template v-if="flow.session"><p>目标：{{ w.snapshot.goals.map(w.topicName).join('、') }}</p><p>当前步骤：{{ {goals:'目标已保存，等待诊断',diagnosis:'正式诊断',analysis:'评分后学情分析',explanation:'资料讲解',verification:'正式复测'}[flow.session.stage] }}</p><p v-if="!flow.data.has_objective_evidence">待诊断：尚无客观答题证据。BKT先验不代表薄弱点结论。</p><p>{{ flow.data.next_task.reason }}</p>
                <p v-if="flow.data.decision_origin?.origin==='legacy_unbound'" class="small muted">当前分配来自旧流程，原发布版本未记录，不补认新版本。</p>
                <div class="phase5-actions"><button v-if="!w.decision?.question && !['finish','stopped'].includes(flow.data.next_task.action)" class="button primary" :disabled="Boolean(flow.busy || flow.pending || !flow.data.release.usable)" @click="flow.allocate()">明确开始诊断 / 正式复测</button><button class="button secondary" @click="$emit('explain')">围绕当前重点学习讲解</button><button class="button secondary" @click="$emit('navigate','insights')">查看学情、自评与目标</button><button class="button secondary" @click="$emit('navigate','practice')">普通练习（不更新BKT）</button></div>
              </template>
              <section v-if="flow.pending" role="status"><p>原操作结果待核对，不会因刷新自动分配或重交。</p><button class="button secondary" @click="flow.load()">只读查询原回执</button><button class="button secondary" @click="flow.retryPending()">明确重试原编号</button><button class="button secondary" @click="flow.releasePending()">保留编号并结束等待</button></section>
            </section>
            <button class="button secondary" @click="$emit('navigate','history')">查看正式学习记录</button><div class="stat-strip"><div><span class="stat-icon"><Icon name="check" /></span><p><strong>{{ w.snapshot.revision }}<small> 道</small></strong><span>已完成练习</span></p></div><div><span class="stat-icon"><Icon name="target" /></span><p><strong>{{ w.snapshot.goals.length }}<small> 个</small></strong><span>本次学习目标</span></p></div><div><span class="stat-icon"><Icon name="activity" /></span><p><strong class="stat-topic">{{ w.activeTopic }}</strong><span>当前学习方向</span></p></div></div>
            <div class="learning-grid"><div class="learning-main"><QuestionPanel v-if="w.decision || w.feedback || w.pending" :decision="w.decision" :selected="w.selected" :feedback="w.feedback" :pending="w.pending" :busy="w.busy || flow?.busy || (flow?.pending ? 'pending' : '')" :topic="w.activeTopic" @select="w.selected = $event" @submit="flow?.session ? flow.submit() : w.submit()" @next="flow?.session ? flow.allocate() : w.next()" /><details><summary>旧版助教与已保存讲解（未绑定课程发布的旧记录）</summary><TutorPanel :reply="w.tutor" :runs="w.tutorRuns" :busy="w.busy" :pending="w.pending" :enabled="Boolean(w.health?.agent_enabled)" :topic="w.activeTopic" @ask="w.ask" @view="w.tutor = $event" /></details></div><MasteryPanel :snapshot="w.snapshot" :current="w.decision?.knowledge_id" /></div>
          <LearningGuidancePanel :overview="flow?.data?.guidance || selfWorkspace?.overview" @navigate="$emit('navigate',$event)" />
<button class="button secondary" @click="$emit('navigate','insights')">编辑自评与学习指南</button>
</template>
