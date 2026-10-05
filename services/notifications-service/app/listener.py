import os
import json
import threading
import time
import redis

from app.store import add_notification

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CHANNEL = "task-events"

MESSAGES = {
    "task_created": "Nouvelle tache creee : {title}",
    "task_completed": "Tache terminee : {title}",
    "task_deleted": "Tache supprimee : {title}",
}


def _build_message(event: dict) -> str:
    template = MESSAGES.get(event.get("event"), "Evenement : {title}")
    return template.format(title=event.get("title", ""))


def _listen_loop():
    """Boucle de consommation Redis pub/sub, relance automatique si la connexion tombe."""
    while True:
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            pubsub = client.pubsub()
            pubsub.subscribe(CHANNEL)
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                    add_notification(event["user_id"], _build_message(event))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        except redis.exceptions.RedisError:
            time.sleep(3)  # Redis pas encore pret : on retente


def start_listener_thread():
    thread = threading.Thread(target=_listen_loop, daemon=True)
    thread.start()
    return thread
