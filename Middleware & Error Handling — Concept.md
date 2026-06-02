# Middleware & Error Handling — Concept

---

## Part 1: Middleware

### What is Middleware?

Middleware is a layer that sits between the web server and your route handlers. Every single request passes through it on the way in, and every response passes through it on the way out — regardless of which route is called.

```
Incoming Request
       │
       ▼
┌─────────────────┐
│   Middleware 1  │  ← e.g. Logging
│   Middleware 2  │  ← e.g. CORS
│   Middleware 3  │  ← e.g. Timing
└─────────────────┘
       │
       ▼
  Route Handler
       │
       ▼
┌─────────────────┐
│   Middleware 3  │  ← response passes back through in reverse
│   Middleware 2  │
│   Middleware 1  │
└─────────────────┘
       │
       ▼
Outgoing Response
```

### How to Write Custom Middleware

```python
from fastapi import Request
import time

async def my_middleware(request: Request, call_next):
    start = time.time()

    response = await call_next(request)  # calls the next middleware or route

    duration = time.time() - start
    response.headers["X-Process-Time"] = str(duration)
    return response

# Register it in main.py:
app.middleware("http")(my_middleware)
```

- `request` — the incoming HTTP request (method, url, headers, body)
- `call_next(request)` — passes the request down the chain and returns the response
- Everything **before** `call_next` runs on the way in
- Everything **after** `call_next` runs on the way out

### Built-in Middleware

FastAPI ships with middleware for common needs:

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# CORS — allow cross-origin requests from browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip — compress large responses automatically
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted Hosts — reject requests with unknown Host headers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["example.com"])
```

### Middleware Execution Order

Middleware added **last** runs **first** on the way in (LIFO — Last In, First Out):

```python
app.add_middleware(MiddlewareA)  # runs second
app.add_middleware(MiddlewareB)  # runs first
```

```
Request  →  MiddlewareB  →  MiddlewareA  →  Route
Response ←  MiddlewareB  ←  MiddlewareA  ←  Route
```

### Common Middleware Use Cases

| Middleware | What it does |
|---|---|
| **Logging** | Record every request's method, path, status code, duration |
| **CORS** | Allow browser apps on other domains to call your API |
| **Timing** | Measure how long each request takes |
| **Auth check** | Validate a token before the request reaches any route |
| **Rate limiting** | Block clients making too many requests |
| **Compression** | Gzip large responses to reduce bandwidth |

---

## Part 2: Error Handling

### The Problem Without Error Handling

If an unhandled exception occurs, FastAPI returns a plain `500 Internal Server Error` with no useful detail. Good error handling means:
- Every error returns a **consistent JSON shape**
- Clients always know what went wrong
- Sensitive server details never leak in responses
- Errors are logged for debugging

### Layer 1 — `HTTPException` (route-level)

The standard way to return an error from a route:

```python
from fastapi import HTTPException

@app.get("/items/{id}")
def get_item(id: int):
    item = db.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

FastAPI catches `HTTPException` and returns:
```json
{ "detail": "Item not found" }
```

### Layer 2 — Custom Exception Classes

Define your own exception types so errors carry semantic meaning instead of HTTP status codes:

```python
class NotFoundException(Exception):
    def __init__(self, resource: str, id: int):
        self.resource = resource
        self.id = id

class AlreadyExistsException(Exception):
    def __init__(self, detail: str):
        self.detail = detail
```

Then raise them anywhere without worrying about HTTP status codes:

```python
raise NotFoundException(resource="Todo", id=42)
raise AlreadyExistsException(detail="Email already registered")
```

### Layer 3 — Exception Handlers (global)

Register handlers that catch specific exception types across the entire app. In this project, handlers are defined as plain async functions in `core/exceptions.py` and registered in `main.py` using `app.add_exception_handler()`:

```python
# core/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse

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
```

```python
# main.py
app.add_exception_handler(NotFoundException, not_found_handler)
app.add_exception_handler(AlreadyExistsException, already_exists_handler)
```

### Layer 4 — Override Built-in Handlers

FastAPI has a default handler for `RequestValidationError` (422). Override it to return cleaner errors:

```python
from fastapi.exceptions import RequestValidationError

async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": e["loc"][-1], "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})

# main.py
app.add_exception_handler(RequestValidationError, validation_handler)
```

Default 422 response (verbose):
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {},
      "url": "..."
    }
  ]
}
```

Custom 422 response (clean):
```json
{
  "detail": [
    { "field": "title", "message": "Field required" }
  ]
}
```

### Layer 5 — Global Fallback (catch-all)

Catch any unhandled exception to prevent raw 500 errors leaking stack traces:

```python
import sys

async def global_handler(request: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )

# main.py
app.add_exception_handler(Exception, global_handler)
```

- Logs the real exception type and message to stderr for debugging
- Returns a safe, generic message to the client — never exposes stack traces

---

## How All Layers Work Together

```
Incoming Request
       │
       ▼
  Middleware (CORS, logging)
       │
       ▼
  Route Handler
       │
  raises Exception?
       │
       ├── NotFoundException       → not_found_handler       → 404 JSON
       ├── AlreadyExistsException  → already_exists_handler  → 400 JSON
       ├── RequestValidationError  → validation_handler      → 422 JSON
       ├── HTTPException           → FastAPI default handler  → JSON response
       └── Any other Exception    → global_handler           → 500 JSON
```

---

## What's Implemented in This Project

### Project Structure

```
fastapi-todo/
├── main.py                    # Registers middleware and exception handlers
└── core/
    ├── middleware.py          # logging_middleware
    └── exceptions.py         # NotFoundException, AlreadyExistsException + 4 handlers
```

### `core/middleware.py` — Request Logging

```python
import time
from fastapi import Request


async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    print(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    return response
```

Sample output on every request:
```
POST /auth/login → 200 (43.2ms)
GET /todos → 200 (12.1ms)
GET /todos/999 → 404 (8.7ms)
```

### `core/exceptions.py` — Full Implementation

```python
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
```

### `main.py` — Registration

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from core.middleware import logging_middleware
from core.exceptions import (
    NotFoundException, not_found_handler,
    AlreadyExistsException, already_exists_handler,
    validation_handler, global_handler,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(logging_middleware)

app.add_exception_handler(NotFoundException, not_found_handler)
app.add_exception_handler(AlreadyExistsException, already_exists_handler)
app.add_exception_handler(RequestValidationError, validation_handler)
app.add_exception_handler(Exception, global_handler)
```

### Error Response Reference

| Scenario | Exception raised | HTTP | Response |
|---|---|---|---|
| Todo ID doesn't exist | `NotFoundException` | 404 | `{"detail": "Todo with id 5 not found"}` |
| Duplicate email on register | `AlreadyExistsException` | 400 | `{"detail": "Email already registered"}` |
| Missing required field | `RequestValidationError` | 422 | `{"detail": [{"field": "title", "message": "Field required"}]}` |
| Invalid/missing JWT | `HTTPException` | 401 | `{"detail": "Invalid or expired token"}` |
| Unhandled server error | `Exception` | 500 | `{"detail": "An unexpected error occurred"}` |
