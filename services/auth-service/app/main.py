from fastapi import Depends, FastAPI, Header, HTTPException, status
from jose import JWTError, jwt
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from app.auth_utils import ALGORITHM, SECRET_KEY, create_access_token, hash_password, verify_password
from app.database import Base, engine, get_db
from app.models import Token, User, UserCreate, UserLogin, UserOut

Base.metadata.create_all(bind=engine)

app = FastAPI(title="auth-service", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth-service"}


@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
