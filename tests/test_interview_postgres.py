"""Relational contract tests, optionally repeated on a disposable PostgreSQL DB.

INTERVIEW_TEST_POSTGRES_URL must point at a loopback-only database whose name
starts with yourin_interview_test. Every test owns a fresh random schema.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from assistant.interview_ai import MockInterviewAI
from assistant.api import create_app
from assistant.interview_postgres import (
    PostgresInterviewRepository, StorageFormatError, accounts, answers, grades,
    metadata, questions, session_questions, sessions,
)
from assistant.interview_schemas import CreateInterview, FinalizeInterview, SaveProgress, SubmitAnswer
from assistant.interview_store import StoreConflict
from assistant.interviews import InterviewError, InterviewService

ROOT = Path(__file__).resolve().parents[1]
OWNER, OTHER = str(uuid4()), str(uuid4())
ANSWER = "Tôi đã viết API với nhóm, kiểm thử và đo kết quả. I wrote tests and measured the result."


@pytest.fixture(params=["sqlite", "postgres"])
def repository(request, tmp_path):
    admin = None
    schema = "yourin_test_" + uuid4().hex
    if request.param == "postgres":
        value = os.environ.get("INTERVIEW_TEST_POSTGRES_URL")
        if not value:
            pytest.skip("Set INTERVIEW_TEST_POSTGRES_URL for the real PostgreSQL suite")
        url = make_url(value)
        if (url.host not in ("127.0.0.1", "localhost", "::1")
                or not (url.database or "").startswith("yourin_interview_test")):
            pytest.fail("PostgreSQL tests require a loopback yourin_interview_test database")
        url = url.set(drivername="postgresql+psycopg")
        admin = create_engine(url, hide_parameters=True)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(url, hide_parameters=True,
                               connect_args={"options": f"-csearch_path={schema}"})
        # Test the actual additive proposal against the pre-existing columns.
        with engine.connect() as connection:
            connection.exec_driver_sql((ROOT / "tests/fixtures/team_interview_baseline.sql").read_text())
            connection.commit()
            connection.exec_driver_sql((ROOT / "docs/schema-proposals/LOCAL-04-interview.sql").read_text())
            connection.commit()
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'relational.sqlite'}",
                               connect_args={"check_same_thread": False, "timeout": 10})
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        metadata.create_all(engine)
    repo = PostgresInterviewRepository(engine)
    try:
        repo.check_schema()
        with engine.begin() as connection:
            connection.execute(accounts.insert(), [
                {"id": OWNER, "username": "fake-user-a"},
                {"id": OTHER, "username": "fake-user-b"},
            ])
        yield repo
    finally:
        repo.close()
        if admin is not None:
            with admin.begin() as connection:
                # schema is generated above, never taken from the environment.
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin.dispose()


def create(repository, ai=None):
    service = InterviewService(repository, ai or MockInterviewAI())
    item = service.create(OWNER, CreateInterview.model_validate({
        "name": "Thử phỏng vấn", "job_profile": {"title": "Python intern", "company": "Ví dụ"},
        "cv": "Dữ liệu giả: sinh viên học Python.",
    }))
    return service, item


def submit(service, item, index):
    return service.submit_answer(OWNER, item["id"], index,
        SubmitAnswer(revision=item["revision"], text=ANSWER))


def test_lossless_resume_and_report_after_reopening(repository):
    service, item = create(repository)
    assert repository.get(item["id"], OWNER) == item
    item = service.save_progress(OWNER, item["id"], SaveProgress(
        revision=0, answers=[ANSWER, "draft thứ hai", ""], current_question=1, status="interrupted"))
    # Dispose the pool to force a new physical connection.
    repository.engine.dispose()
    service = InterviewService(PostgresInterviewRepository(repository.engine))
    assert service.get(OWNER, item["id"]) == item
    for index in range(3):
        item, job = submit(service, item, index)
        service.grade_answer(OWNER, item["id"], index, job)
    item = service.finalize(OWNER, item["id"], FinalizeInterview(revision=item["revision"]))
    repository.engine.dispose()
    assert repository.get(item["id"], OWNER) == item
    assert service.finalize(OWNER, item["id"], FinalizeInterview(revision=0)) == item
    with repository.engine.connect() as connection:
        row = connection.execute(select(sessions).where(sessions.c.id == item["id"])).mappings().one()
        assert row["finished"] and row["finished_at"] and row["report"] == item["report"]
        stored = connection.execute(select(grades)).mappings().all()
        assert len(stored) == 3 and all(r["accepted"] and r["level"] is None for r in stored)


def test_ownership_and_stale_update_do_not_touch_children(repository):
    service, item = create(repository)
    assert repository.get(item["id"], OTHER) is None
    stolen = {**deepcopy(item), "owner_id": OTHER, "version": 1}
    with pytest.raises(StoreConflict):
        repository.save(stolen, 0)
    item["version"] = 1
    repository.save(item, 0)
    stale = deepcopy(item)
    stale["answers"][0]["text"] = "must never overwrite"
    with pytest.raises(StoreConflict):
        repository.save(stale, 0)
    assert repository.get(item["id"], OWNER) == item


def test_missing_account_rolls_back_entire_creation(repository):
    before = {}
    with repository.engine.connect() as connection:
        for table in (sessions, questions, session_questions, answers):
            before[table.name] = connection.scalar(select(func.count()).select_from(table))
    service = InterviewService(repository)
    with pytest.raises(IntegrityError):
        service.create(str(uuid4()), CreateInterview(job_profile={"title": "Intern"}))
    with repository.engine.connect() as connection:
        for table in (sessions, questions, session_questions, answers):
            assert connection.scalar(select(func.count()).select_from(table)) == before[table.name]


def test_child_failure_rolls_back_revision_and_answer_changes(repository, monkeypatch):
    service, item = create(repository)
    original = repository._write_answer
    calls = 0
    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated outage after first child write")
        original(*args)
    monkeypatch.setattr(repository, "_write_answer", fail_second)
    with pytest.raises(RuntimeError):
        service.save_progress(OWNER, item["id"], SaveProgress(
            revision=0, current_question=1, answers=["new one", "new two", ""]))
    assert repository.get(item["id"], OWNER) == item


def test_edit_removes_persisted_grade_and_superseded_job_cannot_restore_it(repository):
    service, item = create(repository)
    item, job = submit(service, item, 0)
    service.grade_answer(OWNER, item["id"], 0, job)
    item = service.get(OWNER, item["id"])
    assert item["answers"][0]["grading_status"] == "graded"
    item = service.save_progress(OWNER, item["id"], SaveProgress(
        revision=item["revision"], current_question=0, answers=["edited answer", "", ""]))
    service.grade_answer(OWNER, item["id"], 0, job)
    assert repository.get(item["id"], OWNER) == item
    with repository.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grades)) == 0


def test_parallel_grading_keeps_both_results_and_client_revision(repository):
    barrier = threading.Barrier(2)
    class ConcurrentAI(MockInterviewAI):
        def grade_answer(self, *args):
            barrier.wait(timeout=10)
            return super().grade_answer(*args)
    service, item = create(repository, ConcurrentAI())
    item, first_job = submit(service, item, 0)
    item, second_job = submit(service, item, 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(service.grade_answer, OWNER, item["id"], index, job)
                for index, job in enumerate([first_job, second_job])]
        for job in jobs:
            job.result(timeout=15)
    saved = repository.get(item["id"], OWNER)
    assert saved["revision"] == 2 and saved["version"] == 4
    assert [a["grading_status"] for a in saved["answers"]] == ["graded", "graded", "unanswered"]


def test_rejected_evidence_does_not_write_grade(repository):
    class FakeEvidenceAI(MockInterviewAI):
        def grade_answer(self, *args):
            return {"score": 9.0, "feedback": "Invalid", "evidence": ["fabricated quote"],
                    "model": "fake-test", "used_fallback": False}
    service, item = create(repository, FakeEvidenceAI())
    item, job = submit(service, item, 0)
    service.grade_answer(OWNER, item["id"], 0, job)
    assert service.get(OWNER, item["id"])["answers"][0]["grading_status"] == "rejected"
    with repository.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grades)) == 0
    with pytest.raises(InterviewError):
        service.finalize(OWNER, item["id"], FinalizeInterview(revision=1))


def test_incomplete_children_are_not_silently_resumed(repository):
    service, item = create(repository)
    with repository.engine.begin() as connection:
        link = connection.scalar(select(session_questions.c.id).limit(1))
        connection.execute(delete(session_questions).where(session_questions.c.id == link))
    with pytest.raises(StorageFormatError):
        service.get(OWNER, item["id"])


def test_legacy_session_is_not_falsely_imported(repository):
    with repository.engine.begin() as connection:
        connection.execute(sessions.insert().values(id=str(uuid4()), user_id=OWNER, role="Old session"))
    with repository.engine.connect() as connection:
        old_id = connection.scalar(select(sessions.c.id))
    assert repository.get(old_id, OWNER) is None


def test_http_runtime_uses_postgres_and_report_survives_app_restart(repository, monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "postgres")
    monkeypatch.setenv("INTERVIEW_AI_PROVIDER", "mock")
    if repository.engine.dialect.name == "postgresql":
        with repository.engine.connect() as connection:
            schema = connection.scalar(select(func.current_schema()))
        url = repository.engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
        monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    else:
        monkeypatch.setenv("DATABASE_URL", "postgresql://fake-local/test")
        monkeypatch.setattr(PostgresInterviewRepository, "connect", lambda url: repository)
    def new_app():
        return create_app(demo_enabled=False, auth_resolver=lambda request: OWNER)
    with TestClient(new_app()) as client:
        created = client.post("/api/interviews", json={"job_profile": {"title": "Intern"}})
        assert created.status_code == 201
        path = "/api/interviews/" + created.json()["id"]
        revision = 0
        for index in range(3):
            submitted = client.post(f"{path}/answers/{index}", json={"revision": revision, "text": ANSWER})
            assert submitted.status_code == 202
            revision = submitted.json()["revision"]
        assert client.get(path + "/progress").json()["graded"] == 3
        result = client.post(path + "/finalize", json={"revision": revision})
        assert result.status_code == 200
        report = result.json()
    with TestClient(new_app()) as client:
        assert client.get(path).json() == report
        assert client.post(path + "/finalize", json={"revision": revision}).json() == report
