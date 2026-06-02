# fastapi-todo

A REST API for managing todos with JWT authentication, request logging middleware, centralized error handling, and Docker support — built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Auth | JWT (python-jose) + bcrypt |
| Validation | Pydantic v2 |
| Package manager | Poetry |
| Container | Docker + Docker Compose |

---

## Project Structure

```
fastapi-todo/
├── main.py                    # App entry point — registers routers, middleware, exception handlers
├── database.py                # DB engine, session factory, and Base
├── .env                       # Environment variables (not committed — create manually)
├── pyproject.toml             # Poetry dependencies
├── Dockerfile                 # Container image definition
├── docker-compose.yml         # Orchestrates API + PostgreSQL containers
├── .dockerignore              # Files excluded from the Docker build context
├── core/
│   ├── config.py              # Loads JWT settings from .env
│   ├── security.py            # Password hashing, JWT creation, get_current_user
│   ├── middleware.py          # Request logging middleware
│   └── exceptions.py         # Custom exception classes and global exception handlers
├── routers/
│   ├── auth.py                # POST /auth/register, POST /auth/login
│   └── todos.py               # Protected /todos endpoints
├── schemas/
│   ├── user.py                # Pydantic schemas for auth (UserCreate, Token, etc.)
│   └── todo.py                # Pydantic schemas for todos
├── models/
│   ├── user.py                # SQLAlchemy users table
│   └── todo.py                # SQLAlchemy todos table
└── crud/
    ├── user.py                # get_by_email(), create_user()
    └── todo.py                # Todo DB operations
```

---

## Quick Start

### Option A: Docker (Recommended — no local Python or Postgres needed)

```bash
git clone https://github.com/<your-username>/fastapi-todo.git
cd fastapi-todo
docker compose up --build
```

API is available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

---

### Option B: Run Locally

**1. Clone the repo**
```bash
git clone https://github.com/<your-username>/fastapi-todo.git
cd fastapi-todo
```

**2. Install dependencies**
```bash
poetry install
```

**3. Create `.env`**

`.env` is not committed to git. Create it manually in the project root:
```bash
touch .env
```

Add the following content:
```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<dbname>
SECRET_KEY=change-this-to-a-long-random-secret-key-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Replace `<user>`, `<password>`, and `<dbname>` with your local PostgreSQL credentials.

**4. Make sure PostgreSQL is running locally**

On Mac with Homebrew:
```bash
brew services start postgresql
```

Create the database if it doesn't exist:
```bash
psql -U postgres -c "CREATE DATABASE <dbname>;"
```

**5. Start the server**
```bash
poetry run uvicorn main:app --reload
```

API is available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

---

## Docker Commands

```bash
docker compose up --build        # build and start (foreground)
docker compose up --build -d     # build and start (background)
docker compose logs -f api       # stream API logs
docker compose logs -f db        # stream DB logs
docker compose down              # stop containers (data preserved)
docker compose down -v           # stop containers + delete database volume
docker compose up --build api    # rebuild only the API after code changes
```

---

## API Reference

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Register a new user |
| `POST` | `/auth/login` | No | Login and receive a JWT token |
| `GET` | `/todos` | Yes | Get all todos |
| `POST` | `/todos` | Yes | Create a new todo |
| `GET` | `/todos/{id}` | Yes | Get a single todo |
| `PUT` | `/todos/{id}` | Yes | Update a todo (partial) |
| `DELETE` | `/todos/{id}` | Yes | Delete a todo |

---

## How It Works

### 1. `.env` — Configuration

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
SECRET_KEY=change-this-to-a-long-random-secret-key-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

- **`DATABASE_URL`** — PostgreSQL connection string
- **`SECRET_KEY`** — used to sign and verify JWTs. Must be kept private.
- **`ALGORITHM`** — `HS256` (HMAC with SHA-256), the standard JWT signing algorithm
- **`ACCESS_TOKEN_EXPIRE_MINUTES`** — how long a token stays valid before the user must log in again

---

### 2. `database.py` — Database Setup

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- **`engine`** — establishes the connection to PostgreSQL
- **`SessionLocal`** — factory that creates a new DB session per request
- **`Base`** — all ORM models inherit from this
- **`get_db()`** — FastAPI dependency that opens a session before a request and closes it after

---

### 3. `core/config.py` — JWT Settings

```python
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
```

Loads JWT settings from `.env` into module-level constants used by `security.py`.

---

### 4. `core/security.py` — Auth Logic

```python
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from models.user import UserModel

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user
```

- **`hash_password`** — one-way bcrypt hash; never store plain passwords
- **`verify_password`** — compares plain input against stored hash on login
- **`create_access_token`** — builds a JWT with the user's `id` as `sub` and an expiry time
- **`oauth2_scheme`** — tells FastAPI to read `Authorization: Bearer <token>` from request headers
- **`get_current_user`** — decodes the token, validates it, fetches the user; raises `401` on any failure

> **Why not `passlib`?** `passlib` is unmaintained and incompatible with `bcrypt` 4+ — it crashes with `AttributeError: module 'bcrypt' has no attribute '__about__'`. Using `bcrypt` directly avoids this entirely.

---

### 5. `core/middleware.py` — Request Logging

```python
import time
from fastapi import Request


