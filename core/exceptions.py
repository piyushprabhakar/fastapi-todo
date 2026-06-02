import sys
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class NotFoundException(Exception):
    def __init__(self, resource: str, id: int):
        self.resource = resource
        self.id = id


class AlreadyExistsException(Exception):
    def __init__(self, detail: str):
        self.detail = detail


async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"{exc.resource} with id {exc.id} not found"},
    )


async def already_exists_handler(request: Request, exc: AlreadyExistsException) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.detail},
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": e["loc"][-1], "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


async def global_handler(request: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )
