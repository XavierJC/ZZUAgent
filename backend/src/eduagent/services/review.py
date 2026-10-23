"""Read-only replay of a learner's own graded assignments.

Repetition is self-review, not another assessment event. Nothing in this
module allocates a question, changes a score, or updates BKT.
"""
from hashlib import sha256
import json


def review_exercises(learning, student_id):
    repo = learning.repository
    with repo.transaction():
        student = learning._student(student_id)
        items = []
        # At most 20 formal rounds under the current policy. Use the frozen
        # assignment and receipt, never today's catalog text/answer.
        for receipt in repo.recent_attempts(student_id, 50):
            decision = repo.decision(receipt['decision_id'])
            if decision is None or decision.student_id != student_id or not decision.question:
                continue
            question = decision.question
            if (question['id'] != receipt['question_id']
                    or question['version'] != receipt['question_version']
                    or receipt['correct_answer'] not in question['options']):
                continue  # Do not silently substitute a newer or mismatched question.
            frozen = dict(question=question, correct_answer=receipt['correct_answer'],
                          explanation=receipt['explanation'], event_id=receipt['event_id'])
            review_key = sha256(json.dumps(frozen, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            items.append(dict(review_key=review_key, **frozen,
                              last_correct=receipt['correct'], last_answer=receipt['selected_answer'],
                              originally_answered_at=receipt['created_at'],
                              bank_version=receipt['bank_version']))
        items.sort(key=lambda item: item['last_correct'])  # Wrong answers first, stable within each group.
        return dict(student_id=student_id, learning_revision=student['revision'],
                    mode='self_review', bkt_updated=False, items=items,
                    record_storage='browser_only', grading_reference='original_saved_feedback')
