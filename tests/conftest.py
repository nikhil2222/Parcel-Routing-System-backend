import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def app_client():
    with TestClient(app) as client:
        yield client