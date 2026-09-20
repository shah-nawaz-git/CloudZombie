import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.clock import FixedClock
from app.persistence.models import Base
from app.providers.base import Attachment, Volume
from app.providers.demo import DemoDataset, load_demo_dataset


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url:
        engine = create_engine(database_url)
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(datetime(2026, 9, 20, 12, tzinfo=UTC))


@pytest.fixture
def demo_dataset() -> DemoDataset:
    return load_demo_dataset()


def make_volume(
    *,
    volume_id: str = "vol-0a1b2c3d4e5f60001",
    state: str = "available",
    attachments: tuple[Attachment, ...] = (),
    tags: dict[str, str] | None = None,
    created_at: datetime | None = None,
    volume_type: str = "gp3",
    size_gib: int = 100,
    iops: int | None = 3000,
    throughput_mibps: int | None = 125,
) -> Volume:
    return Volume(
        volume_id=volume_id,
        state=state,
        volume_type=volume_type,
        size_gib=size_gib,
        iops=iops,
        throughput_mibps=throughput_mibps,
        encrypted=True,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_id=None,
        attachments=attachments,
        tags=tags or {},
        availability_zone="us-east-1a",
    )
