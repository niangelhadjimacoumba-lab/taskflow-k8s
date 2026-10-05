import os
import tempfile
import uuid
from pathlib import Path

_db = Path(tempfile.gettempdir()) / f"test_auth_{os.getpid()}.db"
if _db.exists():
    _db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex}@example.com"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login():
    email = _unique_email()
    r = client.post("/register", json={"email": email, "password": "secret123"})
    assert r.status_code == 201

    r = client.post("/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_invalid_credentials():
    r = client.post("/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_jwt():
    r = client.get("/me")
    assert r.status_code == 401


def test_me_with_token():
    email = _unique_email()
    client.post("/register", json={"email": email, "password": "secret123"})
    token = client.post("/login", json={"email": email, "password": "secret123"}).json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email
