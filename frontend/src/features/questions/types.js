export const questionTypes = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', fill_blank: '填空题', short_answer: '简答题', calculation: '计算题', proof: '证明题', unknown: '未确定', other: '旧版未分类' }
export const objective = value => ['single_choice', 'true_false'].includes(value?.question_type)
export const emptyQuestion = () => ({ number: '', question_type: 'short_answer', stem: '', options: [], answer: null, explanation: '', concepts: [], shared_context: '', answer_text: '', answer_keys: [], subquestions: [], dependencies: [], issues: [] })
