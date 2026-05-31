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
