from concurrent.futures import ThreadPoolExecutor
import threading

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import SQLAlchemyError

from assistant.interview_ai import MockInterviewAI
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewService
from assistant.web import create_app

JOB = {"job_profile": {"title": "Python intern"}}
ANSWER = "I built a Python API with my team and wrote tests to verify the results."


@pytest.fixture
def service(tmp_path):
    store = SQLAlchemyInterviewRepository.local(tmp_path / "api.sqlite")
    yield InterviewService(store, MockInterviewAI())
    store.close()


def test_lifecycle_and_restart_without_a_second_login_system(tmp_path):
    path = tmp_path / "restart.sqlite"
    store = SQLAlchemyInterviewRepository.local(path)
    service = InterviewService(store, MockInterviewAI())
    # Trusted resolver is injected by the test; there is no production fake-login route.
    app = create_app(service=service, auth_resolver=lambda request: "verified-a")
    with TestClient(app) as client:
        created = client.post('/api/interviews', json=JOB)
        assert created.status_code == 201
        url = '/api/interviews/' + created.json()['id']
        saved = client.post(url + '/progress', json={'revision': 0,
            'current_question': 1, 'answers': [ANSWER, 'draft two', ''], 'status': 'interrupted'})
        assert saved.status_code == 200
    store.close()
    store = SQLAlchemyInterviewRepository.local(path)
    try:
        app = create_app(service=InterviewService(store, MockInterviewAI()), auth_resolver=lambda request: 'verified-a')
        with TestClient(app) as client:
            state = client.get(url).json()
            assert state['answers'][1]['text'] == 'draft two' and state['current_question'] == 1
            revision = state['revision']
            for index in range(3):
                reply = client.post(url + f'/answers/{index}', json={'revision': revision, 'text': ANSWER})
                assert reply.status_code == 202
                assert reply.json()['answers'][index]['grading_status'] == 'pending'
                revision = reply.json()['revision']
            assert client.get(url + '/progress').json()['graded'] == 3
            final = client.post(url + '/finalize', json={'revision': revision})
            assert final.status_code == 200
            assert len(final.json()['report']['items']) == 3
            assert client.get(url).json()['report'] == final.json()['report']
            assert client.post(url + '/finalize', json={'revision': revision}).json() == final.json()
            # Trương's separate history router can use the same verified-owner seam.
            assert app.state.interview_service.list('verified-a')[0]['id'] == final.json()['id']
            assert app.state.interview_service.list('verified-b') == []
    finally:
        store.close()


def test_unconfigured_auth_never_trusts_browser_owner(service):
    with TestClient(create_app(service=service)) as client:
        response = client.post('/api/interviews', json={**JOB, 'owner_id': 'browser-user'})
        assert response.status_code in (400, 503)
        assert client.post('/api/interviews', json=JOB).status_code == 503
        for path in ('/api/demo/session', '/api/cv', '/api/feedback'):
            assert client.post(path).status_code == 404


def test_foreign_owner_cannot_access_or_change_interview(service):
    app = create_app(service=service, auth_resolver=lambda request: request.headers.get('x-test-owner', ''))
    with TestClient(app) as client:
        client.headers['x-test-owner'] = 'verified-a'
        created = client.post('/api/interviews', json=JOB).json()
        url = '/api/interviews/' + created['id']
        client.headers['x-test-owner'] = 'verified-b'
        assert client.get(url).status_code == 404
        assert client.post(url + '/progress', json={'revision': 0, 'current_question': 1}).status_code == 404
        assert client.post(url + '/answers/0', json={'revision': 0, 'text': ANSWER}).status_code == 404
        assert client.post(url + '/finalize', json={'revision': 0}).status_code == 404


def test_invalid_answer_and_storage_error_do_not_echo_private_inputs(service, monkeypatch):
    with TestClient(create_app(service=service, auth_resolver=lambda request: 'verified-a')) as client:
        url = '/api/interviews/' + client.post('/api/interviews', json=JOB).json()['id']
        response = client.post(url + '/answers/0', json={'revision': 0, 'text': ''})
        assert response.status_code == 400
        def fail(*args):
            raise SQLAlchemyError('private database details')
        monkeypatch.setattr(service.repository, 'get', fail)
        response = client.get(url)
        assert response.status_code == 503 and 'private' not in response.text


def test_response_is_sent_before_background_grading_completes(service):
    entered, release, sent = threading.Event(), threading.Event(), threading.Event()
    class SlowAI(MockInterviewAI):
        def grade_answer(self, *args):
            entered.set()
            assert release.wait(5)
            return super().grade_answer(*args)
    service.ai.provider = SlowAI()
    app = create_app(service=service, auth_resolver=lambda request: 'verified-a')
    class Capture:
        async def __call__(self, scope, receive, send):
            async def capture(message):
                if '/answers/' in scope.get('path', '') and message['type'] == 'http.response.body':
                    sent.set()
                await send(message)
            await app(scope, receive, capture)
    with TestClient(Capture()) as client:
        url = '/api/interviews/' + client.post('/api/interviews', json=JOB).json()['id']
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, url + '/answers/0', json={'revision': 0, 'text': ANSWER})
            try:
                assert sent.wait(5) and entered.wait(5)
                assert service.get('verified-a', url.rsplit('/', 1)[1])['answers'][0]['grading_status'] == 'pending'
            finally:
                release.set()
            assert future.result(timeout=5).status_code == 202
