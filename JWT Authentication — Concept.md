# JWT Authentication — Concept

## What is JWT Authentication?

JWT (JSON Web Token) authentication is a stateless way to secure API endpoints. Instead of storing sessions on the server, the server issues a signed token to the client on login. The client sends this token with every subsequent request, and the server verifies it without needing to query a database for session data.

---

## The Full Flow

```
REGISTER                          LOGIN                        PROTECTED ROUTE
────────                          ─────                        ───────────────
User sends                        User sends                   User sends request
email + password                  email + password             with header:
     │                                 │                       Authorization: Bearer <token>
     ▼                                 ▼                              │
Hash password                     Fetch user from DB                  ▼
with bcrypt                       Compare password hash         Decode & verify JWT
     │                                 │                              │
Save user to DB                   Create JWT token              Extract user_id
     │                            signed with SECRET_KEY              │
Return user info                       │                        Inject user into route
                                  Return token                  via Depends(get_current_user)
```

---

## Three Key Concepts

### 1. Password Hashing (bcrypt)

You never store plain text passwords in the database. `bcrypt` hashes them using a one-way algorithm that cannot be reversed.

```
"mysecret"  →  "$2b$12$abc...xyz"
```

- **On register** — hash the password before saving to DB
- **On login** — compare the incoming plain password against the stored hash using `verify_password()`
- Even if your database is compromised, attackers cannot recover the original passwords

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

> **Why not `passlib`?** `passlib` is unmaintained and incompatible with `bcrypt` 4+ — it crashes with `AttributeError: module 'bcrypt' has no attribute '__about__'`. Using `bcrypt` directly avoids this entirely.

---

### 2. JWT (JSON Web Token)

A JWT is a signed string made of 3 base64-encoded parts separated by dots:

```
header.payload.signature
```

**Header** — algorithm used to sign
```json
{ "alg": "HS256", "typ": "JWT" }
```

**Payload** — the data you embed (claims)
```json
{ "sub": "42", "exp": 1234567890 }
```
- `sub` (subject) — the user's ID
- `exp` — expiry timestamp (Unix time)

**Signature** — proves the token hasn't been tampered with
```
HMACSHA256(base64(header) + "." + base64(payload), SECRET_KEY)
```

Anyone can decode the header and payload — they are only base64 encoded, not encrypted. The **signature** is what makes it secure. Without your `SECRET_KEY`, no one can forge a valid token.

```python
from jose import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
```

> `datetime.now(timezone.utc)` is used instead of the deprecated `datetime.utcnow()`.

---

### 3. `Depends(get_current_user)` — FastAPI Dependency Injection

FastAPI's `Depends()` system lets you declare shared logic that runs before a route handler. `get_current_user` is a dependency that:

1. Reads the `Authorization: Bearer <token>` header from the request
2. Decodes and verifies the JWT
3. Looks up the user in the database
4. Returns the user object — or raises `401 Unauthorized` if anything fails

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from models.user import UserModel

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user
```

- `WWW-Authenticate: Bearer` header is included so clients know what auth scheme is expected
- A single `credentials_exception` object is reused for all failure paths — avoids leaking which check failed

Any route that adds `Depends(get_current_user)` is automatically protected:

```python
@router.get("/todos", response_model=list[Todo])
def get_all_todos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return crud.get_all(db)
```

The `_` name signals the user object is not needed in the route body — we only care that the token is valid.

---

## Project Structure

```
fastapi-todo/
├── main.py                        # Registers routers, middleware, exception handlers, creates tables
├── database.py                    # DB engine, session, Base
├── .env                           # DATABASE_URL, SECRET_KEY, ALGORITHM, EXPIRE_MINUTES
├── core/
│   ├── config.py                  # Loads JWT settings from .env
│   ├── security.py                # hash_password, verify_password, create_token, get_current_user
│   ├── middleware.py              # Request logging middleware
│   └── exceptions.py             # Custom exception classes and global handlers
├── models/
│   ├── todo.py                    # todos table
│   └── user.py                    # users table (id, email, hashed_password)
├── schemas/
│   ├── todo.py                    # Todo, TodoCreate, TodoUpdate
│   └── user.py                    # UserCreate, UserResponse, Token, TokenData
├── crud/
│   ├── todo.py                    # Todo DB operations
│   └── user.py                    # get_by_email(), create_user()
└── routers/
    ├── todos.py                   # Protected /todos routes
    └── auth.py                    # POST /auth/register, POST /auth/login
```

---

## API Endpoints

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Create a new user account |
| `POST` | `/auth/login` | No | Login and receive a JWT token |
| `GET` | `/todos` | Yes | Get all todos |
| `POST` | `/todos` | Yes | Create a todo |
| `GET` | `/todos/{id}` | Yes | Get a single todo |
| `PUT` | `/todos/{id}` | Yes | Update a todo |
| `DELETE` | `/todos/{id}` | Yes | Delete a todo |

---

## Environment Variables

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
SECRET_KEY=change-this-to-a-long-random-secret-key-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

- **`SECRET_KEY`** — used to sign and verify JWTs. Keep this private and random in production.
- **`ALGORITHM`** — `HS256` is HMAC with SHA-256, the most common JWT signing algorithm.
- **`ACCESS_TOKEN_EXPIRE_MINUTES`** — how long a token stays valid before the user must log in again.

---

## Request / Response Examples

### Register
```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```
```json
{ "id": 1, "email": "user@example.com" }
```

### Register — duplicate email
```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```
```json
{ "detail": "Email already registered" }
```

### Login
```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```
```json
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```

### Protected Route
```bash
curl http://127.0.0.1:8000/todos \
  -H "Authorization: Bearer eyJhbGci..."
```

### Invalid / missing token
```bash
curl http://127.0.0.1:8000/todos
# → {"detail": "Not authenticated"}

curl http://127.0.0.1:8000/todos -H "Authorization: Bearer badtoken"
# → {"detail": "Invalid or expired token"}
```

---

## Why Stateless?

Traditional session-based auth stores session data on the server and sends the client a session ID cookie. Every request hits the database to look up the session.

JWT auth is stateless — the token itself contains the user identity. The server only needs the `SECRET_KEY` to verify it. No session table, no extra DB query per request.

| | Session Auth | JWT Auth |
|---|---|---|
| State stored | Server (DB/memory) | Client (token) |
| DB query per request | Yes | No (only on protected routes that need user data) |
| Logout | Delete session from DB | Token expires naturally |
| Scalability | Harder (shared session store needed) | Easier (any server can verify the token) |
