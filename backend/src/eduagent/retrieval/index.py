"""Tiny reproducible TF-IDF baseline searched by a FAISS inner-product index.

L2-normalized vectors make inner product equal cosine similarity. Chinese
unigrams/bigrams and English words provide a lexical baseline, not semantic
embeddings. The index is rebuilt from five small local sources at startup.
"""

from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re

import faiss
import numpy as np

from eduagent.retrieval.lexical import terms, informative_phrases, PHRASE_STOPWORDS


@dataclass(frozen=True)
class Passage:
    citation_id: str
    knowledge_id: str
    title: str
    section: str
    source: str
    content: str
    review_status: str
    score: float = 0.0


class CourseIndex:
    def __init__(self, material_dir: Path, knowledge_ids: set[str], *, phrase_gate: bool = True):
        if type(phrase_gate) is not bool:
            raise ValueError("phrase_gate 必须为布尔值")
        self.phrase_gate = phrase_gate
        self.passages: list[Passage] = []
        manifest = json.loads((material_dir / "manifest.json").read_text(encoding="utf-8"))
        seen: set[str] = set()
        for item in manifest["documents"]:
            document_id = item["id"]
            if not re.fullmatch(r"[a-z0-9_]+", document_id) or document_id in seen:
                raise ValueError("课程资料 ID 非法或重复")
            seen.add(document_id)
            if item["knowledge_id"] not in knowledge_ids:
                raise ValueError("课程资料引用未知知识点")
            root = material_dir.resolve()
            path = (root / item["file"]).resolve()
            if not path.is_relative_to(root) or path.suffix != ".md":
                raise ValueError("课程资料路径需位于 materials 目录中且为 Markdown")
            if item["review_status"] not in ("pending", "human_verified") or not item.get("license"):
                raise ValueError("课程资料需记录校验状态与使用许可")
            text = path.read_text(encoding="utf-8")
            sections = re.split(r"^## (.+)$", text, flags=re.M)
            for number, offset in enumerate(range(1, len(sections), 2), 1):
                content = sections[offset + 1].strip()
                if not content or len(content) > 3000:
                    raise ValueError("课程章节为空或过长")
                self.passages.append(Passage(
                    citation_id=f"{document_id}:{number}", knowledge_id=item["knowledge_id"],
                    title=item["title"], section=sections[offset].strip(),
                    source=f"materials/{item['file']}", content=content,
                    review_status=item["review_status"],
                ))
        if not self.passages:
            raise ValueError("课程资料没有可索引的二级标题章节")
        counters = [Counter(terms(p.title + " " + p.section + " " + p.content)) for p in self.passages]
        self.passage_phrases = [informative_phrases(p.title + " " + p.section + " " + p.content)
                                for p in self.passages]
        self.vocabulary = {term: i for i, term in enumerate(sorted(set().union(*counters)))}
        if not self.vocabulary:
            raise ValueError("课程资料缺少可索引词项")
        count = len(counters)
        self.idf = {term: math.log((1 + count) / (1 + sum(term in c for c in counters))) + 1
                    for term in self.vocabulary}
        self.index = faiss.IndexFlatIP(len(self.vocabulary))
        self.vectors = np.vstack([self._vector(counter) for counter in counters])
        self.index.add(self.vectors)

    @property
    def configuration(self) -> dict:
        return {"version": "tfidf-phrase-v2" if self.phrase_gate else "tfidf-v1",
                "minimum_cosine_score": 0.12, "require_informative_phrase": self.phrase_gate,
                "phrase_stopwords": sorted(PHRASE_STOPWORDS) if self.phrase_gate else []}

    def _vector(self, counts: Counter) -> np.ndarray:
        vector = np.zeros(len(self.vocabulary), dtype="float32")
        for term, count in counts.items():
            if term in self.vocabulary:
                vector[self.vocabulary[term]] = (1 + math.log(count)) * self.idf[term]
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def search(self, query: str, knowledge_id: str | None = None, top_k: int = 3,
               *, source_ids: frozenset[str] | None = None) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("检索问题必须为 1～1000 字符")
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise ValueError("检索数量需在 1～5 内")
        if knowledge_id is not None and knowledge_id not in {p.knowledge_id for p in self.passages}:
            raise ValueError("检索知识点无效")
        vector = self._vector(Counter(terms(query)))
        if not np.any(vector):
            return []
        phrases = informative_phrases(query)
        # Selected-source retrieval searches only allowed rows, using the unchanged
        # course vocabulary/IDF. The legacy call takes exactly the original path.
        mapping = list(range(len(self.passages))) if source_ids is None else [
            i for i, p in enumerate(self.passages) if p.citation_id.split(":")[0] in source_ids]
        if not mapping:
            return []
        index = self.index
        if len(mapping) != len(self.passages):
            index = faiss.IndexFlatIP(len(self.vocabulary))
            index.add(self.vectors[mapping])
        scores, positions = index.search(vector.reshape(1, -1), len(mapping))
        result = []
        for score, position in zip(scores[0], positions[0]):
            position = mapping[int(position)]
            passage = self.passages[position]
            if score < 0.12 or (knowledge_id is not None and passage.knowledge_id != knowledge_id):
                continue
            if self.phrase_gate and not phrases.intersection(self.passage_phrases[int(position)]):
                continue
            value = asdict(passage)
            value["score"] = float(score)
            result.append(value)
            if len(result) == top_k:
                break
        return result