async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    print(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    return response
```

Logs every request to stdout:

```
POST /auth/login → 200 (43.2ms)
GET /todos → 200 (12.1ms)
GET /todos/999 → 404 (8.7ms)
```

---

### 6. `core/exceptions.py` — Custom Exceptions & Global Handlers

```python
import sys
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class NotFoundException(Exception):
    def __init__(self, resource: str, id: int):
        self.resource = resource
        self.id = id


class AlreadyExistsException(Exception):
    def __init__(self, detail: str):
        self.detail = detail


async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"{exc.resource} with id {exc.id} not found"},
    )


async def already_exists_handler(request: Request, exc: AlreadyExistsException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.detail})


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


async def global_handler(request: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})
```

| Handler | Catches | Status | Response |
|---|---|---|---|
| `not_found_handler` | `NotFoundException` | 404 | `{"detail": "Todo with id 5 not found"}` |
| `already_exists_handler` | `AlreadyExistsException` | 400 | `{"detail": "Email already registered"}` |
| `validation_handler` | `RequestValidationError` | 422 | `{"detail": [{"field": "title", "message": "Field required"}]}` |
| `global_handler` | Any unhandled `Exception` | 500 | `{"detail": "An unexpected error occurred"}` |

---

### 7. `models/user.py` — Users Table

```python
from sqlalchemy import Column, Integer, String
from database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
```

---

### 8. `models/todo.py` — Todos Table

```python
from sqlalchemy import Column, Integer, String, Boolean
from database import Base


class TodoModel(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    completed = Column(Boolean, default=False)
```

---

### 9. `schemas/user.py` — Auth Pydantic Schemas

```python
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: int | None = None
```

| Schema | Used for |
|---|---|
| `UserCreate` | Request body for `/auth/register` and `/auth/login` |
| `UserResponse` | Response after register (no password returned) |
| `Token` | Response after login — contains the JWT |
| `TokenData` | Internal helper to hold decoded token payload |

---

### 10. `schemas/todo.py` — Todo Pydantic Schemas

```python
from pydantic import BaseModel
from typing import Optional


class TodoCreate(BaseModel):
    title: str
    description: str
    completed: bool = False


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


class Todo(BaseModel):
    id: int
    title: str
    description: str
    completed: bool = False

    class Config:
        from_attributes = True
```

---

### 11. `crud/user.py` — User DB Operations

```python
from sqlalchemy.orm import Session
from models.user import UserModel
from schemas.user import UserCreate
from core.security import hash_password


def get_by_email(db: Session, email: str) -> UserModel | None:
    return db.query(UserModel).filter(UserModel.email == email).first()


def create_user(db: Session, user: UserCreate) -> UserModel:
    new_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
```

---

### 12. `crud/todo.py` — Todo DB Operations

```python
from sqlalchemy.orm import Session
from models.todo import TodoModel
from schemas.todo import TodoCreate, TodoUpdate


def get_all(db: Session) -> list[TodoModel]:
    return db.query(TodoModel).all()

def get_one(db: Session, todo_id: int) -> TodoModel | None:
    return db.query(TodoModel).filter(TodoModel.id == todo_id).first()

def create(db: Session, todo: TodoCreate) -> TodoModel:
    new_todo = TodoModel(**todo.model_dump())
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo

def update(db: Session, todo_id: int, updated: TodoUpdate) -> TodoModel | None:
    todo = get_one(db, todo_id)
    if not todo:
        return None
    for field, value in updated.model_dump(exclude_none=True).items():
        setattr(todo, field, value)
    db.commit()
    db.refresh(todo)
    return todo

def delete(db: Session, todo_id: int) -> bool:
    todo = get_one(db, todo_id)
    if not todo:
        return False
    db.delete(todo)
    db.commit()
    return True
```

---

### 13. `routers/auth.py` — Auth Routes

```python
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, UserResponse, Token
from crud.user import get_by_email, create_user
from core.security import verify_password, create_access_token
from core.exceptions import AlreadyExistsException

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if get_by_email(db, user.email):
        raise AlreadyExistsException(detail="Email already registered")
    return create_user(db, user)


@router.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_by_email(db, user.email)
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}
```

- **`/register`** — raises `AlreadyExistsException` if email is taken; caught globally → 400
- **`/login`** — keeps `HTTPException(401)` since it's tied to the HTTP auth spec

---

### 14. `routers/todos.py` — Protected Todo Routes

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.todo import Todo, TodoCreate, TodoUpdate
from core.security import get_current_user
from core.exceptions import NotFoundException
import crud.todo as crud

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("/{todo_id}", response_model=Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    todo = crud.get_one(db, todo_id)
    if not todo:
        raise NotFoundException(resource="Todo", id=todo_id)
    return todo

# ... same pattern for create, update, and delete
```

