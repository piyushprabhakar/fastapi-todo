# Docker — End to End Guide

---

## What is Docker and Why Use It?

Docker packages your application and everything it needs (Python, dependencies, config) into a **container** — a self-contained unit that runs the same way on any machine.

Without Docker:
- "Works on my machine" problems
- Everyone on the team needs to install the same Python version, Postgres version, and all dependencies manually
- Different OS environments cause subtle bugs

With Docker:
- One command starts the entire stack
- Postgres and the API run together in isolated containers
- No local Python or Postgres installation needed

---

## Files Overview

```
fastapi-todo/
├── Dockerfile          # Recipe to build the API container image
├── docker-compose.yml  # Orchestrates API + PostgreSQL as one stack
└── .dockerignore       # Files excluded from the Docker build context
```

---

## How It All Fits Together

```
Your Machine
│
├── docker compose up
│        │
│        ▼
│   ┌─────────────────────────────────────────┐
│   │           Docker Network                │
│   │                                         │
│   │  ┌──────────────┐   ┌───────────────┐  │
│   │  │   db service │   │  api service  │  │
│   │  │  PostgreSQL  │◄──│   FastAPI     │  │
│   │  │  port: 5432  │   │   port: 8000  │  │
│   │  └──────────────┘   └───────────────┘  │
│   │         │                   │           │
│   └─────────┼───────────────────┼───────────┘
│             │                   │
│        localhost:5432      localhost:8000
│        (Postgres GUI)      (API / Swagger)
```

- The two services communicate over Docker's internal network using the service name `db` as the hostname
- Your machine accesses them via `localhost` on the mapped ports

---

## Part 1: `Dockerfile`

The Dockerfile is a step-by-step recipe for building the API container image.

```dockerfile
FROM python:3.12-slim
```
- Starts from the official Python 3.12 image
- `-slim` is a minimal variant — smaller size, only what's needed to run Python

```dockerfile
WORKDIR /app
```
- Sets `/app` as the working directory inside the container
- All subsequent commands (`COPY`, `RUN`, `CMD`) operate relative to `/app`

```dockerfile
COPY pyproject.toml .
```
- Copies only `pyproject.toml` first, before copying the rest of the code
- **Why?** Docker caches each step as a layer. If you copy all files at once and any source file changes, Docker reinstalls all dependencies from scratch. By copying `pyproject.toml` first, the dependency install layer is only invalidated when dependencies actually change — not when you edit `main.py`

```dockerfile
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction
```
- `pip install poetry` — installs the Poetry package manager
- `poetry config virtualenvs.create false` — tells Poetry to install packages directly into the system Python instead of creating a virtual environment (unnecessary inside a container)
- `poetry install --no-root` — installs all dependencies from `pyproject.toml`; `--no-root` skips installing the project itself as a package

```dockerfile
COPY . .
```
- Copies the rest of the source code into `/app`
- Happens after dependency install so code changes don't bust the cache

```dockerfile
EXPOSE 8000
```
- Documents that the container listens on port 8000
- Informational only — the actual port mapping is configured in `docker-compose.yml`

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
- The command that runs when the container starts
- `--host 0.0.0.0` — listens on all network interfaces inside the container (required so Docker can forward traffic from your machine into the container; `127.0.0.1` would only be accessible from inside the container itself)

### Build Caching — Visualised

```
Step 1: FROM python:3.12-slim          ← cached after first build
Step 2: WORKDIR /app                   ← cached
Step 3: COPY pyproject.toml .          ← only invalidated if deps change
Step 4: RUN pip install poetry && ...  ← only re-runs if pyproject.toml changed
Step 5: COPY . .                       ← invalidated on any code change
Step 6: EXPOSE 8000                    ← cached
Step 7: CMD [...]                      ← cached
```

This ordering means most code changes only re-run steps 5–7, making rebuilds fast.

---

## Part 2: `.dockerignore`

Before Docker builds an image, it sends all files in the project directory to the Docker daemon (called the **build context**). The `.dockerignore` file tells Docker which files to exclude.

```
# Python
.venv               ← local virtual environment — deps are reinstalled inside the image
__pycache__         ← compiled bytecode — regenerated at runtime
*.pyc / *.pyo       ← compiled Python files
*.egg-info          ← packaging metadata

# Environment
.env                ← NEVER bake secrets into an image

# Version control
.git                ← git history adds size with no benefit
.gitignore

# IDE
.idea               ← JetBrains config
.vscode             ← VS Code config

# Documentation
*.md                ← not needed at runtime

# Docker
Dockerfile          ← no need to include the build recipe inside the image
docker-compose.yml

# OS
.DS_Store           ← macOS metadata noise
```

**Why does `.env` exclusion matter?**
If `.env` were included in the image, anyone who pulls the image could extract your `SECRET_KEY` and database password. Always pass secrets via environment variables at runtime, never bake them into the image.

