from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

from models import Todo, TodoCreate, TodoUpdate
from database import engine, get_db
import db_models

db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")


# ─── CREATE ───────────────────────────────────────────
@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    new_todo = db_models.TodoModel(**todo.model_dump())
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo


# ─── READ ALL ─────────────────────────────────────────
@app.get("/todos", response_model=list[Todo])
def get_all_todos(db: Session = Depends(get_db)):
    return db.query(db_models.TodoModel).all()


# ─── READ ONE ─────────────────────────────────────────
@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(db_models.TodoModel).filter(db_models.TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


# ─── UPDATE ───────────────────────────────────────────
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


# ─── DELETE ───────────────────────────────────────────
@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(db_models.TodoModel).filter(db_models.TodoModel.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(todo)
    db.commit()
