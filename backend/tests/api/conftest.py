import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.persistence.database import get_engine, get_session_factory


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    database = tmp_path / "api.db"
    monkeypatch.setenv("CLOUDZOMBIE_MODE", "demo")
    monkeypatch.setenv("CLOUDZOMBIE_DEMO_SEED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


def find_by_resource(client, resource_id):
    response = client.get("/api/findings", params={"q": resource_id})
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["resource_id"] == resource_id)
