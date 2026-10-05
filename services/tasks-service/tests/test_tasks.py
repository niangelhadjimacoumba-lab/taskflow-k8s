import os
import tempfile
from pathlib import Path

_db = Path(tempfile.gettempdir()) / f"test_tasks_{os.getpid()}.db"
if _db.exists():
    _db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from jose import jwt
import app.events as events_module

# On remplace Redis par un mock en memoire pour les tests
class FakeRedis:
    def publish(self, channel, payload):
        pass

events_module._client = FakeRedis()

from app.main import app

client = TestClient(app)


def _auth_header(user_id=1):
    token = jwt.encode({"sub": str(user_id)}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_create_list_update_delete_task():
    headers = _auth_header()

    r = client.post("/tasks", json={"title": "Ecrire le README"}, headers=headers)
    assert r.status_code == 201
    task_id = r.json()["id"]

    r = client.get("/tasks", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.put(f"/tasks/{task_id}", json={"done": True}, headers=headers)
    assert r.status_code == 200
    assert r.json()["done"] is True

    r = client.delete(f"/tasks/{task_id}", headers=headers)
    assert r.status_code == 204


def test_requires_auth():
    r = client.get("/tasks")
    assert r.status_code == 401
