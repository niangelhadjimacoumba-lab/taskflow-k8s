import os
import json
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CHANNEL = "task-events"

_client = None


def get_redis_client():
    global _client
    if _client is None:
        _client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _client


def publish_task_event(event_type: str, user_id: int, task_id: int, title: str):
    """Publie un evenement sur le canal Redis consomme par notifications-service."""
    client = get_redis_client()
    payload = {
        "event": event_type,       # "task_created" | "task_completed" | "task_deleted"
        "user_id": user_id,
        "task_id": task_id,
        "title": title,
    }
    try:
        client.publish(CHANNEL, json.dumps(payload))
    except redis.exceptions.RedisError:
        # On ne bloque jamais l'API metier si Redis est indisponible.
        pass
