<script setup>
import { computed } from 'vue'
import LegacyWelcome from './LegacyWelcome.vue'
import Icon from '../components/Icon.vue'
const props = defineProps({ space: Object })
const learner = computed({ get:()=>props.space.learnerId, set:v=>{props.space.learnerId=v} })
</script>
<template>
  <LegacyWelcome v-if="!space.modern || space.tab==='learn'" :space="space" />
  <section v-else class="product-welcome"><div class="product-welcome-icon"><Icon name="book" :size="32" /></div><p class="product-kicker">你的 AI 学习伙伴</p><h1>让资料有条理，<br />让学习有方向。</h1><p>把课件、习题与笔记放进一个笔记本。<br />围绕资料提问，在练习中检验理解。</p><form class="product-entry-form" @submit.prevent="space.start()"><div class="product-segment"><button type="button" :class="{active:space.formMode==='new'}" @click="space.formMode='new'">开始新的学习</button><button type="button" :class="{active:space.formMode==='restore'}" @click="space.formMode='restore'">恢复已有记录</button></div><label for="learner-id">学习标识</label><input id="learner-id" v-model="learner" required maxlength="128" placeholder="输入之前的标识或一个新昵称" /><p class="product-help">使用同一标识恢复本机资料与学习记录；这不是账号登录。</p><button class="product-primary" :disabled="Boolean(space.w.busy || !space.w.health)">{{space.w.busy==='start'?'正在打开…':'进入学习空间'}}<Icon name="arrow" :size="17" /></button></form></section>
</template>
