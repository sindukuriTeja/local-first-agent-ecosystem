# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Local-First Agent Ecosystem — multi-portal web app
#
# Stage 1: build the React/Vite frontend -> frontend/dist
# Stage 2: Python backend (FastAPI/uvicorn) that serves the API + the SPA
#
# The backend talks to a sibling `ollama` service (see docker-compose.yml).
# Point it at the right host with LFAE_OLLAMA_URL (set in compose).
# ---------------------------------------------------------------------------

# ---------- Stage 1: frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /build
# Install deps first (better layer caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend ----------
FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend package + config
COPY agent_platform/ ./agent_platform/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Built frontend (served by FastAPI from frontend/dist)
COPY --from=frontend /build/dist ./frontend/dist

# Runtime data (knowledge store, documents, audit log, memory) — volume this
RUN mkdir -p /app/data

EXPOSE 8000

# Healthcheck hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "agent_platform.server"]