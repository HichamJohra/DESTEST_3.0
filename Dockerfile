# DESTEST web app - container image (Google Cloud Run or any Docker host)
#   docker build -t destest-web .
#   docker run -p 8080:8080 destest-web        ->  http://localhost:8080
FROM python:3.13-slim

# uv, pinned to the version of the lock file
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1. Dependencies only (cached as long as pyproject.toml and uv.lock do not change):
#    the package's own dependencies + the "web" group, no development tools.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --group web --no-install-project

# 2. The package and the results shown by the app
COPY src ./src
COPY ["Result data", "/app/Result data"]
RUN uv sync --locked --no-dev --group web

ENV PATH="/app/.venv/bin:$PATH" \
    DESTEST_RESULTS="/app/Result data"

# Cloud Run provides $PORT (8080 by default).
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 120 "destest.webapp.app:server"
