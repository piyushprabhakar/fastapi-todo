from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.todo import Todo, TodoCreate, TodoUpdate
from core.security import get_current_user
from core.exceptions import NotFoundException
import crud.todo as crud

router = APIRouter(prefix="/todos", tags=["todos"])


@router.post("", response_model=Todo, status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return crud.create(db, todo)


@router.get("", response_model=list[Todo])
def get_all_todos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return crud.get_all(db)


@router.get("/{todo_id}", response_model=Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    todo = crud.get_one(db, todo_id)
    if not todo:
        raise NotFoundException(resource="Todo", id=todo_id)
    return todo


@router.put("/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, updated: TodoUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    todo = crud.update(db, todo_id, updated)
    if not todo:
        raise NotFoundException(resource="Todo", id=todo_id)
    return todo


@router.delete("/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if not crud.delete(db, todo_id):
        raise NotFoundException(resource="Todo", id=todo_id)
