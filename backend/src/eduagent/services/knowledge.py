"""Selected-source local retrieval; ownership/version validation precedes scoring."""

from hashlib import sha256
import json

from eduagent.domain import notes as rules
from eduagent.retrieval.note_chunks import INDEXER_VERSION
from eduagent.retrieval.personal import search_personal
from eduagent.services.learning import StudentNotFound, identifier
from eduagent.storage.personal import PersonalRepository


class SourceChanged(ValueError):
    pass


class IndexUnavailable(ValueError):
    pass


def note_version(note):
    return f"r{note['revision']}-{note['content_hash']}"


class CourseSources:
    def __init__(self, index, directory):
        self.index, self.directory = index, directory
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        self.manifest_hash = sha256((directory / 'manifest.json').read_bytes()).hexdigest()
        self.documents = {}
        self.locations = {}
        for document in manifest['documents']:
            text = (directory / document['file']).read_text(encoding='utf-8')
            raw_hash = sha256(text.encode()).hexdigest()
            version = sha256(json.dumps({'document': document, 'hash': raw_hash}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            self.documents[document['id']] = {**document, 'text': text, 'content_hash': raw_hash, 'source_version': version}
            cursor = 0
            for passage in index.passages:
                if passage.citation_id.split(':')[0] == document['id']:
                    start = text.find(passage.content, cursor)
                    if start < 0:
                        raise SourceChanged('课程资料已变化，请重启服务重建课程索引')
                    end = start + len(passage.content)
                    self.locations[passage.citation_id] = (start, end)
                    cursor = end

    def verify(self):
        try:
            current_manifest = sha256((self.directory / 'manifest.json').read_bytes()).hexdigest()
        except OSError:
            raise SourceChanged('课程来源目录已变化，请重启本地服务') from None
        if current_manifest != self.manifest_hash:
            raise SourceChanged('课程来源目录已变化，请重启本地服务')
        for document in self.documents.values():
            try:
                current = (self.directory / document['file']).read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                raise SourceChanged('课程来源已变化，请重启本地服务') from None
            if sha256(current.encode()).hexdigest() != document['content_hash']:
                raise SourceChanged('课程来源已变化，请重启本地服务')

    def sources(self):
        return [dict(source_type='course_material', source_id=key, source_version=value['source_version'],
            source_revision=None, content_hash=value['content_hash'], title=value['title'],
            knowledge_point_ids=[value['knowledge_id']], review_status=value['review_status'], index_status='ready', error_code=None)
            for key, value in self.documents.items()]

    def search(self, query, source_ids, knowledge_id, top_k):
        result = []
        for match in self.index.search(query, knowledge_id, top_k, source_ids=frozenset(source_ids)):
            key = match['citation_id'].split(':')[0]
            document = self.documents[key]
            start, end = self.locations[match['citation_id']]
            result.append(dict(source_type='course_material', source_id=key, source_version=document['source_version'],
                source_revision=None, content_hash=document['content_hash'], chunk_hash=sha256(match['content'].encode()).hexdigest(),
                chunk_id=match['citation_id'], citation_id=match['citation_id'], title=match['title'], section=match['section'],
                knowledge_point_ids=[match['knowledge_id']], review_status=match['review_status'], raw_md=match['content'],
                content_text=match['content'], start_offset=start, end_offset=end,
                start_line=document['text'].count('\n', 0, start) + 1,
                end_line=document['text'].count('\n', 0, end - 1) + 1, retrieval_score=match['score'], fusion_score=None))
        return result


class KnowledgeService:
    def __init__(self, catalog, repository, course_sources=None, enabled=True):
        self.catalog, self.repository = catalog, repository
        self.personal = PersonalRepository(repository)
        self.courses, self.enabled = course_sources, enabled
        from eduagent.services.teaching_sources import TeachingSources
        self.teachers = TeachingSources(repository)

    def student(self, student_id, course_id):
        identifier(student_id, '学生标识')
        rules.course(course_id)
        if self.repository.student(student_id) is None:
            raise StudentNotFound('学生标识不存在，请先创建学习记录')

    def sources(self, student_id, course_id=rules.COURSE_ID):
        with self.repository.transaction():
            self.student(student_id, course_id)
            if self.courses:
                self.courses.verify()
            items = self.courses.sources() if self.courses else []
            rows = self.personal.db.execute('SELECT * FROM notes WHERE student_id=? AND course_id=? AND deleted_at IS NULL ORDER BY id',
                                            (student_id, course_id)).fetchall()
            for row in rows:
                note = dict(row)
                state = self.personal.state(note['id'])
                items.append(dict(source_type='personal_note', source_id=note['id'], source_version=note_version(note),
                    source_revision=note['revision'], content_hash=note['content_hash'], title=note['title'],
                    knowledge_point_ids=[r[0] for r in self.personal.db.execute(
                        'SELECT knowledge_point_id FROM note_knowledge_points WHERE note_id=? ORDER BY knowledge_point_id', (note['id'],))],
                    review_status='personal_unverified', index_status=state['status'] if state else 'pending',
                    error_code=state['error_code'] if state else None))
            items.extend(self.teachers.sources(student_id))
            return {'course_id': course_id, 'retrieval_enabled': self.enabled, 'items': items}

    def _validate(self, student_id, source_refs, course_id):
        self.student(student_id, course_id)
        if not isinstance(source_refs, list) or not 1 <= len(source_refs) <= 55:
            raise ValueError('必须明确选择1～55个来源，空来源不能查询全库')
        seen, notes, courses = set(), [], []
        for ref in source_refs:
            if not isinstance(ref, dict) or set(ref) != {'source_type', 'source_id', 'source_version'}:
                raise ValueError('来源引用字段无效')
            kind, key, version = ref['source_type'], ref['source_id'], ref['source_version']
            if not all(isinstance(v, str) for v in (kind, key, version)) or (kind, key) in seen:
                raise ValueError('来源引用无效或重复')
            seen.add((kind, key))
            if kind == 'personal_note':
                note = self.personal.note(student_id, key, course_id)
                if note_version(note) != version:
                    raise SourceChanged('来源版本已变化，请刷新来源列表')
                state = self.personal.state(key)
                if (not state or state['status'] not in ('ready', 'empty') or state['indexed_revision'] != note['revision']
                        or state['indexed_hash'] != note['content_hash'] or state['target_revision'] != note['revision']
                        or state['indexer_version'] != INDEXER_VERSION):
                    raise IndexUnavailable('所选笔记索引尚未就绪，请检查状态并重建')
                notes.append((note, state))
            elif kind == 'course_material':
                if not self.courses:
                    raise IndexUnavailable('本地课程检索不可用，请检查检索依赖与开关')
                document = self.courses.documents.get(key)
                if document is None:
                    raise rules.NoteNotFound('所选来源不存在')
                if document['source_version'] != version:
                    raise SourceChanged('来源版本已变化，请刷新来源列表')
                courses.append(key)
            elif kind == 'teaching_material':
                self.teachers.validate(student_id, ref)
            else:
                raise ValueError('来源类型无效')
        return notes, courses

    def search(self, student_id, query, sources, course_id=rules.COURSE_ID, knowledge_id=None, top_k=3):
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError('检索问题必须为1～1000字符')
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise ValueError('top_k必须为1～5')
        if knowledge_id is not None and knowledge_id not in self.catalog.knowledge:
            raise ValueError('筛选知识点不存在')
        # Short snapshot, then CPU work outside the write lock. A final snapshot
        # checks every selected source even when it produced no matching chunk.
        with self.repository.transaction():
            notes, courses = self._validate(student_id, sources, course_id)
            if not self.enabled:
                raise IndexUnavailable('本地检索已关闭')
            if courses:
                self.courses.verify()
            ids = [note['id'] for note, _ in notes]
            chunks = self.personal.chunks(student_id, course_id, ids)
            for note, state in notes:
                own_chunks = [chunk for chunk in chunks if chunk['note_id'] == note['id']]
                if (len(own_chunks) != state['chunk_count'] or any(
                        chunk['raw_md'] != note['content_md'][chunk['start_offset']:chunk['end_offset']]
                        or chunk['chunk_hash'] != sha256(chunk['raw_md'].encode()).hexdigest() for chunk in own_chunks)):
                    raise IndexUnavailable('所选笔记派生片段不完整，请重建索引')
            links = {note['id']: [r[0] for r in self.personal.db.execute(
                'SELECT knowledge_point_id FROM note_knowledge_points WHERE note_id=? ORDER BY knowledge_point_id', (note['id'],))]
                for note, _ in notes}
            chunks = [chunk for chunk in chunks if knowledge_id is None or knowledge_id in links[chunk['note_id']]]
        personal_results = []
        for chunk in search_personal(chunks, query, 5):
            personal_results.append(dict(source_type='personal_note', source_id=chunk['note_id'],
                source_version=f"r{chunk['revision']}-{chunk['content_hash']}", source_revision=chunk['revision'],
                content_hash=chunk['content_hash'], chunk_hash=chunk['chunk_hash'], chunk_id=chunk['chunk_id'],
                citation_id=f"note_{chunk['note_id'].replace('-', '')}_r{chunk['revision']}:{chunk['ordinal'] + 1}",
                title=chunk['title'], section=chunk['section'], knowledge_point_ids=links[chunk['note_id']],
                review_status='personal_unverified', raw_md=chunk['raw_md'], content_text=chunk['content_text'],
                start_offset=chunk['start_offset'], end_offset=chunk['end_offset'], start_line=chunk['start_line'], end_line=chunk['end_line'],
                retrieval_score=chunk['retrieval_score'], fusion_score=None))
        course_results = self.courses.search(query, courses, knowledge_id, 5) if courses else []
        teacher_refs = [s for s in sources if s['source_type']=='teaching_material']
        teacher_results = self.teachers.search(student_id, teacher_refs, query, knowledge_id) if teacher_refs else []
        result = course_results + personal_results + teacher_results
        mixed = sum(bool(x) for x in (courses,notes,teacher_refs)) > 1
        if mixed:
            for branch in (course_results, personal_results, teacher_results):
                for rank, item in enumerate(branch, 1):
                    item['fusion_score'] = 1 / (60 + rank)
            result.sort(key=lambda p: (-p['fusion_score'], p['source_type'], p['citation_id']))
        result = result[:top_k]
        with self.repository.transaction():
            self._validate(student_id, sources, course_id)
            if courses:
                self.courses.verify()
        return {'course_id': course_id, 'query': query, 'sources': sources, 'items': result,
                'model_calls': 0, 'retrieval_policy': 'selected-tfidf-phrase-v1', 'fusion': 'rrf-k60' if mixed else None}
