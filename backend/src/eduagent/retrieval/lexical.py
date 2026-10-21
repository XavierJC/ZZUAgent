"""Shared lexical rules; moving these does not change the course baseline."""

import re

def terms(text: str) -> list[str]:
    result = re.findall(r"[a-z][a-z0-9_]*", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(run)
        result.extend(run[i:i + 2] for i in range(len(run) - 1))
    return result


# Generic connective/request language is not evidence of a course topic. This
# is a lexical guard, NOT a semantic relevance classifier or an intent model.
PHRASE_STOPWORDS = frozenset({
    "什么", "为什", "如何", "怎么", "是否", "可以", "不能", "一个", "哪些", "应该",
    "需要", "使用", "进行", "对于", "这个", "这里", "哪里", "时候", "现在", "我们",
    "我的", "你的", "学习", "课程", "知识", "问题", "解释", "说明", "方法", "全部",
    "the", "what", "how", "is", "are", "do", "does", "can", "for", "to", "in", "and",
    "of", "on", "an", "as", "this", "you", "my", "be", "it",
})


def informative_phrases(text: str) -> frozenset[str]:
    phrases = set(re.findall(r"[a-z][a-z0-9_]+", text.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        phrases.update(run[i:i + 2] for i in range(len(run) - 1))
    return frozenset(phrases - PHRASE_STOPWORDS)


