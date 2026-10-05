from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import Base, engine, get_db
from app.models import Task, TaskCreate, TaskUpdate, TaskOut
from app.auth_deps import get_current_user_id
from app.events import publish_task_event

Base.metadata.create_all(bind=engine)

app = FastAPI(title="tasks-service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health():
    return {"status": "ok", "service": "tasks-service"}


@app.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    task = Task(user_id=user_id, title=payload.title, description=payload.description)
    db.add(task)
    db.commit()
    db.refresh(task)
    publish_task_event("task_created", user_id, task.id, task.title)
    return task


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(Task).filter(Task.user_id == user_id).all()


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    was_done = task.done
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)

    if not was_done and task.done:
        publish_task_event("task_completed", user_id, task.id, task.title)

    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    publish_task_event("task_deleted", user_id, task_id, task.title)
    return None
