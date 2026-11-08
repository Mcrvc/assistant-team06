from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from assistant.api import create_app
from assistant.interview_postgres import PostgresInterviewRepository
from assistant.interview_runtime import configured_repository
from assistant.interview_store import SQLAlchemyInterviewRepository


@pytest.fixture(autouse=True)
def clean_config(monkeypatch):
    for name in ("INTERVIEW_STORAGE", "INTERVIEW_LOCAL_STORAGE", "INTERVIEW_DEMO_ENABLED", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_default_does_not_connect_just_because_database_url_exists(monkeypatch):
    connect = Mock()
    monkeypatch.setattr(PostgresInterviewRepository, "connect", connect)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake-user:fake-password@invalid/db")
    assert configured_repository(demo_enabled=False) is None
    connect.assert_not_called()


def test_auto_keeps_existing_local_demo(monkeypatch, tmp_path):
    path = tmp_path / "demo.sqlite"
    monkeypatch.setenv("INTERVIEW_DB_PATH", str(path))
    repository = configured_repository(demo_enabled=True)
    try:
        assert isinstance(repository, SQLAlchemyInterviewRepository) and path.is_file()
    finally:
        repository.close()


def test_postgres_selection_is_explicit_and_does_not_create_sqlite(monkeypatch):
    expected = Mock()
    connect = Mock(return_value=expected)
    local = Mock()
    monkeypatch.setattr(PostgresInterviewRepository, "connect", connect)
    monkeypatch.setattr(SQLAlchemyInterviewRepository, "local", local)
    monkeypatch.setenv("INTERVIEW_STORAGE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake-user@localhost/test")
    monkeypatch.setenv("INTERVIEW_LOCAL_STORAGE", "1")
    assert configured_repository(demo_enabled=False) is expected
    connect.assert_called_once_with("postgresql://fake-user@localhost/test")
    local.assert_not_called()


def test_postgres_cannot_accept_demo_identity(monkeypatch):
    connect = Mock()
    monkeypatch.setattr(PostgresInterviewRepository, "connect", connect)
    monkeypatch.setenv("INTERVIEW_STORAGE", "postgres")
    with pytest.raises(ValueError, match="disable interview demo"):
        configured_repository(demo_enabled=True)
    connect.assert_not_called()


def test_missing_url_or_driver_never_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "postgres")
    local = Mock()
    monkeypatch.setattr(SQLAlchemyInterviewRepository, "local", local)
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        configured_repository(demo_enabled=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setattr(PostgresInterviewRepository, "connect", Mock(side_effect=ImportError("driver")))
    with pytest.raises(ValueError, match="postgres extra"):
        configured_repository(demo_enabled=False)
    local.assert_not_called()


@pytest.mark.parametrize("value", ["a private malformed URL", "sqlite:///test.sqlite", "postgresql+asyncpg://localhost/test"])
def test_bad_urls_are_rejected_without_echoing_input(value):
    with pytest.raises(ValueError) as exc:
        PostgresInterviewRepository.connect(value)
    assert value not in str(exc.value)


def test_schema_failure_disposes_pool_and_hides_connection_details(monkeypatch):
    engine = Mock()
    monkeypatch.setattr("assistant.interview_postgres.create_engine", Mock(return_value=engine))
    monkeypatch.setattr(PostgresInterviewRepository, "check_schema", Mock(
        side_effect=SQLAlchemyError("private connection and SQL details")))
    with pytest.raises(SQLAlchemyError) as exc:
        PostgresInterviewRepository.connect("postgresql://fake-user:fake-password@localhost/test")
    assert "private" not in str(exc.value) and "fake-password" not in str(exc.value)
    assert exc.value.__suppress_context__
    engine.dispose.assert_called_once()


def test_startup_failure_does_not_serve_a_silent_sqlite_fallback(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setattr(PostgresInterviewRepository, "connect", Mock(
        side_effect=SQLAlchemyError("Interview database unavailable")))
    local = Mock()
    monkeypatch.setattr(SQLAlchemyInterviewRepository, "local", local)
    with pytest.raises(SQLAlchemyError, match="unavailable"):
        with TestClient(create_app(demo_enabled=False)):
            pytest.fail("App should not start after a PostgreSQL failure")
    local.assert_not_called()


def test_invalid_storage_choice_is_not_echoed(monkeypatch):
    monkeypatch.setenv("INTERVIEW_STORAGE", "private-invalid-value")
    with pytest.raises(ValueError) as exc:
        configured_repository(demo_enabled=False)
    assert "private-invalid-value" not in str(exc.value)
