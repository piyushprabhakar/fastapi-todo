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
