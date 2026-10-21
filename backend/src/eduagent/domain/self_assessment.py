"""Subjective reports are ordinal labels, never BKT observations."""

from uuid import UUID

LEVEL_LABELS = {1: '不了解', 2: '理解概念', 3: '能够完成基础习题', 4: '能够独立应用'}


def request_uuid(value):
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('request_id 必须是标准小写UUID') from None
    if result != value:
        raise ValueError('request_id 必须是标准小写UUID')
    return result


def assessment_items(items, catalog):
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        raise ValueError('每次保存1～5个知识点自评')
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) - {'knowledge_id', 'level', 'confidence'} or not {'knowledge_id', 'level'} <= set(item):
            raise ValueError('自评字段无效')
        key, level, confidence = item['knowledge_id'], item['level'], item.get('confidence')
        if not isinstance(key, str) or key not in catalog.knowledge or key in seen:
            raise ValueError('知识点不存在或重复')
        if type(level) is not int or level not in LEVEL_LABELS:
            raise ValueError('自评等级必须为1～4')
        if confidence is not None and (type(confidence) is not int or not 1 <= confidence <= 5):
            raise ValueError('信心必须为空或1～5')
        seen.add(key)
        result.append(dict(knowledge_id=key, level=level, confidence=confidence))
    return sorted(result, key=lambda item: item['knowledge_id'])
