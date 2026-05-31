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
