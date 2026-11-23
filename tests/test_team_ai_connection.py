from types import SimpleNamespace

import pytest

from assistant.ai import AiError
from assistant.interview_ai import (
    GradeRejected, MockInterviewAI, SafeInterviewAI, TeamInterviewAI, configured_ai,
)
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


def ready_config(ready=True):
    return SimpleNamespace(llm_ready=ready, model='test-model')


def test_provider_auto_selects_the_real_provider_once_a_key_is_configured(monkeypatch):
    monkeypatch.delenv('INTERVIEW_AI_PROVIDER', raising=False)
    monkeypatch.setattr('assistant.ai.get_config', lambda: ready_config(False))
    assert isinstance(configured_ai(), MockInterviewAI)
    monkeypatch.setattr('assistant.ai.get_config', lambda: ready_config(True))
    assert isinstance(configured_ai(), TeamInterviewAI)
    monkeypatch.setenv('INTERVIEW_AI_PROVIDER', 'auto')
    assert isinstance(configured_ai(), TeamInterviewAI)


def test_provider_choice_can_still_be_pinned(monkeypatch):
    monkeypatch.setattr('assistant.ai.get_config', lambda: ready_config(True))
    monkeypatch.setenv('INTERVIEW_AI_PROVIDER', 'mock')
    assert isinstance(configured_ai(), MockInterviewAI)
    monkeypatch.setenv('INTERVIEW_AI_PROVIDER', 'nvidia')
    assert isinstance(configured_ai(), TeamInterviewAI)
    monkeypatch.setenv('INTERVIEW_AI_PROVIDER', 'something-else')
    with pytest.raises(ValueError, match='mock, auto or nvidia'):
        configured_ai()


def test_provider_outage_keeps_fallback_label():
    def offline(*args, **kwargs):
        raise TimeoutError('private provider details')
    provider = TeamInterviewAI(worker=SimpleNamespace(generate_questions=offline), timeout_s=9)
    result = SafeInterviewAI(provider).generate_questions({'title': 'Intern'}, None)
    assert len(result['questions']) == 3 and result['used_fallback'] is True


def generation_worker(questions):
    """A working provider whose questions are exactly ``questions``."""
    def generate(job, cv, notes, sources, **options):
        assert options['timeout_s'] == 9
        return {'source': 'nvidia', 'questions': questions}
    return SimpleNamespace(generate_questions=generate,
                           grade_answer_with_evidence=lambda *a, **k: {},
                           EvidenceRejected=Rejected)


def rubric_of(name='actions', points=10):
    return {'max_score': 10, 'criteria': [{'name': name, 'points': points, 'good': 'g'}]}


def test_one_unusable_real_question_does_not_mock_the_whole_interview():
    """Five real questions, one shaped a way the team schema refuses: the other
    four survive as real questions instead of the whole set becoming mock."""
    questions = [{'question': f'Tell me about project {index}.',
                  'rubric': rubric_of()} for index in range(4)]
    questions.append({'question': '   ', 'rubric': rubric_of()})  # unusable
    result = SafeInterviewAI(TeamInterviewAI(worker=generation_worker(questions), timeout_s=9)) \
        .generate_questions({'title': 'Intern'}, None)
    assert result['used_fallback'] is False and result['model'] != 'local-mock'
    assert [q['text'] for q in result['questions']] == [
        f'Tell me about project {index}.' for index in range(4)]
    assert all(q['rubric'] for q in result['questions'])


def test_an_overlong_real_question_is_trimmed_not_thrown_away():
    questions = [{'question': 'q' * 4001, 'rubric': rubric_of()}]
    result = SafeInterviewAI(TeamInterviewAI(worker=generation_worker(questions), timeout_s=9)) \
        .generate_questions({'title': 'Intern'}, None)
    assert result['used_fallback'] is False
    assert len(result['questions'][0]['text']) == 4000  # trimmed to the limit


def test_a_rubric_the_team_schema_refuses_is_repaired_into_a_usable_one():
    questions = [{
        'question': 'Tell me about your tests.',
        'rubric': {'max_score': 10, 'criteria': [
            {'name': f'c{index}', 'points': 10 / 7, 'good': 'g'} for index in range(7)]},
    }]
    result = SafeInterviewAI(TeamInterviewAI(worker=generation_worker(questions), timeout_s=9)) \
        .generate_questions({'title': 'Intern'}, None)
    kept = result['questions'][0]
    assert result['used_fallback'] is False
    assert len(kept['criteria']) == 6            # the schema caps criteria at six
    assert len(kept['rubric']['criteria']) == 6
    assert abs(sum(c['points'] for c in kept['rubric']['criteria']) - 10.0) < 1e-6


def test_a_criterion_with_extra_fields_is_kept_without_them():
    questions = [{
        'question': 'Tell me about your tests.',
        'rubric': {'max_score': 10, 'criteria': [
            {'name': 'depth', 'points': 5, 'good': 'g', 'why': 'because'},
            {'name': 'clarity', 'points': 5, 'good': 'g'}]},
    }]
    result = SafeInterviewAI(TeamInterviewAI(worker=generation_worker(questions), timeout_s=9)) \
        .generate_questions({'title': 'Intern'}, None)
    criteria = result['questions'][0]['rubric']['criteria']
    assert result['used_fallback'] is False and len(criteria) == 2
    assert all(set(criterion) == {'name', 'points', 'good'} for criterion in criteria)


def test_a_generation_with_nothing_usable_falls_back_to_the_mock():
    questions = [{'question': '', 'rubric': rubric_of()},
                 {'question': '   ', 'rubric': rubric_of()}]
    result = SafeInterviewAI(TeamInterviewAI(worker=generation_worker(questions), timeout_s=9)) \
        .generate_questions({'title': 'Intern'}, None)
    assert result['used_fallback'] is True and result['model'] == 'local-mock'


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
