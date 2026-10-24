"""Direct, unverified document reading sources, separate from reviewed teaching links."""
from hashlib import sha256
import json
from pathlib import Path

from eduagent.services.teaching_sources import TeachingSources, COURSE, digest
from eduagent.retrieval.note_chunks import chunk_markdown, ChunkingError, INDEXER_VERSION
from eduagent.retrieval.personal import search_personal

VERSION='uploaded-document-reading-v1'


class DocumentSources(TeachingSources):
    def source(self, student, source_id):
        doc = self.document(student, source_id)
        file_format=self.db.execute('SELECT format FROM document_versions WHERE id=?',(doc['current_version_id'],)).fetchone()[0]
        runs = self.db.execute('SELECT * FROM document_parse_runs WHERE document_id=? AND student_id=? AND version_id=? AND generation=? ORDER BY updated_at,id',
                               (source_id, student, doc['current_version_id'], doc['parse_generation'])).fetchall()
        head = next((r for r in runs if r['id'] == doc['current_parse_id']), None)
        units = {}
        if head and head['status'] in ('ready', 'partial'):
            eligible = [head] + [r for r in runs if r['mode'] == 'vision' and r['status'] in ('ready', 'partial') and r['expected_revision'] == doc['revision']]
            for run in eligible:
                for row in self.db.execute('SELECT * FROM document_units WHERE run_id=? AND student_id=? ORDER BY ordinal', (run['id'], student)):
                    units[row['ordinal']] = dict(row)
        selected = sorted(units.values(), key=lambda u: u['ordinal'])
        readable = [u for u in selected if len(''.join(u['content_md'].split())) >= 24 and 'hidden_slide_not_for_retrieval' not in json.loads(u['warnings_json'])]
        version = digest([VERSION, INDEXER_VERSION, doc['revision'], doc['current_version_id'], doc['current_parse_id'], doc['parse_generation'],
                          [(u['id'], sha256(u['content_md'].encode()).hexdigest()) for u in selected]])
        state = 'ready' if readable else 'empty' if head and head['status'] in ('ready', 'partial', 'empty') else 'failed' if head and head['status'] in ('failed', 'uncertain') else 'pending'
        return dict(source_type='uploaded_document', source_id=source_id, source_version=version,
                    source_revision=doc['revision'], content_hash=doc['content_hash'], title=doc['title'],
                    knowledge_point_ids=[], review_status='document_unverified', index_status=state,
                    error_code=None if readable else 'no_readable_text' if state == 'empty' else 'parse_not_ready',
                    document_id=source_id, version_id=doc['current_version_id'], run_id=doc['current_parse_id'],
                    readable_units=len(readable), total_units=len(selected), file_format=file_format,
                    units=readable, preview_units=selected, document=doc)

    def sources(self, student):
        self.student(student)
        rows = self.db.execute('SELECT id FROM course_documents WHERE student_id=? AND course_id=? AND deleted_at IS NULL ORDER BY created_at,id', (student, COURSE)).fetchall()
        return [{k:v for k,v in self.source(student, r['id']).items() if k not in ('units', 'preview_units', 'document')} for r in rows]

    def validate(self, student, ref, *, require_ready=True):
        from eduagent.services.knowledge import SourceChanged, IndexUnavailable
        from eduagent.domain.notes import NoteNotFound
        try: source = self.source(student, ref['source_id'])
        except ValueError: raise NoteNotFound('当前标识下没有该上传资料') from None
        if source['source_version'] != ref['source_version']: raise SourceChanged('上传资料版本或解析已变化，请重新选择')
        if require_ready and source['index_status'] != 'ready': raise IndexUnavailable('资料尚无可读正文，请检查解析或选择需要识别的页面')
        doc = source['document']
        if self.directory:
            root = Path(self.directory).resolve(); path = (root/doc['storage_key']).resolve()
            if not path.is_relative_to(root) or not path.is_file() or sha256(path.read_bytes()).hexdigest() != doc['content_hash']:
                raise IndexUnavailable('原件完整性检查未通过，请检查资料文件')
        return source

    def search(self, student, refs, query, knowledge_id=None):
        from eduagent.domain.notes import NoteTooLarge
        chunks = []
        for ref in refs:
            source = self.validate(student, ref)
            # An unclassified uploaded page must never pretend to have a
            # confirmed formal knowledge-point mapping.
            if knowledge_id: continue
            for unit in source['units']:
                try:
                    parts = chunk_markdown(dict(id=unit['id'], student_id=student, course_id=COURSE,
                                                revision=source['source_revision'], content_hash=source['content_hash'],
                                                title=source['title'], content_md=unit['content_md']))
                except ChunkingError:
                    raise IndexUnavailable('资料包含超大公式/代码块，请缩小或整理资料后重试') from None
                location = json.loads(unit['location_json'])
                page = location.get('page_number', location.get('slide_number', unit['ordinal']))
                position=f'幻灯片{page}' if source['file_format']=='pptx' else f'文本单位{page}' if source['file_format'] in ('md','txt') else f'第{page}页'
                for part in parts:
                    chunks.append(dict(source_type='uploaded_document', source_id=source['source_id'], source_version=source['source_version'],
                        source_revision=source['source_revision'], content_hash=source['content_hash'], chunk_hash=part['chunk_hash'],
                        chunk_id=part['chunk_id'], citation_id='doc_'+unit['id'].replace('-', '')+':'+str(part['ordinal']+1),
                        title=source['title'], section=f"{position} · {part['section']}", knowledge_point_ids=[],
                        review_status='document_unverified', raw_md=part['raw_md'], content_text=part['content_text'],
                        start_offset=part['start_offset'], end_offset=part['end_offset'], start_line=part['start_line'], end_line=part['end_line'],
                        retrieval_score=0., fusion_score=None, document_id=source['document_id'], version_id=source['version_id'],
                        page_number=page, file_format=source['file_format'], excerpt_origin=unit['origin'], original_text_snapshot=part['raw_md']))
                    if len(chunks)>4096: raise NoteTooLarge('所选资料超过4096片段，请缩小文件范围')
        # Fixed bounded batches avoid the note index's 256-chunk limit on
        # long slide decks. Scores remain lexical, not a semantic accuracy claim.
        matches=[]
        for offset in range(0,len(chunks),64): matches.extend(search_personal(chunks[offset:offset+64],query,5))
        return sorted(matches,key=lambda p:(-p['retrieval_score'],p['chunk_id']))[:5]
