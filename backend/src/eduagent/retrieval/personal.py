"""Small sparse TF-IDF index. Inputs must already be scoped and versioned.

No global cache, FAISS files, provider client or training. The shared tokenizer,
log TF, smoothed IDF, cosine threshold and phrase guard match the course baseline.
"""

from collections import Counter
import math

from eduagent.domain.notes import NoteTooLarge
from eduagent.retrieval.lexical import informative_phrases, terms

MAX_SEARCH_CHUNKS, MAX_TERMS = 256, 8192


def search_personal(chunks: list[dict], query: str, top_k: int) -> list[dict]:
    if len(chunks) > MAX_SEARCH_CHUNKS:
        raise NoteTooLarge('本次所选笔记超过256片段，请缩小来源范围')
    counters = [Counter(terms(f"{p['title']} {p['section']} {p['content_text']}")) for p in chunks]
    vocabulary = set().union(*counters) if counters else set()
    if len(vocabulary) > MAX_TERMS:
        raise NoteTooLarge('本次所选笔记超过8192词项，请缩小来源范围')
    document_frequency = Counter(term for counts in counters for term in counts)
    idf = {term: math.log((1 + len(chunks)) / (1 + frequency)) + 1 for term, frequency in document_frequency.items()}

    def vector(counts):
        values = {term: (1 + math.log(count)) * idf[term] for term, count in counts.items() if term in idf}
        norm = math.sqrt(sum(value * value for value in values.values()))
        return {term: value / norm for term, value in values.items()} if norm else {}

    question = vector(Counter(terms(query)))
    phrases = informative_phrases(query)
    result = []
    for chunk, counts in zip(chunks, counters):
        candidate = vector(counts)
        score = sum(value * candidate.get(term, 0) for term, value in question.items())
        if score >= 0.12 and phrases.intersection(informative_phrases(f"{chunk['title']} {chunk['section']} {chunk['content_text']}")):
            result.append({**chunk, 'retrieval_score': score})
    return sorted(result, key=lambda p: (-p['retrieval_score'], p['chunk_id']))[:top_k]
