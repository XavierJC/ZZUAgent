// Navigation hints are read-only. Only stored concept IDs establish topic links.
export const topicQuestion = name => `请解释${name}的核心概念，结合所选资料举例，并指出常见误区。`

export function practiceCandidates(questions, knowledge, { resource = '', topic = '', query = '' } = {}) {
  const concepts = new Set((knowledge || []).flatMap(group => (group.concepts || [])
    .filter(concept => concept.formal_knowledge_ids?.includes(topic))
    .map(concept => `${group.architecture_id}:${concept.id}`)))
  const text = query.trim().toLocaleLowerCase()
  return (questions || []).filter(question => question.status === 'practice'
    && ['current', 'manual'].includes(question.source_status)
    && (!resource || question.source?.resource_id === resource)
    && (!topic || question.payload.concepts?.some(ref => concepts.has(`${ref.architecture_id}:${ref.concept_id}`)))
    && (!text || `${question.payload.stem} ${question.source?.title || ''}`.toLocaleLowerCase().includes(text)))
}

export const sourcePosition = source => source.page_number
  ? source.file_format === 'pptx' ? `幻灯片 ${source.page_number}` : ['md', 'txt'].includes(source.file_format)
    ? `文本单位 ${source.page_number}` : `第 ${source.page_number} 页`
  : source.start_line != null ? `行 ${source.start_line}–${source.end_line}` : '资料正文'
