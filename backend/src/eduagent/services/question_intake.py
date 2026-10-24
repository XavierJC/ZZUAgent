"""Conservative automatic ordinary-practice admission, never human verification."""
from hashlib import sha256
import json
import re

from eduagent.domain.personal_bank import practice_ready, question

VERSION = 'ordinary-intake-v1'
ALLOWED_ISSUES = {'answer_missing', 'image_transcription_unverified'}


def identity(payload):
    body = {k:payload.get(k) for k in ('question_type','stem','shared_context','options','subquestions')}
    return sha256(re.sub(r'\s+', '', json.dumps(body, sort_keys=True, ensure_ascii=False)).casefold().encode()).hexdigest()


def inspect(payload, warnings=()):
    problems = list(dict.fromkeys([*payload.get('issues', []), *warnings]))
    reasons = [p for p in problems if p not in ALLOWED_ISSUES]
    try: practice_ready(payload)
    except ValueError: reasons.append('incomplete_question_structure')
    if len(payload['stem'].strip()) < 6 or re.search(r'无法辨认|待转录|内容待补|\[缺失', payload['stem']): reasons.append('incomplete_stem')
    if payload.get('dependencies'): reasons.append('unresolved_dependencies')
    for child in payload.get('subquestions', []): reasons.extend(inspect(child))
    return list(dict.fromkeys(reasons))


def auto_entry(bank, student, payload, source, batch, origin, warnings=()):
    from eduagent.services.learning import now
    # Canonical defaults belong at the storage entrance, including for local
    # callers. An absent optional concept list must not break later selection.
    payload = question(payload)
    reasons = inspect(payload, warnings)
    fingerprint = identity(payload)
    # Repeated uploads/tasks may return the existing question; never rewrite
    # its user edits, archived status, or answer provenance.
    for row in bank.db.execute('SELECT * FROM personal_questions WHERE student_id=? AND course_id=? ORDER BY created_at,id', (student,'machine_learning')):
        previous = json.loads(row['payload_json'])
        if identity(previous) != fingerprint: continue
        if row['status']=='archived' or bank.resources.source_status(student,json.loads(row['source_json'])) not in ('current','manual'):
            continue  # A fresh import must not resolve to an unusable old source.
        fields = ('answer','answer_text','answer_keys','explanation')
        if any(previous.get(k) != payload.get(k) for k in fields):
            reasons.append('duplicate_answer_conflict'); break
        return row['id'], 'duplicate'
    status = 'draft' if reasons else 'practice'
    review = dict(reviewed=False, answer_confirmed=False, automation=dict(version=VERSION,
                  admitted=status=='practice', issues=list(dict.fromkeys(reasons)), created_at=now()),
                  content_verification='ai_extracted_unverified' if source.get('extraction_request_id') else 'structure_only_unverified')
    key = bank._insert_question(student, payload, source, batch, origin, status=status, review=review)
    return key, 'needs_attention' if reasons else 'ready'


def organize(bank, student, body):
    """Explicitly process existing drafts. Historical practice is not rewritten."""
    def apply():
        ids = body.get('question_ids')
        rows = [dict(r) for r in bank.db.execute("SELECT * FROM personal_questions WHERE student_id=? AND course_id=? AND status='draft' ORDER BY created_at,id", (student,'machine_learning'))]
        if ids is not None:
            for key in ids: bank.row(student,key)
            rows = [r for r in rows if r['id'] in ids]
        rows = rows[:50]
        counts = dict(ready=0, needs_attention=0)
        from eduagent.services.learning import now
        for row in rows:
            payload = json.loads(row['payload_json']); source = json.loads(row['source_json'])
            reasons = inspect(payload, source.get('warnings', []))
            if source.get('proposal_for'): reasons.append('proposal_requires_explicit_acceptance')
            if bank.resources.source_status(student,source) not in ('current','manual'): reasons.append('source_changed')
            existing = json.loads(bank.db.execute('SELECT review_json FROM personal_question_revisions WHERE question_id=? AND revision=?', (row['id'],row['revision'])).fetchone()[0])
            review = dict(existing, reviewed=False, answer_confirmed=False,
                          automation=dict(version=VERSION,admitted=not reasons,issues=reasons,created_at=now()))
            bank._save_revision(student,row,payload,'draft' if reasons else 'practice',review)
            counts['needs_attention' if reasons else 'ready'] += 1
        return dict(processed=len(rows),**counts,bkt_updated=False)
    return bank._write(student,body,'organize-ordinary',apply)
