"""Exhausted learners may self-review; formal facts remain immutable."""
from copy import deepcopy
from uuid import uuid4

from eduagent.services.review import review_exercises
from eduagent.storage.migrations import fact_snapshot
from test_api import client, api_settings, start, next_question, submit


def answer(service, student='student-a', correct=False):
    d = service.next_action(student)
    q = service.catalog.questions[d.question['id']]
    selected = q.answer if correct else next(k for k in q.options if k != q.answer)
    return service.submit(student, d.decision_id, selected, str(uuid4()))


def test_exhausted_questions_recover_as_read_only_review(service):
    answer(service)
    answer(service, correct=True)
    stopped = service.next_action('student-a')
    assert stopped.stop_reason == 'insufficient_questions'
    before = fact_snapshot(service.repository.connection)
    exercises = review_exercises(service, 'student-a')
    assert len(exercises['items']) == 2
    assert exercises['items'][0]['last_correct'] is False
    assert exercises['mode'] == 'self_review' and exercises['bkt_updated'] is False
    assert exercises['record_storage'] == 'browser_only'
    assert len(set(i['review_key'] for i in exercises['items'])) == 2
    for i in exercises['items']:
        assert i['question']['review_status'] == 'pending'
        assert i['correct_answer'] in i['question']['options']
        assert i['explanation']
    for _ in range(3):
        assert review_exercises(service, 'student-a') == exercises
    assert fact_snapshot(service.repository.connection) == before
    assert service.next_action('student-a') == stopped


def test_review_uses_saved_assignment_not_current_catalog(service):
    result = answer(service)
    expected = deepcopy(review_exercises(service, 'student-a')['items'][0])
    # Swap a catalog object in memory, without changing the persisted facts.
    service.catalog.questions.pop(result.question_id)
    assert review_exercises(service, 'student-a')['items'][0] == expected


def test_review_scoped_and_no_unattempted_answers(service):
    answer(service)
    service.register('student-b')
    assert review_exercises(service, 'student-b')['items'] == []
    assert len(review_exercises(service, 'student-a')['items']) == 1


def test_http_review_restoration_is_get_only_and_leaves_formal_state(client):
    start(client, goals=['linear_regression_loss'])
    start(client, student='other', goals=['linear_regression_loss'])
    for i in range(2):
        decision = next_question(client)
        assert submit(client, decision, event_id=f'e-{i}').status_code == 200
    assert next_question(client)['stop_reason'] == 'insufficient_questions'
    root = '/api/v1/students/api-student'
    before = {p: client.get(root+p).json() for p in ('/mastery', '/history', '/current-decision')}
    first = client.get(root+'/review-exercises')
    assert first.status_code == 200 and len(first.json()['items']) == 2
    assert client.get('/api/v1/students/other/review-exercises').json()['items'] == []
    assert client.get('/api/v1/students/missing/review-exercises').status_code == 404
    assert client.post(root+'/review-exercises', json={}).status_code == 405
    for _ in range(3):
        assert client.get(root+'/review-exercises').json() == first.json()
    assert {p: client.get(root+p).json() for p in before} == before
