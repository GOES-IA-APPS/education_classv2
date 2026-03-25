import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@example.org"
os.environ["ADMIN_PASSWORD"] = "Admin!234"
os.environ["CREATE_SCHEMA_ON_STARTUP"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.core.bootstrap import initialize_phase1
from app.db import Base, SessionLocal, engine
from app.main import app
from app.utils.cache import clear_cache


@pytest.fixture(autouse=True)
def reset_database():
    clear_cache()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        initialize_phase1(db)
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
