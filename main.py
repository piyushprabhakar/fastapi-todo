from fastapi import FastAPI, HTTPException
from models import Todo, TodoCreate, TodoUpdate
from typing import List

app = FastAPI(title="Todo API", version="1.0.0")

# In-memory database (a simple list for now)
todos: List[Todo] = []
counter: int = 1


# ─── CREATE ───────────────────────────────────────────
@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(todo: TodoCreate):
    global counter
    new_todo = Todo(
        id=counter,
        title=todo.title,
        description=todo.description,
        completed=todo.completed
    )
    todos.append(new_todo)
    counter += 1
    return new_todo


# ─── READ ALL ─────────────────────────────────────────
@app.get("/todos", response_model=List[Todo])
def get_all_todos():
    return todos


# ─── READ ONE ─────────────────────────────────────────
@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int):
    for todo in todos:
        if todo.id == todo_id:
            return todo
    raise HTTPException(status_code=404, detail="Todo not found")


# ─── UPDATE ───────────────────────────────────────────
@app.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, updated: TodoUpdate):
    for index, todo in enumerate(todos):
        if todo.id == todo_id:
            if updated.title is not None:
                todos[index].title = updated.title
            if updated.description is not None:
                todos[index].description = updated.description
            if updated.completed is not None:
                todos[index].completed = updated.completed
            return todos[index]
    raise HTTPException(status_code=404, detail="Todo not found")


# ─── DELETE ───────────────────────────────────────────
@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    for index, todo in enumerate(todos):
        if todo.id == todo_id:
            todos.pop(index)
            return
    raise HTTPException(status_code=404, detail="Todo not found")