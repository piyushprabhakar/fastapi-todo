# Todo API — FastAPI + PostgreSQL

A simple REST API for managing todos, built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**.

---

## Project Structure

```
MyFirstProject/
├── main.py            # App entry point — registers routers, creates tables
├── database.py        # DB engine, session factory, and Base
├── .env               # Environment variables (DATABASE_URL)
├── pyproject.toml     # Poetry dependencies
├── routers/
│   └── todos.py       # HTTP routes for /todos endpoints
├── schemas/
│   └── todo.py        # Pydantic models (request/response shapes)
├── models/
│   └── todo.py        # SQLAlchemy ORM model (database table)
└── crud/
    └── todo.py        # Database operations (create, read, update, delete)
```

---

## How It Works

### 1. `.env` — Configuration

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
```

Stores the database connection string. Loaded at runtime using `python-dotenv` so credentials are never hardcoded.

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
- **`Base`** — all ORM models inherit from this; SQLAlchemy uses it to know which classes map to tables
- **`get_db()`** — a FastAPI dependency that opens a session before a request and closes it after, even if an error occurs

---

### 3. `models/todo.py` — Database Table

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

This is the **SQLAlchemy model** — it defines the actual `todos` table in PostgreSQL. Each `Column` maps to a column in the table. SQLAlchemy auto-generates the `id` (primary key) on insert.

---

### 4. `schemas/todo.py` — Pydantic Schemas

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

These are **Pydantic schemas** — they validate and shape the data coming in and going out of the API:

| Schema | Purpose |
|---|---|
| `TodoCreate` | Request body for creating a todo (no `id` — DB generates it) |
| `TodoUpdate` | Request body for partial updates (all fields optional) |
| `Todo` | Full response shape (includes `id`) |

> `from_attributes = True` allows Pydantic to read data directly from SQLAlchemy ORM objects.

> Pydantic schemas ≠ database models. Pydantic handles the HTTP layer; SQLAlchemy handles the database layer.

---

### 5. `crud/todo.py` — Database Operations

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

This layer contains all database logic, keeping routes clean:

- **`get_all`** — fetches every row from `todos`
- **`get_one`** — fetches a single row by `id`, returns `None` if not found
- **`create`** — inserts a new row, refreshes to get the DB-generated `id`
- **`update`** — applies only the fields that were sent (`exclude_none=True`)
- **`delete`** — removes the row, returns `False` if it didn't exist

---

### 6. `routers/todos.py` — HTTP Routes

```python
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.todo import Todo, TodoCreate, TodoUpdate
import crud.todo as crud

router = APIRouter(prefix="/todos", tags=["todos"])


@router.post("", response_model=Todo, status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    return crud.create(db, todo)


@router.get("", response_model=list[Todo])
def get_all_todos(db: Session = Depends(get_db)):
    return crud.get_all(db)


@router.get("/{todo_id}", response_model=Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = crud.get_one(db, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.put("/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, updated: TodoUpdate, db: Session = Depends(get_db)):
    todo = crud.update(db, todo_id, updated)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.delete("/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    if not crud.delete(db, todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
```

Routes are responsible only for HTTP concerns — accepting requests, calling the right crud function, and returning HTTP errors when something isn't found. No DB logic lives here.

- **`APIRouter`** with `prefix="/todos"` means all routes automatically start with `/todos`
- **`Depends(get_db)`** injects a DB session into each route automatically

---

### 7. `main.py` — App Entry Point

```python
from fastapi import FastAPI
from database import engine
from models.todo import TodoModel
from routers import todos

TodoModel.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")

app.include_router(todos.router)
```

- `metadata.create_all(bind=engine)` — creates the `todos` table on startup if it doesn't exist
- `app.include_router(todos.router)` — registers all routes from `routers/todos.py`

---

## Setup & Running

### Prerequisites
- Python 3.12+
- PostgreSQL running locally
- Poetry installed

### Install dependencies
```bash
poetry install
```

### Configure environment
Edit `.env` with your Postgres credentials:
```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<dbname>
```

### Start the server
```bash
poetry run uvicorn main:app --reload
```

### Open the interactive docs
```
http://127.0.0.1:8000/docs
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/todos` | Create a new todo |
| `GET` | `/todos` | Get all todos |
| `GET` | `/todos/{id}` | Get a single todo |
| `PUT` | `/todos/{id}` | Update a todo |
| `DELETE` | `/todos/{id}` | Delete a todo |

### Example Request — Create Todo
```bash
curl -X POST http://127.0.0.1:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "description": "From the store", "completed": false}'
```

### Example Response
```json
{
  "id": 1,
  "title": "Buy milk",
  "description": "From the store",
  "completed": false
}
```
