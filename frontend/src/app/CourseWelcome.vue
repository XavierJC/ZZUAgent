<script setup>
import { computed } from 'vue'
import LegacyWelcome from './LegacyWelcome.vue'
import Icon from '../components/Icon.vue'
const props = defineProps({ space: Object })
const learner = computed({ get:()=>props.space.learnerId, set:v=>{props.space.learnerId=v} })
</script>
<template>
  <LegacyWelcome v-if="!space.modern" :space="space" />
  <section v-else class="product-welcome"><div class="product-welcome-icon"><Icon name="book" :size="32" /></div><p class="product-kicker">你的 AI 学习伙伴</p><h1>{{space.tab==='learn'?'测一下，找到学习起点。':'今天想弄懂什么？'}}</h1><p>{{space.tab==='learn'?'回答几道题，看看接下来适合学什么。':'添加资料，向 AI 提问，随时练一练。'}}</p><form class="product-entry-form" @submit.prevent="space.start()"><div class="product-segment"><button type="button" :class="{active:space.formMode==='new'}" @click="space.formMode='new'">开始新的学习</button><button type="button" :class="{active:space.formMode==='restore'}" @click="space.formMode='restore'">继续以前的学习</button></div><template v-if="space.formMode==='restore'"><label for="learner-id">之前的学习昵称</label><input id="learner-id" v-model="learner" required maxlength="128" placeholder="输入之前使用的昵称" /></template><details v-else class="welcome-options"><summary>昵称和学习重点（可选）</summary><label for="learner-id">学习昵称</label><input id="learner-id" v-model="learner" required maxlength="128" /><p class="product-help">昵称已为你生成，也可以改成容易记住的名字。</p><fieldset><legend>想先学哪些内容？不选则覆盖整门课程</legend><label v-for="point in space.w.knowledge" :key="point.id" class="pb-check"><input v-model="space.goals" type="checkbox" :value="point.id" />{{point.name}}</label></fieldset></details><button class="product-primary" :disabled="Boolean(space.w.busy || !space.w.health)">{{space.w.busy==='start'?'正在打开…':space.tab==='learn'?'开始测一下':space.formMode==='restore'?'继续学习':'开始学习'}}<Icon name="arrow" :size="17" /></button><p class="product-help">资料和记录保存在本机；使用同一昵称可以继续学习。</p></form></section>
</template>
