"""Opt-in PostgreSQL integration test; use a dedicated Neon branch/database."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

enabled = os.getenv("RUN_DB_TESTS", "false").lower() == "true"
pytestmark = pytest.mark.skipif(not enabled, reason="Set RUN_DB_TESTS=true for a dedicated test database")


def test_alert_event_loader_is_idempotent():
    from src.persistence.models import AlertEvent, Base
    from src.persistence.repository import PersistenceRepository
    from src.persistence.settings import PersistenceSettings

    url = PersistenceSettings().sqlalchemy_url
    if not url:
        pytest.skip("DATABASE_URL is not configured")
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    repository = PersistenceRepository(engine)
    # Unique synthetic event is isolated from all real source rows.
    started = pd.Timestamp.now(tz="UTC").floor("s")
    events = pd.DataFrame([{
        "oblast": f"integration-{uuid.uuid4()}", "raion": None, "hromada": None,
        "level": "oblast", "started_at": started,
        "finished_at": started + pd.Timedelta(minutes=5), "source": "integration-test",
    }])
    try:
        assert repository.upsert_alert_events(events) == 1
        assert repository.upsert_alert_events(events) == 0
        with engine.connect() as connection:
            count = connection.scalar(select(func.count()).select_from(AlertEvent).where(
                AlertEvent.alert_start == started,
                AlertEvent.region_name == events.iloc[0]["oblast"],
            ))
        assert count == 1
    finally:
        engine.dispose()
