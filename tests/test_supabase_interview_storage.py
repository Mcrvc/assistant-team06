"""Data API transport tests and optional real, isolated PostgreSQL RPC tests."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from assistant.db import AppEnvConfig
from assistant.interview_ai import MockInterviewAI
from assistant.interview_runtime import configured_repository
from assistant.interview_schemas import CreateInterview, SaveProgress, SubmitAnswer, FinalizeInterview
from assistant.interview_store import StoreConflict
from assistant.interview_supabase import SupabaseInterviewRepository
from assistant.interviews import InterviewError, InterviewService

ROOT = Path(__file__).resolve().parents[1]
OWNER, OTHER = str(uuid4()), str(uuid4())
CONFIG = AppEnvConfig("https://unit-test.supabase.co", "sb_publishable_test", "sb_secret_unit_test", "")


class Response(BytesIO):
    status = 200


def test_supabase_runtime_opt_in_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "supabase")
    monkeypatch.setenv("INTERVIEW_LOCAL_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    monkeypatch.setenv("SUPABASE_URL", CONFIG.supabase_url)
    with pytest.raises(ValueError, match="backend secret key"):
        configured_repository()


def test_api_key_headers_no_redirects_and_connect_probe(monkeypatch):
    calls = []
    def open_request(opener, request, *, timeout):
        assert request.full_url == "https://unit-test.supabase.co/rest/v1/rpc/yourin_interview_v1"
        assert request.get_header("Apikey") == CONFIG.supabase_secret_key
        assert request.get_header("Authorization") is None
        assert timeout == 10
        calls.append(json.loads(request.data))
        return Response(b'{"schema_version":1}')
    from urllib.request import OpenerDirector
    monkeypatch.setattr(OpenerDirector, "open", open_request)
    SupabaseInterviewRepository.connect(CONFIG)
    assert calls[0]["p_operation"] == "check"


@pytest.mark.parametrize("code,status,expected", [("PT409",409,StoreConflict),
    ("23505",409,SQLAlchemyError),("PGRST202",404,SQLAlchemyError),("x",500,SQLAlchemyError)])
def test_storage_failure_hides_body_and_key(monkeypatch, code, status, expected):
    repo = SupabaseInterviewRepository(CONFIG.supabase_url, CONFIG.supabase_secret_key)
    def fail(*args, **kwargs):
        raise HTTPError(repo._url, status, "private", {}, BytesIO(json.dumps({
            "code":code,"message":"private credentials and SQL"}).encode()))
    monkeypatch.setattr(repo._opener, "open", fail)
    with pytest.raises(expected) as exc:
        repo.get(str(uuid4()), OWNER)
    assert "private" not in str(exc.value) and CONFIG.supabase_secret_key not in str(exc.value)


def test_no_retry_after_ambiguous_network_write(monkeypatch):
    repo = SupabaseInterviewRepository(CONFIG.supabase_url, CONFIG.supabase_secret_key)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise URLError("private network details")
    monkeypatch.setattr(repo._opener, "open", fail)
    with pytest.raises(SQLAlchemyError):
        repo.delete(str(uuid4()), OWNER)
    assert calls == [1]


@pytest.mark.parametrize('operation,constraint,expected', [
    ('create', 'sessions_user_id_fkey', InterviewError),
    ('save', 'sessions_user_id_fkey', SQLAlchemyError),
    ('create', 'sessions_domain_id_fkey', SQLAlchemyError),
])
def test_missing_profile_is_distinguished_from_unrelated_foreign_keys(monkeypatch, operation, constraint, expected):
    repo = SupabaseInterviewRepository(CONFIG.supabase_url, CONFIG.supabase_secret_key)
    def fail(*args, **kwargs):
        body = {'code': '23503', 'message': f'violates foreign key constraint "{constraint}"',
                'details': 'private database/account details'}
        raise HTTPError(repo._url, 409, '', {}, BytesIO(json.dumps(body).encode()))
    monkeypatch.setattr(repo._opener, 'open', fail)
    with pytest.raises(expected) as exc:
        repo._call(operation, OWNER, str(uuid4()))
    if isinstance(exc.value, InterviewError):
        assert exc.value.status == 409 and exc.value.code == 'account_not_found'
    assert 'private' not in str(exc.value)


@pytest.fixture
def rpc_repository(monkeypatch):
    value = os.environ.get("INTERVIEW_TEST_POSTGRES_URL")
    if not value:
        pytest.skip("Set loopback INTERVIEW_TEST_POSTGRES_URL to test the actual RPC SQL")
    url = make_url(value)
    if url.host not in ("127.0.0.1","localhost","::1") or not (url.database or "").startswith("yourin_interview_test"):
        pytest.fail("RPC tests require a disposable loopback test database")
    schema = "yourin_rpc_" + uuid4().hex
    admin = create_engine(url.set(drivername="postgresql+psycopg"), hide_parameters=True)
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(url.set(drivername="postgresql+psycopg"), hide_parameters=True,
                          connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql((ROOT/"tests/fixtures/team_interview_baseline.sql").read_text())
            conn.exec_driver_sql("ALTER TABLE answers ADD COLUMN ai_comment text, ADD COLUMN ai_rating varchar(50)")
            conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN ai_overall_comment text, ADD COLUMN ai_overall_rating varchar(50)")
            conn.execute(text("INSERT INTO accounts(id,username) VALUES(:a,'rpc-a'),(:b,'rpc-b')"), {"a":OWNER,"b":OTHER})
            conn.commit()
            proposal = (ROOT/"docs/schema-proposals/LOCAL-09-supabase-api.sql").read_text()
            # Only the fresh random local schema receives the actual proposal.
            conn.exec_driver_sql(proposal.replace("public.", f'"{schema}".').replace(
                "search_path = public, pg_temp", f'search_path = "{schema}", pg_temp'))
            conn.commit()
        repo = SupabaseInterviewRepository(CONFIG.supabase_url, CONFIG.supabase_secret_key)
        def transport(request, *, timeout):
            data = json.loads(request.data)
            try:
                with engine.begin() as conn:
                    result = conn.execute(text("SELECT yourin_interview_v1(:op,CAST(:owner AS uuid),:id,CAST(:item AS jsonb),:version)"), {
                        "op":data["p_operation"],"owner":data["p_owner"],"id":data["p_id"],
                        "item":json.dumps(data["p_item"]) if data["p_item"] is not None else None,
                        "version":data["p_expected_version"],
                    }).scalar_one()
            except SQLAlchemyError as exc:
                code = getattr(exc.orig, "sqlstate", "storage_error")
                constraint = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', '')
                error = {'code': code, 'message': f'violates foreign key constraint "{constraint}"'}
                raise HTTPError(repo._url,409 if code in ("PT409", "23503") else 400,"",{},
                                BytesIO(json.dumps(error).encode())) from None
            return Response(json.dumps(result).encode())
        monkeypatch.setattr(repo._opener,"open",transport)
        assert repo._call("check") == {"schema_version":1}
        yield repo,engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def create(repo):
    service = InterviewService(repo, MockInterviewAI())
    item = service.create(OWNER, CreateInterview(job_profile={"title":"Python intern"}))
    return service,item


def test_rpc_lifecycle_and_owner_isolation(rpc_repository):
    repo,engine = rpc_repository
    service,item = create(repo)
    assert repo.get(item["id"],OWNER) == item
    item = service.save_progress(OWNER,item["id"],SaveProgress(revision=0,current_question=1,status="interrupted"))
    assert repo.get(item["id"],OWNER)["current_question"] == 1
    assert repo.get(item["id"],OTHER) is None
    assert repo.list_for_owner(OTHER) == []
    for idx in range(3):
        item = service.get(OWNER,item["id"])
        pending = service.submit_answer(OWNER,item["id"],idx,SubmitAnswer(
            revision=item["revision"],text="I built a Python API with my team and wrote tests to verify the results."))
        # Service submit returns a snapshot and grading job ID.
        snapshot,job = pending
        service.grade_answer(OWNER,item["id"],idx,job)
    item = service.get(OWNER,item["id"])
    final = service.finalize(OWNER,item["id"],FinalizeInterview(revision=item["revision"]))
    assert repo.get(item["id"],OWNER) == final
    assert repo.list_for_owner(OWNER) == [final]
    with engine.connect() as conn:
        row=conn.execute(text("SELECT current_question_index,finished,ai_overall_rating FROM sessions")).one()
        assert row.current_question_index == 2 and row.finished is True
        assert row.ai_overall_rating == final["report"]["label"]
        assert conn.execute(text("SELECT count(*) FROM grades WHERE level IS NOT NULL")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM grades WHERE accepted=true")).scalar_one() >= 3
    repo.delete(item["id"],OWNER)
    assert repo.get(item["id"],OWNER) is None


def test_rpc_conflict_foreign_delete_and_atomic_rollback(rpc_repository):
    repo,engine = rpc_repository
    service,item = create(repo)
    with pytest.raises(StoreConflict):
        repo.delete(item["id"],OTHER)
    assert repo.get(item["id"],OWNER) == item
    changed=deepcopy(item)
    changed.update(version=1,current_question=2)
    repo.save(changed,expected_version=0)
    with pytest.raises(StoreConflict):
        repo.save(changed,expected_version=0)
    bad=deepcopy(changed)
    bad.update(version=2,name="Must roll back")
    bad["answers"][0].update(grading_status="graded",grade={"score":"invalid"})
    with pytest.raises(SQLAlchemyError):
        repo.save(bad,expected_version=1)
    assert repo.get(item["id"],OWNER) == changed
    with engine.connect() as conn:
        assert conn.execute(text("SELECT interview_name FROM sessions")).scalar_one() == changed["name"]


def test_rpc_concurrent_cas_allows_only_one_writer(rpc_repository):
    from concurrent.futures import ThreadPoolExecutor
    repo,engine=rpc_repository
    service,item=create(repo)
    def write(index):
        changed=deepcopy(item)
        changed.update(version=1,current_question=index)
        try:
            repo.save(changed,expected_version=0)
            return "saved"
        except StoreConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write,[1,2])) == ["conflict","saved"]


def test_rpc_via_http_routes_background_grading_and_report(rpc_repository):
    from fastapi.testclient import TestClient
    from assistant.web import create_app
    repo,engine=rpc_repository
    service=InterviewService(repo,MockInterviewAI())
    app=create_app(service=service,auth_resolver=lambda request: OWNER)
    with TestClient(app) as client:
        created=client.post('/api/interviews',json={'job_profile':{'title':'Intern'}})
        assert created.status_code == 201
        path='/api/interviews/'+created.json()['id']
        revision=0
        for idx in range(3):
            submitted=client.post(f'{path}/answers/{idx}',json={'revision':revision,
                'text':'I worked with my team to build and test a Python API and check the results.'})
            assert submitted.status_code == 202
            revision=submitted.json()['revision']
        assert client.get(path+'/progress').json()['graded'] == 3
        assert client.post(path+'/finalize',json={'revision':revision}).status_code == 200
        assert client.get(path).json()['report'] is not None


def test_rpc_http_replays_preserve_one_set_of_answers_and_report(rpc_repository):
    from fastapi.testclient import TestClient
    from assistant.web import create_app
    repo, engine = rpc_repository
    service = InterviewService(repo, MockInterviewAI())
    with TestClient(create_app(service=service, auth_resolver=lambda request: OWNER)) as client:
        created = client.post('/api/interviews', json={'name': 'Actual saved title',
            'job_profile': {'title': 'Intern'}}).json()
        path = '/api/interviews/' + created['id']
        text_answer = 'I wrote Python tests and checked the result with my team.'
        request = {'revision': 0, 'text': text_answer}
        assert client.post(path + '/answers/0', json=request).status_code == 202
        before = repo.get(created['id'], OWNER)
        assert client.post(path + '/answers/0', json=request).status_code == 202
        assert repo.get(created['id'], OWNER) == before
        progress = {'revision': 1, 'current_question': 1, 'status': 'interrupted',
                    'answers': [text_answer, 'Second draft', '']}
        assert client.post(path + '/progress', json=progress).status_code == 200
        before = repo.get(created['id'], OWNER)
        assert client.post(path + '/progress', json=progress).status_code == 200
        assert repo.get(created['id'], OWNER) == before
        revision = before['revision']
        for index in (1, 2):
            response = client.post(path + f'/answers/{index}', json={'revision': revision, 'text': text_answer})
            assert response.status_code == 202
            revision = response.json()['revision']
        response = client.post(path + '/finalize', json={'revision': revision})
        assert response.status_code == 200
        report = response.json()['report']
        assert response.json()['name'] == 'Actual saved title'
        assert [item['answer'] for item in report['items']] == [text_answer] * 3
        assert client.get(path).json()['report'] == report
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM sessions')).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM answers')).scalar_one() == 3
        assert conn.execute(text('SELECT count(*) FROM session_questions')).scalar_one() == 3


def test_rpc_missing_account_is_actionable_and_leaves_no_partial_interview(rpc_repository):
    from fastapi.testclient import TestClient
    from assistant.web import create_app
    repo, engine = rpc_repository
    owner_without_profile = str(uuid4())
    app = create_app(service=InterviewService(repo, MockInterviewAI()),
                     auth_resolver=lambda request: owner_without_profile)
    with TestClient(app) as client:
        result = client.post('/api/interviews', json={'job_profile': {'title': 'Intern'}})
        assert result.status_code == 409
        assert result.json()['error']['code'] == 'account_not_found'
        assert owner_without_profile not in result.text
    with engine.connect() as conn:
        for table in ('sessions', 'questions', 'answers', 'session_questions'):
            assert conn.execute(text(f'SELECT count(*) FROM {table}')).scalar_one() == 0


def test_rpc_grading_collision_keeps_user_draft_and_ai_grade(rpc_repository, monkeypatch):
    repo, engine = rpc_repository
    service, item = create(repo)
    answer = 'I wrote tests and measured the Python API result with my team.'
    item, job = service.submit_answer(OWNER, item['id'], 0, SubmitAnswer(revision=0, text=answer))
    original = repo.save
    collided = False
    def save(interview, expected_version):
        nonlocal collided
        if not collided:
            collided = True
            # AI commits after progress was read but before progress is written.
            service.grade_answer(OWNER, item['id'], 0, job)
        return original(interview, expected_version)
    monkeypatch.setattr(repo, 'save', save)
    saved = service.save_progress(OWNER, item['id'], SaveProgress(revision=1,
        current_question=1, status='interrupted', answers=[answer, 'Bản nháp câu hai', '']))
    assert collided and saved['revision'] == 2
    assert saved['answers'][0]['grading_status'] == 'graded'
    assert saved['answers'][1]['text'] == 'Bản nháp câu hai'
    assert repo.get(item['id'], OWNER) == saved
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM grades')).scalar_one() >= 1
        assert conn.execute(text('SELECT count(*) FROM answers')).scalar_one() == 3