- All routes protected with `Depends(get_current_user)` → `401` if token is missing or invalid
- Missing records raise `NotFoundException` → caught globally → `404` with descriptive message

---

### 15. `main.py` — App Entry Point

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from database import engine
from models.todo import TodoModel
from models.user import UserModel
from routers import todos, auth
from core.middleware import logging_middleware
from core.exceptions import (
    NotFoundException, not_found_handler,
    AlreadyExistsException, already_exists_handler,
    validation_handler, global_handler,
)

TodoModel.metadata.create_all(bind=engine)
UserModel.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(logging_middleware)

app.add_exception_handler(NotFoundException, not_found_handler)
app.add_exception_handler(AlreadyExistsException, already_exists_handler)
app.add_exception_handler(RequestValidationError, validation_handler)
app.add_exception_handler(Exception, global_handler)

app.include_router(auth.router)
app.include_router(todos.router)
```

- **CORS middleware** — allows frontend apps on any origin to call the API
- **Logging middleware** — logs every request with method, path, status, and duration
- **Exception handlers** — every error type has a consistent JSON response shape

---

## How to Test

### Option 1: Swagger UI (Recommended)

1. Open `http://localhost:8000/docs`
2. Call `POST /auth/register` to create a user
3. Call `POST /auth/login` — copy the `access_token` from the response
4. Click the **Authorize** button (top right), paste the token, click **Authorize**
5. All `/todos` routes are now unlocked — test them directly in the UI

---

### Option 2: curl (Terminal)

**Register**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```
```json
{ "id": 1, "email": "user@example.com" }
```

**Login**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```
```json
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```

**Create a todo**
```bash
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGci..." \
  -d '{"title": "Buy milk", "description": "From the store"}'
```

**Get all todos**
```bash
curl http://localhost:8000/todos \
  -H "Authorization: Bearer eyJhbGci..."
```

**Update a todo**
```bash
curl -X PUT http://localhost:8000/todos/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGci..." \
  -d '{"completed": true}'
```

**Delete a todo**
```bash
curl -X DELETE http://localhost:8000/todos/1 \
  -H "Authorization: Bearer eyJhbGci..."
```

---

### Error Response Reference

| Scenario | Status | Response |
|---|---|---|
| Duplicate email | 400 | `{"detail": "Email already registered"}` |
| Wrong password | 401 | `{"detail": "Invalid email or password"}` |
| No token | 401 | `{"detail": "Not authenticated"}` |
| Invalid token | 401 | `{"detail": "Invalid or expired token"}` |
| Todo not found | 404 | `{"detail": "Todo with id 999 not found"}` |
| Missing field | 422 | `{"detail": [{"field": "title", "message": "Field required"}]}` |
| Server error | 500 | `{"detail": "An unexpected error occurred"}` |
