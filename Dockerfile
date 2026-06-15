# syntax=docker/dockerfile:1

# Stage 1: build the Next.js static export
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime serving FastAPI + static frontend
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies from the lockfile (no dev deps)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the backend application
COPY backend/ ./

# Install the project itself now that the source is present
RUN uv sync --frozen --no-dev

# Copy the frontend static export into the dir the backend serves from
COPY --from=frontend /frontend/out ./app/static

# Persisted SQLite lives outside the source tree so the volume mount does not
# shadow backend/db/schema.sql (resolved relative to the package).
ENV PATH="/app/.venv/bin:$PATH"
ENV FINALLY_DB_PATH=/data/finally.db
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
