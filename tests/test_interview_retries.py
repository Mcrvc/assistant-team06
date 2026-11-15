"""Lost responses and overlapping writes must not discard accepted answers."""
from concurrent.futures import ThreadPoolExecutor
import threading

from fastapi.testclient import TestClient
import pytest

from assistant.interview_ai import MockInterviewAI
from assistant.interview_schemas import CreateInterview, FinalizeInterview, SaveProgress, SubmitAnswer
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService
from assistant.web import create_app

OWNER = 'verified-retry-owner'
ANSWER = 'I built a Python API with my team and wrote tests to verify the result.'


class CountingAI(MockInterviewAI):
    def __init__(self):
        self.calls = 0
    def grade_answer(self, *args):
        self.calls += 1
        return super().grade_answer(*args)


@pytest.fixture
def service(tmp_path):
    repository = SQLAlchemyInterviewRepository.local(tmp_path / 'retries.sqlite')
    yield InterviewService(repository, CountingAI())
    repository.close()


def create(service):
    return service.create(OWNER, CreateInterview(job_profile={'title': 'Python intern'}))


def test_retry_of_accepted_http_answer_returns_success_without_grading_again(service):
    with TestClient(create_app(service=service, auth_resolver=lambda request: OWNER)) as client:
        created = client.post('/api/interviews', json={'job_profile': {'title': 'Intern'}}).json()
        path = '/api/interviews/' + created['id']
        request = {'revision': 0, 'text': ANSWER}
        assert client.post(path + '/answers/0', json=request).status_code == 202
        before = service.get(OWNER, created['id'])
        retry = client.post(path + '/answers/0', json=request)
        assert retry.status_code == 202
        assert retry.json()['answers'][0]['grading_status'] == 'graded'
        assert service.get(OWNER, created['id']) == before
        assert service.ai.provider.calls == 1


def test_retry_of_saved_draft_after_grading_keeps_grade_and_draft(service):
    item = create(service)
    item, job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    request = SaveProgress(revision=1, current_question=1, status='interrupted', answers=[ANSWER, 'Unsent second draft', ''])
    service.save_progress(OWNER, item['id'], request)
    service.grade_answer(OWNER, item['id'], 0, job)
    before = service.get(OWNER, item['id'])
    retry = service.save_progress(OWNER, item['id'], request)
    assert retry == before
    assert retry['answers'][0]['grading_status'] == 'graded'
    assert retry['answers'][1]['text'] == 'Unsent second draft'
    assert retry['status'] == 'interrupted'


def test_overlapping_identical_answer_has_only_one_grading_job(service, monkeypatch):
    item = create(service)
    barrier = threading.Barrier(2)
    original = service.repository.save
    def save(interview, expected_version):
        if expected_version == 0:
            barrier.wait(timeout=5)
        return original(interview, expected_version)
    monkeypatch.setattr(service.repository, 'save', save)
    def submit(_):
        return service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sum(job is not None for _, job in results) == 1
    assert results[0][0]['answers'][0]['grading_id'] == results[1][0]['answers'][0]['grading_id']
    assert service.get(OWNER, item['id'])['revision'] == 1


def test_retry_with_current_revision_can_explicitly_restart_pending_grading(service):
    item = create(service)
    first, old_job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    fresh, new_job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=first['revision'], text=ANSWER))
    assert new_job and new_job != old_job
    service.grade_answer(OWNER, item['id'], 0, old_job)
    assert service.get(OWNER, item['id'])['answers'][0]['grading_status'] == 'pending'
    service.grade_answer(OWNER, item['id'], 0, new_job)
    assert service.get(OWNER, item['id'])['answers'][0]['grading_status'] == 'graded'


def test_pending_replay_keeps_job_and_old_replays_still_conflict(service):
    item = create(service)
    first, job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    replay, duplicate_job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    assert replay == first and duplicate_job is None
    latest = service.save_progress(OWNER, item['id'], SaveProgress(revision=1,
        current_question=1, status='interrupted', answers=[ANSWER, 'Newer local draft', '']))
    with pytest.raises(InterviewError) as exc:
        service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    assert exc.value.code == 'revision_conflict'
    with pytest.raises(InterviewError):
        service.save_progress(OWNER, item['id'], SaveProgress(revision=1,
            current_question=1, status='interrupted', answers=[ANSWER, 'A different draft', '']))
    assert service.get(OWNER, item['id']) == latest


def test_different_stale_edit_still_conflicts_and_keeps_current_answer(service):
    item = create(service)
    current, _ = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    with pytest.raises(InterviewError) as exc:
        service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text='A conflicting different answer'))
    assert exc.value.status == 409 and exc.value.code == 'revision_conflict'
    assert service.get(OWNER, item['id']) == current


def test_save_retries_internal_version_collision_without_losing_ai_result(service, monkeypatch):
    item = create(service)
    item, job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=ANSWER))
    original = service.repository.save
    collided = False
    def save(interview, expected_version):
        nonlocal collided
        if not collided:
            collided = True
            service.grade_answer(OWNER, item['id'], 0, job)
        return original(interview, expected_version)
    monkeypatch.setattr(service.repository, 'save', save)
    saved = service.save_progress(OWNER, item['id'], SaveProgress(revision=1, current_question=1,
        status='interrupted', answers=[ANSWER, 'Second answer draft', '']))
    assert collided and saved['revision'] == 2
    assert saved['answers'][0]['grade'] is not None
    assert saved['answers'][1]['text'] == 'Second answer draft'


def test_overlapping_finalize_returns_same_report_without_regrading(service, monkeypatch):
    item = create(service)
    for index in range(3):
        item = service.get(OWNER, item['id'])
        item, job = service.submit_answer(OWNER, item['id'], index, SubmitAnswer(revision=item['revision'], text=ANSWER))
        service.grade_answer(OWNER, item['id'], index, job)
    before = service.get(OWNER, item['id'])
    barrier = threading.Barrier(2)
    original = service.repository.save
    def save(interview, expected_version):
        if expected_version == before['version']:
            barrier.wait(timeout=5)
        return original(interview, expected_version)
    monkeypatch.setattr(service.repository, 'save', save)
    def finalize(_):
        return service.finalize(OWNER, item['id'], FinalizeInterview(revision=before['revision'], name='Real saved name'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(finalize, range(2)))
    assert first == second
    assert first['name'] == 'Real saved name' and first['revision'] == before['revision'] + 1
    assert service.ai.provider.calls == 3
