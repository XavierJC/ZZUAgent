<script setup>
import { questionTypes, emptyQuestion } from './types.js'
const props = defineProps({ value: Object, prefix: { type: String, default: 'pb' }, child: Boolean })
function changeType() {
  props.value.answer = null
  if (props.value.question_type === 'true_false') props.value.options = [{ key: 'true', text: '正确' }, { key: 'false', text: '错误' }]
  else if (!['single_choice','multiple_choice'].includes(props.value.question_type)) props.value.options = []
  else if (!props.value.options.length || props.value.options[0].key === 'true') props.value.options = [{ key: 'A', text: '' }, { key: 'B', text: '' }]
}
</script>
<template>
  <label :for="`${prefix}-number`">原题号</label><input :id="`${prefix}-number`" v-model="value.number" maxlength="40" />
  <label :for="`${prefix}-kind`">题型</label><select :id="`${prefix}-kind`" v-model="value.question_type" @change="changeType"><option v-for="(name,key) in questionTypes" :key="key" :value="key">{{ name }}</option></select>
  <label :for="`${prefix}-context`">共享材料 / 共有条件</label><textarea :id="`${prefix}-context`" v-model="value.shared_context" rows="3" maxlength="16000" />
  <label :for="`${prefix}-stem`">题干 Markdown / LaTeX</label><textarea :id="`${prefix}-stem`" v-model="value.stem" rows="7" maxlength="16000" required />
  <div v-for="(o,index) in value.options" :key="index" class="pb-option"><label :for="`${prefix}-option-key-${index}`">选项标识</label><input :id="`${prefix}-option-key-${index}`" v-model="o.key" maxlength="8" /><label :for="`${prefix}-option-${index}`">选项内容</label><textarea :id="`${prefix}-option-${index}`" v-model="o.text" rows="2" maxlength="4000" /><button type="button" class="wb-text-button" @click="value.options.splice(index,1)">移除此选项</button></div>
  <button v-if="['single_choice','multiple_choice'].includes(value.question_type) && value.options.length<12" type="button" class="button secondary" @click="value.options.push({ key: String.fromCharCode(65+value.options.length), text: '' })">增加选项</button>
  <template v-if="['single_choice','true_false'].includes(value.question_type)"><label :for="`${prefix}-answer`">原文答案键（未知请留空）</label><select :id="`${prefix}-answer`" v-model="value.answer"><option :value="null">未知 / 无可靠答案</option><option v-for="o in value.options" :key="o.key" :value="o.key">{{ o.key }}</option></select></template>
  <fieldset v-if="value.question_type === 'multiple_choice'"><legend>原文多选答案键（本轮不自动判分）</legend><label v-for="o in value.options" :key="o.key"><input v-model="value.answer_keys" type="checkbox" :value="o.key" />{{ o.key }}</label></fieldset>
  <label :for="`${prefix}-answer-text`">原文 / 人工参考答案文字（识别时不自动解题）</label><textarea :id="`${prefix}-answer-text`" v-model="value.answer_text" rows="4" maxlength="16000" />
  <label :for="`${prefix}-explanation`">原文或人工核对解析</label><textarea :id="`${prefix}-explanation`" v-model="value.explanation" rows="4" maxlength="16000" />
  <fieldset v-if="!child"><legend>子问（共享父题条件）</legend><section v-for="(sub,index) in value.subquestions" :key="index" class="panel"><h4>子问 {{ index+1 }}</h4><QuestionFields :value="sub" :prefix="`${prefix}-sub-${index}`" child /><button type="button" class="button secondary" @click="value.subquestions.splice(index,1)">移除此子问</button></section><button v-if="value.subquestions?.length<20" type="button" class="button secondary" @click="value.subquestions.push(emptyQuestion())">增加子问</button></fieldset>
  <label :for="`${prefix}-dependencies`">图表 / 外部材料依赖（每行一项）</label><textarea :id="`${prefix}-dependencies`" :value="(value.dependencies || []).join('\n')" rows="2" @input="value.dependencies = $event.target.value.split('\n').filter(Boolean)" />
  <label :for="`${prefix}-issues`">具体缺项及待核对事项（每行一项）</label><textarea :id="`${prefix}-issues`" :value="(value.issues || []).join('\n')" rows="2" @input="value.issues = $event.target.value.split('\n').filter(Boolean)" />
  <p v-if="value.dependencies?.length" class="alert alert-info">依赖原图/材料：{{ value.dependencies.join('；') }}</p><p v-if="value.issues?.length" class="wb-run-notice">待校对：{{ value.issues.join('；') }}</p>
</template>
