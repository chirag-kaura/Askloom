from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "Askloom",
    }


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Askloom API"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"
