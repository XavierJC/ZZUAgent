<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import LearningOverview from '../../views/LearningOverview.vue'
import PracticeModes from '../practice/PracticeModes.vue'
import QuestionPanel from '../../components/QuestionPanel.vue'
import MasteryPanel from '../../components/MasteryPanel.vue'
import ReviewPracticePanel from '../../components/ReviewPracticePanel.vue'
import Icon from '../../components/Icon.vue'
const space = useCurrentCourseSpace()
const w=space.w, flow=space.flow, working=ref(false)
const bank=computed(()=>flow.data?.assessment_bank)
const busy=computed(()=>working.value || w.busy || flow.busy)
const blocked=computed(()=>busy.value || flow.pending || w.pending)
const next=computed(()=>flow.data?.next_task)
const canContinue=computed(()=>!['finish','stopped'].includes(next.value?.action))
let alive=true
onUnmounted(()=>{alive=false})
onMounted(async()=>{if(space.modern && alive)await flow.load()})
async function beginDiagnosis(){
  if(blocked.value)return
  const owner=w.student
  working.value=true
  try{
    if(!flow.session && !await flow.begin())return
    if(!alive || owner!==w.student)return
    await flow.allocate()
  }finally{working.value=false}
}
</script>
<template>
  <LearningOverview v-if="!space.modern" :w="w" :review="space.features.review" :flow="flow" :self-workspace="space.features.assessment" @navigate="space.navigate" @explain="space.explainNext" />
  <section v-else class="simple-diagnosis">
    <PracticeModes active="learn" @navigate="space.navigate" />
    <header class="simple-diagnosis-heading"><div><p class="product-kicker">了解自己，学得更有方向</p><h1>测一下</h1><p>根据你的答题安排下一步，提交后更新掌握情况。</p></div><button class="product-text-button" @click="space.navigate('insights')">看看学习进度<Icon name="arrow" :size="16" /></button></header>
    <p v-if="flow.error || w.error" class="product-message error" role="alert">{{flow.error || w.error}}</p>
    <p v-if="flow.notice" class="product-message" role="status">{{flow.notice}}</p>
    <section v-if="flow.pending" class="product-message" role="status"><strong>正在确认上次操作的结果</strong><p>先查看结果，避免重复作答。</p><button class="product-secondary" @click="flow.load()">查看结果</button><details><summary>仍未查到结果？</summary><button class="product-text-button" :disabled="Boolean(flow.busy)" @click="flow.retryPending()">用原编号重试</button><button class="product-text-button" @click="flow.releasePending()">保留记录，稍后处理</button></details></section>
    <div class="diagnosis-summary"><span><Icon name="book" :size="17" />{{w.snapshot?.goals.length===w.knowledge.length?'机器学习 · 全部知识点':space.goalsText || '机器学习'}}</span><span>已完成 {{w.snapshot?.revision || 0}} 次作答</span><span v-if="bank">{{bank.question_count}} 道可用题目</span></div>
    <ReviewPracticePanel v-if="space.features.review?.active && !w.pending && !flow.pending" :review="space.features.review" :topic-name="w.topicName" @explain="space.explainNext" @navigate="space.navigate" />
    <QuestionPanel v-else-if="w.decision || w.feedback || w.pending" :decision="w.decision" :selected="w.selected" :feedback="w.feedback" :pending="w.pending" :busy="busy || flow.pending?'working':''" :topic="w.activeTopic" :can-review="space.features.review?.enabled" @select="w.selected=$event" @submit="flow.session?flow.submit():w.submit()" @next="beginDiagnosis" @review="space.features.review.open()" @explain="space.explainNext" @navigate="space.navigate" />
    <section v-else class="diagnosis-start panel"><span class="diagnosis-start-icon"><Icon name="target" :size="30" /></span><h2>{{canContinue?'从一道题开始':'先看看这次的学习情况'}}</h2><p>{{next?.reason || '系统会结合已有答题记录，为你选择合适的题目。'}}</p><button v-if="canContinue" class="product-primary" :disabled="Boolean(blocked)" @click="beginDiagnosis">{{working?'正在准备…':w.snapshot?.revision?'继续测一下':'开始测一下'}}<Icon name="arrow" :size="17" /></button><button v-else class="product-primary" @click="space.navigate('insights')">查看学习进度</button><p class="product-help">可以中途离开，已提交的作答会保存。</p></section>
    <div class="diagnosis-secondary"><button class="product-text-button" @click="space.explainNext()"><Icon name="spark" :size="16" />有不明白的，请 AI 讲解</button><button class="product-text-button" @click="space.navigate('history')">查看以前的作答</button></div>
    <details class="diagnosis-details"><summary>各知识点的学习情况</summary><MasteryPanel v-if="w.snapshot" :snapshot="w.snapshot" :current="w.decision?.knowledge_id" /></details>
    <details class="diagnosis-details"><summary>课程设置与测评说明</summary><p>掌握情况是基于答题的模型估计。自由练习、笔记和自评不会计入本次测评；已做过的题不会因刷新重复计分。</p><p v-if="bank">课程题 {{bank.shared_count}} 道，当前学习昵称下的个人题 {{bank.personal_count}} 道。AI检查与人工确认分别记录。</p><label for="diagnosis-release">课程版本</label><select id="diagnosis-release" v-model="flow.selectedRelease"><option v-for="release in flow.releases" :key="release.id" :value="release.id" :disabled="!release.usable">{{release.title}} · v{{release.release_version}}</option></select><button v-if="flow.session" class="product-text-button" :disabled="Boolean(blocked || w.decision?.question)" @click="flow.begin()">使用所选课程开始新会话</button></details>
  </section>
</template>
