from fastapi.testclient import TestClient
from app.store import add_notification
import app.listener as listener_module

# On evite de lancer le vrai thread Redis pendant les tests unitaires
listener_module.start_listener_thread = lambda: None

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_notifications_empty_by_default():
    r = client.get("/notifications/42")
    assert r.status_code == 200
    assert r.json() == []


def test_notifications_after_add():
    add_notification(42, "Nouvelle tache creee : Demo")
    r = client.get("/notifications/42")
    assert r.status_code == 200
    assert len(r.json()) == 1
