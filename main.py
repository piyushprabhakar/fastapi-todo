from fastapi import FastAPI
from database import engine
from models.todo import TodoModel
from routers import todos

TodoModel.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")

app.include_router(todos.router)
