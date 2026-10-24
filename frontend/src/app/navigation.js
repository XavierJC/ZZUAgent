export const studentTabs = [
  { id: 'study', name: '资料学习', icon: 'book' },
  { id: 'practice', name: '练习', icon: 'check' },
  { id: 'insights', name: '学习进度', icon: 'target' },
]
export const builderTabs = [
  { id: 'builder', name: '课程概览', icon: 'home' },
  { id: 'materials', name: '课程资料', icon: 'book' },
  { id: 'architecture', name: '知识体系', icon: 'book' },
  { id: 'bank', name: '习题管理', icon: 'book' },
  { id: 'publish', name: '课程审核与发布', icon: 'check' },
]
export const auxiliaryTabs = [
  { id: 'learn', name: '正式学习与复习', icon: 'home' },
  { id: 'notes', name: '我的笔记', icon: 'book' },
  { id: 'history', name: '学习记录', icon: 'history' },
  { id: 'resources', name: '原文资料', icon: 'book' },
]
export const headings = {
  study: ['围绕资料，弄懂一个问题。', '选择资料提问，点击引用回到原文。'],
  practice: ['练习，让理解落地。', '导入习题，自动整理，直接开始练习。'],
  insights: ['知道下一步学什么。', '把正式测评、自评和学习建议放在一起。'],
  notes: ['把理解，写成自己的笔记。', '记录理解，保存原文、公式与知识点关联。'],
  learn: ['把理解，再向前推进一步。', '正式诊断和复测提供客观学习证据。'],
  history: ['回看走过的每一步。', '从答题反馈中发现变化。'],
  materials: ['把课程资料放在一起。', '上传、查看原件和解析，整理课程知识结构。'],
  bank: ['识别、校对，再开始练习。', '保留原题型与来源，普通练习独立保存。'],
  builder: ['准备这门课程。', '资料、知识体系和习题各自保存，通过发布版本关联。'],
  publish: ['核对内容，再发布。', '发布保留来源版本，不改变已有学习事实。'],
  architecture: ['梳理课程知识。', '概念导航独立于正式BKT知识点。'],
  resources: ['回到资料原文。', '查看当前资料和可读解析，保留来源位置。'],
}
