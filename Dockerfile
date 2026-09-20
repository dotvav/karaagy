# Multi-stage Dockerfile for Karaagy OpenAI Gateway
FROM python:3.12-slim AS runner

# Install runtime dependencies (curl, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy static uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install python dependencies into virtualenv
RUN uv sync --frozen --no-dev

# Create non-root karaagy user (UID 8888)
RUN useradd -m -u 8888 karaagy && \
    mkdir -p /home/karaagy/.gemini /app && \
    chown -R karaagy:karaagy /app /home/karaagy

# Install agy CLI into container for karaagy user
USER karaagy
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash

ENV PATH="/app/.venv/bin:/home/karaagy/.local/bin:$PATH"
ENV PYTHONPATH="/app/src"

USER root
# Copy application source code
COPY --chown=karaagy:karaagy src/ ./src/
COPY --chown=karaagy:karaagy README.md ./

USER karaagy

EXPOSE 8000
CMD ["uvicorn", "karaagy.main:app", "--host", "0.0.0.0", "--port", "8000"]
