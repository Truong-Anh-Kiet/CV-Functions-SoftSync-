from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_mock_careerviet() -> None:
    original = settings.careerviet_mock_enabled
    settings.careerviet_mock_enabled = True
    yield
    settings.careerviet_mock_enabled = original


def test_search_careerviet_profiles_by_text() -> None:
    response = client.get("/api/v1/web-search/careerviet/profiles", params={"query": "database"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["source"] == "CareerViet"
    assert payload["data"]["items"]
    assert payload["data"]["items"][0]["title"] == "Supervisor Database"


def test_get_careerviet_profile_detail() -> None:
    response = client.get("/api/v1/web-search/careerviet/profiles/careerviet-101")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["id"] == "careerviet-101"
    assert payload["data"]["source"] == "CareerViet"
