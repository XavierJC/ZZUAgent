<script setup>
import { computed, ref } from 'vue'
import { questionTypes } from '../questions/types.js'
const props = defineProps({ source: Object, bulk: Boolean, checked: Boolean, attached: Boolean, busy: Boolean, deletable: Boolean, updated: Boolean })
const emit = defineEmits(['toggle', 'add', 'delete'])
const confirming = ref(false)
const ready = computed(() => ['ready', 'empty'].includes(props.source.index_status))
const kind = computed(() => ({ course_material: '课程资料', uploaded_document: '上传资料 · 未核验', teaching_material: '已确认课件片段', personal_note: '个人笔记', personal_question: questionTypes[props.source.question_type] || '练习题' }[props.source.source_type]))
const status = computed(() => ({ ready: '已就绪', empty: '暂无正文', pending: '正在准备', failed: props.source.source_type === 'uploaded_document' ? '解析失败' : '暂不可用' }[props.source.index_status] || '未就绪'))
</script>
<template>
  <div class="notebook-picker-row" role="group" :aria-label="`资料：${source.title}`">
    <input v-if="bulk" type="checkbox" :checked="checked" :aria-label="`选择资料：${source.title}`" :disabled="busy || (!checked && !ready)" @change="emit('toggle', $event.target.checked)" />
    <span><strong>{{source.title}}</strong><small>{{kind}} · {{status}}</small><small v-if="updated">资料已有新版本。</small><p v-if="confirming" class="source-delete-confirm">删除这份资料？所有主题将停止使用，历史记录保留。</p></span>
    <div class="source-row-actions">
      <template v-if="confirming"><button class="product-text-button" :disabled="busy" @click="confirming=false">取消</button><button class="product-secondary source-delete-button" :disabled="busy" :aria-label="`确认删除资料：${source.title}`" @click="emit('delete')">{{busy?'正在删除…':'确认删除'}}</button></template>
      <template v-else><button v-if="!bulk" class="product-secondary" :disabled="busy || attached || !ready" @click="emit('add')">{{attached?'已加入':'加入主题'}}</button><button v-if="deletable && source.source_type==='uploaded_document'" class="product-text-button source-delete-button" :disabled="busy" :aria-label="`删除资料：${source.title}`" @click="confirming=true">删除</button></template>
    </div>
  </div>
</template>
