from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import List
from prometheus_fastapi_instrumentator import Instrumentator

from app.store import get_notifications
from app.listener import start_listener_thread


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_listener_thread()
    yield


app = FastAPI(title="notifications-service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health():
    return {"status": "ok", "service": "notifications-service"}


@app.get("/notifications/{user_id}", response_model=List[dict])
def notifications(user_id: int):
    return get_notifications(user_id)
