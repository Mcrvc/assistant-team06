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
from assistant.interviews import InterviewService

ROOT = Path(__file__).resolve().parents[1]
OWNER, OTHER = str(uuid4()), str(uuid4())
CONFIG = AppEnvConfig("https://unit-test.supabase.co", "sb_publishable_test", "sb_secret_unit_test", "")


class Response(BytesIO):
    status = 200


def test_supabase_runtime_opt_in_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "supabase")
    monkeypatch.setenv("INTERVIEW_LOCAL_STORAGE", "1")
    with pytest.raises(ValueError, match="disable interview demo"):
        configured_repository(demo_enabled=True)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    monkeypatch.setenv("SUPABASE_URL", CONFIG.supabase_url)
    with pytest.raises(ValueError, match="backend secret key"):
        configured_repository(demo_enabled=False)


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
                raise HTTPError(repo._url,409 if code=="PT409" else 400,"",{},
                                BytesIO(json.dumps({"code":code}).encode())) from None
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
