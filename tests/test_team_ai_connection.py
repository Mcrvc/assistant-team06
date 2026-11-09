from types import SimpleNamespace

import pytest

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