---

## Part 3: `docker-compose.yml`

Docker Compose defines and runs multiple containers as a single stack.

```yaml
services:
  db:
    image: postgres:16-alpine
```
- Uses the official PostgreSQL 16 image
- `-alpine` is a minimal Linux variant — smaller image size

```yaml
    restart: always
```
- Automatically restarts the container if it crashes or if Docker restarts

```yaml
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
```
- These variables are read by the official Postgres image on first start to create the database, user, and password

```yaml
    ports:
      - "5432:5432"
```
- Maps `host:container` port — lets you connect to Postgres from your machine using a GUI tool like TablePlus or DBeaver at `localhost:5432`

```yaml
    volumes:
      - postgres_data:/var/lib/postgresql/data
```
- Mounts a named volume at the path where Postgres stores its data files
- **Without this:** all data is lost every time the container stops
- **With this:** data persists across `docker compose down` and restarts

```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
```
- Runs `pg_isready` every 5 seconds to check if Postgres is accepting connections
- The `api` service won't start until this check passes — prevents the API from crashing because it tried to connect before Postgres was ready

```yaml
  api:
    build: .
```
- Builds the image from the `Dockerfile` in the current directory (`.`)
- Unlike `db` which uses a pre-built image, the API is built fresh from your code

```yaml
    ports:
      - "8000:8000"
```
- Maps port 8000 on your machine to port 8000 inside the container
- Access the API at `http://localhost:8000`

```yaml
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/postgres
```
- `db` in the URL is the service name — Docker resolves it to the `db` container's IP address automatically on the internal network
- This is why you can't use `localhost` here — `localhost` inside the `api` container refers to the `api` container itself, not the `db` container

```yaml
    depends_on:
      db:
        condition: service_healthy
```
- Waits for the `db` healthcheck to pass before starting the `api` container
- `condition: service_healthy` is stronger than plain `depends_on` — it waits for Postgres to actually accept connections, not just for the container to start

```yaml
volumes:
  postgres_data:
```
- Declares the named volume used by the `db` service
- Named volumes are managed by Docker and persist on your machine until explicitly deleted

---

## Part 4: End to End Startup Sequence

When you run `docker compose up --build`, this is what happens in order:

```
1. Docker reads docker-compose.yml

2. Builds the API image from Dockerfile
   └── Downloads python:3.12-slim (first time only)
   └── Installs Poetry and all dependencies
   └── Copies source code

3. Pulls postgres:16-alpine image (first time only)

4. Creates the Docker internal network

5. Starts the db container
   └── Initialises the postgres database
   └── Begins healthcheck every 5 seconds

6. Waits for db healthcheck to pass (pg_isready)

7. Starts the api container
   └── uvicorn starts on 0.0.0.0:8000
   └── SQLAlchemy connects to db:5432
   └── Creates todos and users tables if they don't exist

8. Both containers are running
   └── API available at http://localhost:8000
   └── Postgres available at localhost:5432
```

---

## Part 5: Common Commands

### Start

```bash
# Build images and start in foreground (see logs)
docker compose up --build

# Build images and start in background
docker compose up --build -d
```

### Logs

```bash
# Stream all logs
docker compose logs -f

# Stream only API logs
docker compose logs -f api

# Stream only database logs
docker compose logs -f db
```

### Stop

```bash
# Stop containers (data is preserved)
docker compose down

# Stop containers AND delete the database volume (wipes all data)
docker compose down -v
```

### Rebuild

```bash
# Rebuild only the API image (e.g. after a code change)
docker compose up --build api

# Force a full rebuild with no cache
docker compose build --no-cache
```

### Inspect

```bash
# List running containers
docker compose ps

# Open a shell inside the API container
docker compose exec api bash

# Open a Postgres shell inside the db container
docker compose exec db psql -U postgres
```

---

## Part 6: Testing After Start

Once `docker compose up --build` is running, test the full stack:

**Swagger UI:**
```
http://localhost:8000/docs
```

**Register a user:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'
```

**Use the token:**
```bash
curl http://localhost:8000/todos \
  -H "Authorization: Bearer <paste_token_here>"
```

---

## Part 7: Common Issues

### Port already in use
```
Error: Bind for 0.0.0.0:5432 failed: port is already allocated
```
Your local Postgres is running on port 5432. Either stop it first or change the host port in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # use 5433 on your machine instead
```

### API starts before DB is ready
This shouldn't happen because of `condition: service_healthy`, but if it does:
```bash
docker compose restart api
```

### Changes to code not reflected
You need to rebuild the API image:
```bash
docker compose up --build
```

### Wipe everything and start fresh
```bash
docker compose down -v       # removes containers + volume
docker compose up --build    # rebuilds from scratch
```
