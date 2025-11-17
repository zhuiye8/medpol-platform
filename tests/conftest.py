import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.persistence import models


@pytest.fixture(scope="session")
def temp_db_file():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def engine(temp_db_file):
    url = f"sqlite+pysqlite:///{temp_db_file}"
    engine = create_engine(url, future=True)
    models.Base.metadata.create_all(engine)
    yield engine
    models.Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine):
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def isolated_formatter_state(monkeypatch, tmp_path):
    from formatter_service import worker

    state_path = tmp_path / "formatter_seen.json"
    monkeypatch.setenv("FORMATTER_SEEN_PATH", str(state_path))
    worker.DEDUPER = worker.FormatterDeduper(state_path)
    yield
