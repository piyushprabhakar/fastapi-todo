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
