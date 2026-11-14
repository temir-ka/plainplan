from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_home_sets_guest_cookie_once() -> None:
    with TestClient(app) as client:
        first = client.get("/")
        assert first.status_code == 200
        assert "hh_id" in first.cookies
        assert "httponly" in first.headers["set-cookie"].lower()

        second = client.get("/")  # client sends the cookie back
        assert "set-cookie" not in second.headers
