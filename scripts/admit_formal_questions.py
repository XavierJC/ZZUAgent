"""Preview/apply a frozen AI content audit to a local DB, without model calls.

The audit plan contains local owner-scoped question IDs and content hashes and
must remain under data/local. Only metadata is changed; no historical answers,
student revisions, ordinary questions or source files are rewritten.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from eduagent.content_review import load_candidate
from eduagent.domain.catalog import Catalog
from eduagent.services.formal_admission import KEY, VERSION, FormalAdmission, checksum
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository, encode


def build_record(repo, data_dir, plan):
    base = Catalog.load(data_dir)
    learning = LearningService(base, repo)
    if learning.formal_admission.record:
        raise ValueError('本机已准入，不能重复覆盖；新增批次需独立版本方案')
    candidate, summary = load_candidate(data_dir, data_dir/'candidates/questions-v2.json')
    if candidate.fingerprint != plan['candidate_fingerprint']:
        raise ValueError('AI检查后候选题已变化，请重新核对')
    config = json.loads(repo.connection.execute("SELECT value FROM metadata WHERE key='configuration'").fetchone()[0])
    record = dict(version=VERSION, bank_version=plan['bank_version'], previous_configuration=config,
                  review=dict(method='assistant_content_check', human_review_performed=False,
                              statistical_calibration=False, paid_model_calls=0),
                  shared_questions=[asdict(q) for q in candidate.questions.values()], personal_questions=[])
    for item in plan.get('personal_questions', []):
        row = repo.connection.execute('SELECT * FROM personal_questions WHERE id=?', (item['id'],)).fetchone()
        if not row or row['revision'] != item['revision'] or row['status'] == 'archived':
            raise ValueError('个人题已修改或归档，请重新检查')
        payload, source = json.loads(row['payload_json']), json.loads(row['source_json'])
        if checksum(payload) != item['payload_hash'] or checksum(source) != item['source_hash']:
            raise ValueError('个人题或来源在AI检查后已变化')
        if payload['question_type'] != 'true_false' or payload.get('answer') not in ('true', 'false') or payload.get('dependencies') or payload.get('subquestions'):
            raise ValueError('本轮只纳入完整且原有明确答案的个人判断题')
        if item['knowledge_id'] not in base.knowledge or not item['explanation'].strip():
            raise ValueError('个人题需要原五点内的明确知识归属与答案解释')
        question = dict(id='personal:'+row['id']+':r'+str(row['revision']), version='r'+str(row['revision']),
                        knowledge_id=item['knowledge_id'], difficulty='medium', stem=payload['stem'],
                        options={'A':'正确', 'B':'错误'}, answer='A' if payload['answer']=='true' else 'B',
                        explanation=item['explanation'], source='个人上传原题 · AI核对现有转录与答案', review_status='ai_checked')
        record['personal_questions'].append(dict(student_id=row['student_id'], personal_id=row['id'],
            revision=row['revision'], payload_hash=item['payload_hash'], source_hash=item['source_hash'],
            source={k:source.get(k) for k in ('original_source_type','original_source_id','source_version','run_id','origin_mode')},
            answer_origin='source_extracted_by_ai', question=question))
    return base, record


def install(repo, base, record):
    """Caller owns the transaction; failures roll back both metadata entries."""
    previous = repo.connection.execute("SELECT value FROM metadata WHERE key='configuration'").fetchone()[0]
    if json.loads(previous) != record['previous_configuration']:
        raise ValueError('配置已变化，拒绝准入')
    repo.connection.execute('INSERT INTO metadata VALUES (?,?)', (KEY, encode(record)))
    admission = FormalAdmission(base, repo, record['previous_configuration'])
    for entry in record['personal_questions']:
        if not admission.source_current(entry['student_id'], entry):
            raise ValueError('个人题来源已过期、删除或未就绪')
    repo.connection.execute("UPDATE metadata SET value=? WHERE key='configuration'", (encode(admission.configuration),))
    LearningService(base, repo)
    if repo.connection.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('外键检查失败')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    if not args.db.is_file():
        raise ValueError('目标数据库不存在，拒绝创建空库')
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    with SQLiteRepository(args.db, allow_upgrade=False) as repo:
        if args.apply:
            if not args.backup or args.backup.exists():
                raise ValueError('应用前必须提供一个不存在的备份路径')
            args.backup.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(args.backup) as backup:
                repo.connection.backup(backup)
        # Dry runs inspect a consistent read transaction; build_record only
        # binds an already present configuration and is required to be a no-op.
        with repo.transaction():
            base, record = build_record(repo, args.data_dir, plan)
            if args.apply:
                install(repo, base, record)
        print(json.dumps(dict(applied=args.apply, shared_questions=len(record['shared_questions']),
                              personal_questions=len(record['personal_questions']),
                              human_review_performed=False, paid_model_calls=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
