# Todo API — FastAPI + PostgreSQL

A simple REST API for managing todos, built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**.

---

## Project Structure

```
MyFirstProject/
├── main.py        # API routes and app entry point
├── models.py      # Pydantic schemas (request/response shapes)
├── db_models.py   # SQLAlchemy ORM model (database table)
├── database.py    # DB connection, session, and Base
├── .env           # Environment variables (DATABASE_URL)
├── pyproject.toml # Poetry dependencies
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

### 3. `db_models.py` — Database Table

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

### 4. `models.py` — Pydantic Schemas

```python
from pydantic import BaseModel
from typing import Optional

class Todo(BaseModel):
    id: int
    title: str
    description: str
    completed: bool = False

class TodoCreate(BaseModel):
    title: str
    description: str
    completed: bool = False

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
```

These are **Pydantic models** — they validate and shape the data coming in and going out of the API:

| Schema | Purpose |
|---|---|
| `Todo` | Full response shape (includes `id`) |
| `TodoCreate` | Request body for creating a todo (no `id` — DB generates it) |
| `TodoUpdate` | Request body for partial updates (all fields optional) |

> Pydantic models ≠ database models. Pydantic handles HTTP layer; SQLAlchemy handles the database layer.

---

### 5. `main.py` — API Routes

```python
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from models import Todo, TodoCreate, TodoUpdate
from database import engine, get_db
import db_models

db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")
```

`Base.metadata.create_all(bind=engine)` runs on startup — it creates the `todos` table if it doesn't already exist.

#### CREATE — `POST /todos`
```python
@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    new_todo = db_models.TodoModel(**todo.model_dump())
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo
```
- Accepts a `TodoCreate` body, converts it to a `TodoModel`, saves to DB
- `db.refresh()` re-reads the row so the DB-generated `id` is returned in the response

#### READ ALL — `GET /todos`
```python
@app.get("/todos", response_model=List[Todo])
def get_all_todos(db: Session = Depends(get_db)):
    return db.query(db_models.TodoModel).all()
```
- Queries all rows from the `todos` table

#### READ ONE — `GET /todos/{todo_id}`
```python
@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(db_models.TodoModel).filter(db_models.TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo
```
- Filters by `id`, returns 404 if not found

#### UPDATE — `PUT /todos/{todo_id}`
```python
@app.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, updated: TodoUpdate, db: Session = Depends(get_db)):
    todo = db.query(db_models.TodoModel).filter(db_models.TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    for field, value in updated.model_dump(exclude_none=True).items():
        setattr(todo, field, value)
    db.commit()
    db.refresh(todo)
    return todo
```
- `exclude_none=True` means only fields the client actually sent get updated (partial update)
- `setattr` dynamically sets each changed field on the ORM object

#### DELETE — `DELETE /todos/{todo_id}`
```python
@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(db_models.TodoModel).filter(db_models.TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(todo)
    db.commit()
```
- Deletes the row and returns `204 No Content` (no response body)

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
