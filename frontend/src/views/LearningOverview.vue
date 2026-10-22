<script setup>
import { onMounted } from 'vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import Icon from '../components/Icon.vue'
import QuestionPanel from '../components/QuestionPanel.vue'
import TutorPanel from '../components/TutorPanel.vue'
import MasteryPanel from '../components/MasteryPanel.vue'
const props=defineProps({ w: Object, selfWorkspace: Object })
onMounted(() => props.selfWorkspace?.load())
defineEmits(['navigate'])
</script>
          <template>
            <button class="button secondary" @click="$emit('navigate','history')">查看正式学习记录</button><div class="stat-strip"><div><span class="stat-icon"><Icon name="check" /></span><p><strong>{{ w.snapshot.revision }}<small> 道</small></strong><span>已完成练习</span></p></div><div><span class="stat-icon"><Icon name="target" /></span><p><strong>{{ w.snapshot.goals.length }}<small> 个</small></strong><span>本次学习目标</span></p></div><div><span class="stat-icon"><Icon name="activity" /></span><p><strong class="stat-topic">{{ w.activeTopic }}</strong><span>当前学习方向</span></p></div></div>
            <div class="learning-grid"><div class="learning-main"><QuestionPanel :decision="w.decision" :selected="w.selected" :feedback="w.feedback" :pending="w.pending" :busy="w.busy" :topic="w.activeTopic" @select="w.selected = $event" @submit="w.submit()" @next="w.next()" /><TutorPanel :reply="w.tutor" :runs="w.tutorRuns" :busy="w.busy" :pending="w.pending" :enabled="Boolean(w.health?.agent_enabled)" :topic="w.activeTopic" @ask="w.ask" @view="w.tutor = $event" /></div><MasteryPanel :snapshot="w.snapshot" :current="w.decision?.knowledge_id" /></div>
          <LearningGuidancePanel :overview="selfWorkspace?.overview" @navigate="$emit('navigate',$event)" />
<button class="button secondary" @click="$emit('navigate','study')">编辑自评与学习指南</button>
</template>
