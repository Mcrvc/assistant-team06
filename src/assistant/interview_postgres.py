"""Relational interview repository for the LOCAL-04 schema proposal.

Uses the team's table names, plus the additions documented in
docs/interview-postgres.md. Never creates or migrates tables at runtime.
The schema is a proposal, not a claim that the live Supabase schema matches.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, MetaData,
    SmallInteger, String, Table, Text, Uuid, create_engine, delete, select, update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from assistant.interview_store import StoreConflict

metadata = MetaData()
document = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
identity = BigInteger().with_variant(Integer, "sqlite")

# Only the columns used by this repository are declared here. Other team tables
# and columns are preserved. Fixture DDL belongs to the integration tests.
accounts = Table("accounts", metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("username", String, nullable=False, unique=True),
)
sessions = Table("sessions", metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Uuid(as_uuid=False), ForeignKey("accounts.id")),
    Column("role", Text), Column("seniority", Text),
    Column("parsed_cv", Text), Column("created", DateTime(timezone=True)),
    Column("finished", Boolean), Column("finished_at", DateTime(timezone=True)),
    # Proposed additions; NULL marks a legacy session, which is not imported.
    Column("interview_format", Integer),
    Column("name", Text), Column("job_profile", document),
    Column("question_generation", document), Column("current_question", SmallInteger),
    Column("status", Text), Column("revision", Integer), Column("version", Integer),
    Column("report", document), Column("updated_at", DateTime(timezone=True)),
)
questions = Table("questions", metadata,
    Column("id", identity, primary_key=True, autoincrement=True),
    Column("question_text", Text), Column("role_hint", Text), Column("seniority", Text),
)
session_questions = Table("session_questions", metadata,
    Column("id", identity, primary_key=True, autoincrement=True),
    Column("session_id", Text, ForeignKey("sessions.id", ondelete="CASCADE")),
    Column("question_id", BigInteger, ForeignKey("questions.id", ondelete="CASCADE")),
    Column("display_order", SmallInteger), Column("grounded", Boolean),
    Column("question_snapshot", document),  # proposed: immutable rubric/source
)
answers = Table("answers", metadata,
    Column("id", identity, primary_key=True, autoincrement=True),
    Column("session_id", Text, ForeignKey("sessions.id", ondelete="CASCADE")),
    Column("question_id", BigInteger, ForeignKey("questions.id", ondelete="CASCADE")),
    Column("answer_text", Text),
    Column("grading_status", Text), Column("grading_id", Text), Column("error_code", Text),
)
grades = Table("grades", metadata,
    Column("id", identity, primary_key=True, autoincrement=True),
    Column("session_id", Text, ForeignKey("sessions.id", ondelete="CASCADE")),
    Column("question_id", BigInteger, ForeignKey("questions.id", ondelete="CASCADE")),
    Column("competency", Text), Column("level", SmallInteger),
    Column("evidence_quoted", Text), Column("accepted", Boolean),
    Column("result", document),  # proposed: complete Grade contract, score 0..10
)


class StorageFormatError(SQLAlchemyError):
    """Stored data cannot be resumed losslessly; do not silently invent fields."""


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso(value: datetime) -> str:
    # PostgreSQL preserves timezone, SQLite's test dialect does not.
    from datetime import timezone
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()


class PostgresInterviewRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @classmethod
    def connect(cls, url: str) -> PostgresInterviewRepository:
        try:
            parsed = make_url(url)
        except Exception:
            raise ValueError("Invalid interview database URL") from None
        if parsed.drivername not in ("postgres", "postgresql", "postgresql+psycopg"):
            raise ValueError("Interview database must use PostgreSQL with psycopg")
        parsed = parsed.set(drivername="postgresql+psycopg")
        engine = create_engine(parsed, pool_pre_ping=True, hide_parameters=True,
                               connect_args={"connect_timeout": 5})
        repository = cls(engine)
        try:
            repository.check_schema()
        except Exception:
            engine.dispose()
            raise SQLAlchemyError("Interview database unavailable or schema proposal not applied") from None
        return repository

    def check_schema(self) -> None:
        """Read-only startup probe: check required columns without reading rows."""
        with self.engine.connect() as connection:
            for table in metadata.sorted_tables:
                connection.execute(select(table).limit(0))

    @staticmethod
    def _session_values(item: dict) -> dict:
        return {
            "role": item["job_profile"]["title"], "seniority": item["job_profile"]["level"],
            "parsed_cv": item["cv"], "created": _date(item["created_at"]),
            "finished": item["status"] == "finalized",
            "finished_at": _date(item["updated_at"]) if item["status"] == "finalized" else None,
            "interview_format": 1,
            **{key: item[key] for key in ("name", "job_profile", "question_generation",
               "current_question", "status", "revision", "version", "report")},
            "updated_at": _date(item["updated_at"]),
        }

    def create(self, interview: dict) -> None:
        # Real user IDs must already exist in accounts; this repository does not
        # create profiles, Auth users, or domain-bank entries on the user's behalf.
        owner = str(UUID(interview["owner_id"]))
        with self.engine.begin() as connection:
            connection.execute(sessions.insert().values(
                id=interview["id"], user_id=owner, **self._session_values(interview)))
            for index, question in enumerate(interview["questions"]):
                question_id = connection.execute(questions.insert().values(
                    question_text=question["text"], role_hint=interview["job_profile"]["title"],
                    seniority=interview["job_profile"]["level"],
                ).returning(questions.c.id)).scalar_one()
                connection.execute(session_questions.insert().values(
                    session_id=interview["id"], question_id=question_id, display_order=index,
                    grounded=question["source_type"] == "reference", question_snapshot=question,
                ))
                self._write_answer(connection, interview["id"], question_id,
                                   interview["answers"][index])

    @staticmethod
    def _write_answer(connection, session_id: str, question_id: int, answer: dict) -> None:
        # Caller holds the session's write lock via its versioned UPDATE.
        # Preserve row IDs and other owners' columns (source/audio metadata).
        values = dict(answer_text=answer["text"],
            **{key: answer[key] for key in ("grading_status", "grading_id", "error_code")},
        )
        scope = (answers.c.session_id == session_id) & (answers.c.question_id == question_id)
        changed = connection.execute(update(answers).where(scope).values(**values)).rowcount
        if not changed:
            connection.execute(answers.insert().values(
                session_id=session_id, question_id=question_id, **values))
        grade_scope = (grades.c.session_id == session_id) & (grades.c.question_id == question_id)
        if answer["grading_status"] == "graded" and answer["grade"] is not None:
            grade = answer["grade"]
            values = dict(accepted=True,
                evidence_quoted=grade["evidence"][0] if len(grade["evidence"]) == 1 else None,
                result=grade,
                # competency/level stay NULL: the team has not agreed how the
                # complete question score maps to competency levels.
            )
            changed = connection.execute(update(grades).where(grade_scope).values(**values)).rowcount
            if not changed:
                connection.execute(grades.insert().values(
                    session_id=session_id, question_id=question_id, **values))
        else:
            connection.execute(delete(grades).where(grade_scope))

    def get(self, interview_id: str, owner_id: str) -> dict | None:
        try:
            owner = str(UUID(owner_id))
        except ValueError:
            return None
        with self.engine.begin() as connection:
            # One SELECT snapshot joins every child table. Multiple SELECTs at
            # READ COMMITTED could mix a session's old revision with new answers.
            joined = sessions.outerjoin(session_questions,
                sessions.c.id == session_questions.c.session_id).outerjoin(answers,
                (answers.c.session_id == sessions.c.id)
                & (answers.c.question_id == session_questions.c.question_id)).outerjoin(grades,
                (grades.c.session_id == sessions.c.id)
                & (grades.c.question_id == session_questions.c.question_id))
            rows = connection.execute(select(
                sessions, session_questions.c.display_order, session_questions.c.question_snapshot,
                answers.c.answer_text, answers.c.grading_status, answers.c.grading_id,
                answers.c.error_code, grades.c.result,
            ).select_from(joined).where(
                sessions.c.id == interview_id, sessions.c.user_id == owner,
                sessions.c.interview_format == 1,
            ).order_by(session_questions.c.display_order)).mappings().all()
        if not rows:
            return None
        if len(rows) != 3 or [row["display_order"] for row in rows] != [0, 1, 2]:
            raise StorageFormatError("Interview question/answer rows are incomplete or duplicated")
        row = rows[0]
        item = {
            "id": row["id"], "owner_id": row["user_id"], "cv": row["parsed_cv"],
            **{key: row[key] for key in ("name", "job_profile", "question_generation",
               "current_question", "status", "revision", "version", "report")},
            "created_at": _iso(row["created"]), "updated_at": _iso(row["updated_at"]),
            "questions": [r["question_snapshot"] for r in rows],
            "answers": [{"text": r["answer_text"], "grading_status": r["grading_status"],
                         "grading_id": r["grading_id"], "error_code": r["error_code"],
                         "grade": r["result"]} for r in rows],
        }
        if any(a["text"] is None or a["grading_status"] is None for a in item["answers"]):
            raise StorageFormatError("Interview answers are incomplete")
        return deepcopy(item)

    def save(self, interview: dict, expected_version: int) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(update(sessions).where(
                sessions.c.id == interview["id"], sessions.c.user_id == interview["owner_id"],
                sessions.c.interview_format == 1, sessions.c.version == expected_version,
            ).values(**self._session_values(interview))).rowcount
            if changed != 1:
                raise StoreConflict()
            links = connection.execute(select(
                session_questions.c.question_id, session_questions.c.display_order,
            ).where(session_questions.c.session_id == interview["id"])
              .order_by(session_questions.c.display_order)).all()
            if len(links) != 3 or [link.display_order for link in links] != [0, 1, 2]:
                raise StorageFormatError("Interview question links are incomplete or duplicated")
            for link in links:
                self._write_answer(connection, interview["id"], link.question_id,
                                   interview["answers"][link.display_order])

    def close(self) -> None:
        self.engine.dispose()
