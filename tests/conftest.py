"""
Pytest fixtures — in-memory SQLite test DB + FastAPI test client.
Uses StaticPool so all sessions share the same in-memory connection.
Tests that call NIM are automatically skipped without a real API key.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_db
from app.database import models  # noqa: F401 — registers all ORM models
from app.main import app

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(test_engine):
    Session = sessionmaker(bind=test_engine)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """Create a test user with a unique email per test to avoid conflicts."""
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "testpass123",
        "full_name": "Test User",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {"token": data["access_token"], "user": data["user"], "email": unique_email}


@pytest.fixture
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['token']}"}


def requires_nim(func):
    """Decorator: skip test if NVIDIA_NIM_API_KEY is not a real key."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = os.getenv("NVIDIA_NIM_API_KEY", "nvapi-demo")
        if not key or key.startswith("nvapi-demo"):
            pytest.skip("NVIDIA_NIM_API_KEY not configured")
        return func(*args, **kwargs)

    return wrapper
