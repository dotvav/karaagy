# Multi-stage Dockerfile using static uv binary
FROM python:3.12-slim AS runner
WORKDIR /app

# Copy static uv binary from official image (avoids apt-get latency)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install python dependencies into virtualenv
RUN uv sync --frozen --no-dev

# Use virtualenv directly
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code
COPY src/ ./src/

EXPOSE 8000
CMD ["uvicorn", "src.my_project.main:app", "--host", "0.0.0.0", "--port", "8000"]
