from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List

# Stockage en memoire simple : {user_id: [notification, ...]}
_notifications: Dict[int, List[dict]] = defaultdict(list)
_lock = Lock()


def add_notification(user_id: int, message: str):
    with _lock:
        _notifications[user_id].append(
            {
                "message": message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def get_notifications(user_id: int) -> List[dict]:
    with _lock:
        return list(_notifications.get(user_id, []))
