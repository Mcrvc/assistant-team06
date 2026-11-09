"""SQLAlchemy local adapter. This is not the team's agreed PostgreSQL schema."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, create_engine, select, update, delete as sa_delete
from sqlalchemy.engine import Engine, URL


class StoreConflict(Exception):
    """An atomic update lost a race; reload before trying again."""


metadata = MetaData()
interviews = Table(
    "local_interviews", metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_id", String(200), nullable=False),
    Column("version", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
)


class SQLAlchemyInterviewRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @classmethod
    def local(cls, path: str | Path) -> SQLAlchemyInterviewRepository:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            URL.create("sqlite", database=str(path)),
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        metadata.create_all(engine)
        return cls(engine)

    def create(self, interview: dict) -> None:
        with self.engine.begin() as connection:
            connection.execute(interviews.insert().values(
                id=interview["id"], owner_id=interview["owner_id"],
                version=interview["version"], payload=interview,
            ))

    def get(self, interview_id: str, owner_id: str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(interviews.c.payload).where(
                interviews.c.id == interview_id, interviews.c.owner_id == owner_id,
            )).first()
        return deepcopy(row[0]) if row else None

    def list_for_owner(self, owner_id: str) -> list[dict]:
        """All interviews of one owner, newest first (history page)."""
        with self.engine.connect() as connection:
            rows = connection.execute(select(interviews.c.payload).where(
                interviews.c.owner_id == owner_id,
            )).all()
        items = [deepcopy(row[0]) for row in rows]
        return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)

    def save(self, interview: dict, expected_version: int) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(update(interviews).where(
                interviews.c.id == interview["id"], interviews.c.owner_id == interview["owner_id"],
                interviews.c.version == expected_version,
            ).values(version=interview["version"], payload=interview)).rowcount
            if changed != 1:
                raise StoreConflict()

    def delete(self, interview_id: str, owner_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(sa_delete(interviews).where(
                interviews.c.id == interview_id, interviews.c.owner_id == owner_id,
            ))

    def close(self) -> None:
        self.engine.dispose()
