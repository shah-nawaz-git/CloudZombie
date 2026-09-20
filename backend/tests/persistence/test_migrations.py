from datetime import UTC, datetime

from alembic.config import Config
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect, select

from alembic import command
from app.core.config import get_settings
from app.persistence.models import Base
from app.persistence.types import UtcDateTime


def test_migration_table_set_and_utc_round_trip(tmp_path, monkeypatch) -> None:
    database = tmp_path / "migration.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    backend = __file__.rsplit("tests", 1)[0]
    config = Config(f"{backend}alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}

    metadata = MetaData()
    moments = Table(
        "moments",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("at", UtcDateTime(), nullable=False),
    )
    metadata.create_all(engine)
    expected = datetime(2026, 9, 20, 10, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(moments.insert().values(id=1, at=expected))
        actual = connection.execute(select(moments.c.at)).scalar_one()
    assert actual == expected
    assert actual.tzinfo is UTC
    get_settings.cache_clear()
