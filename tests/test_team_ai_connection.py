from types import SimpleNamespace

import pytest

from assistant.ai import AiError
from assistant.interview_ai import GradeRejected, SafeInterviewAI, TeamInterviewAI, configured_ai
from assistant.interview_schemas import CreateInterview, SubmitAnswer
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService

RUBRIC = {'max_score': 10, 'criteria': [{'name': 'actions', 'points': 10, 'good': 'Explain personal actions'}]}


class Rejected(Exception):
    code = 'feedback_ungrounded'


def worker(grade=None):
    def generate(job, cv, notes, sources, **options):
        assert cv == {} and notes == '' and sources == []
        assert options['timeout_s'] == 9
        return {'source': 'nvidia', 'questions': [
            {'question': f'Q{i}?', 'rubric': RUBRIC} for i in range(3)]}
    return SimpleNamespace(generate_questions=generate, grade_answer_with_evidence=grade or (
        lambda *args, **kwargs: {'score': 7.5, 'feedback': 'Clear actions', 'evidence': ['wrote tests'],
                                'model': 'test-model', 'used_fallback': False}), EvidenceRejected=Rejected)


def test_provider_connection_preserves_rubric_and_does_not_forward_cv():
    provider = TeamInterviewAI(worker=worker(), model='duy-model', timeout_s=9)
    generation = SafeInterviewAI(provider).generate_questions({'title': 'Intern'}, 'private CV')
    assert generation['used_fallback'] is False and generation['model'] == 'duy-model'
    assert generation['questions'][0]['rubric'] == RUBRIC
    grade = SafeInterviewAI(provider).grade_answer({}, generation['questions'][0], 'I wrote tests')
    assert grade['score'] == 7.5 and grade['used_fallback'] is False


def test_refused_grade_is_saved_without_a_mock_score(tmp_path):
    def reject(*args, **kwargs):
        raise Rejected('private provider details')
    repo = SQLAlchemyInterviewRepository.local(tmp_path / 'refused.sqlite')
    try:
        service = InterviewService(repo, TeamInterviewAI(worker=worker(reject), timeout_s=9))
        item = service.create('verified-a', CreateInterview(job_profile={'title': 'Intern'}))
        item, job = service.submit_answer('verified-a', item['id'], 0, SubmitAnswer(revision=0, text='I wrote tests'))
        service.grade_answer('verified-a', item['id'], 0, job)
        saved = service.get('verified-a', item['id'])['answers'][0]
        assert saved['grading_status'] == 'rejected' and saved['grade'] is None
        assert saved['error_code'] == 'feedback_ungrounded'
    finally:
        repo.close()


def test_missing_duy_modules_fail_explicitly_instead_of_silent_mock(monkeypatch):
    def missing(name):
        raise ImportError('not integrated')
    monkeypatch.setattr('assistant.interview_ai.import_module', missing)
    monkeypatch.setenv('INTERVIEW_AI_PROVIDER', 'nvidia')
    with pytest.raises(ValueError, match="Duy's reviewed"):
        configured_ai()


def test_provider_outage_keeps_fallback_label():
    def offline(*args, **kwargs):
        raise TimeoutError('private provider details')
    provider = TeamInterviewAI(worker=SimpleNamespace(generate_questions=offline), timeout_s=9)
    result = SafeInterviewAI(provider).generate_questions({'title': 'Intern'}, None)
    assert len(result['questions']) == 3 and result['used_fallback'] is True


def test_real_grade_the_schema_refuses_is_coerced_not_mocked():
    """A genuine grade must never be lost to a strict team schema: clamp the
    score, trim overlong feedback/model, drop blank and extra evidence."""
    def oversized(*args, **kwargs):
        return {'score': 12.0, 'feedback': 'x' * 9000,
                'evidence': ['a', '', 'b'] * 3, 'model': 'm' * 500,
                'used_fallback': False}
    provider = TeamInterviewAI(worker=worker(oversized), timeout_s=9)
    result = SafeInterviewAI(provider).grade_answer({}, {
        'text': 'q', 'rubric': RUBRIC}, 'I wrote tests')
    assert result['used_fallback'] is False and result['model'] != 'local-mock'
    assert result['score'] == 10.0
    assert len(result['feedback']) == 8000
    assert result['evidence'] == ['a', 'b'] * 3  # blanks dropped, capped at 6
    assert len(result['model']) == 200


def test_provider_blip_gets_one_retry_before_the_mock():
    calls = {'n': 0}

    def flaky(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            raise AiError('transient provider blip')
        return {'score': 7.5, 'feedback': 'Clear actions',
                'evidence': ['wrote tests'], 'model': 'test-model',
                'used_fallback': False}
    provider = TeamInterviewAI(worker=worker(flaky), timeout_s=9)
    result = SafeInterviewAI(provider).grade_answer({}, {
        'text': 'q', 'rubric': RUBRIC}, 'I wrote tests')
    assert calls['n'] == 2  # one extra attempt, then the real grade
    assert result['used_fallback'] is False and result['score'] == 7.5


def test_missing_rubric_returns_the_mock_not_a_silent_real_attempt():
    provider = TeamInterviewAI(worker=worker(), timeout_s=9)
    result = SafeInterviewAI(provider).grade_answer({}, {'text': 'q'}, 'answer')
    assert result['used_fallback'] is True and result['model'] == 'local-mock'
