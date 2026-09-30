<p align="center">
  <img src="assets/karaagy-logo.svg" alt="Karaagy Logo" width="180" />
</p>

# Karaagy 🚀

<p align="center">
  <a href="https://github.com/roukine/karaagy/actions/workflows/ci.yml"><img src="https://github.com/roukine/karaagy/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
  <a href="https://github.com/roukine/karaagy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg" alt="Python 3.12 | 3.13" />
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" /></a>
  <img src="https://img.shields.io/badge/type%20checking-mypy%20strict-blue" alt="Mypy Strict" />
  <img src="https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker" alt="Docker GHCR" />
</p>

> High-performance, lightweight OpenAI-compatible REST and SSE API gateway wrapping the Google Antigravity CLI (`agy`).

Karaagy provides drop-in compatibility for standard OpenAI SDKs (Python, TypeScript), AI IDEs (Continue.dev, Cursor), and web UIs (Open WebUI, LibreChat) to communicate with Antigravity models.


---

## 🌟 Key Features

- **OpenAI Standard Endpoints**: Supports `GET /v1/models` and `POST /v1/chat/completions`.
- **Real-Time Streaming**: Full Server-Sent Events (SSE) streaming (`stream: true`) with token deltas.
- **Interactive Web Status Dashboard**: Self-contained, responsive dashboard on `GET /` with live `/usage` quota tracking, concurrency metrics, sanitized environment inspector, and model alias mappings.
- **Dynamic Model Discovery & Alias Routing**: Discovers available models from `agy models` with transparent mapping for common aliases (`gpt-4o`, `gpt-3.5-turbo`, `claude-3-5-sonnet`, `gemini-flash`).
- **Storage Hygiene**: Automatically prunes ephemeral CLI transcripts and conversation state on completion.
- **Resilience**: Built-in exponential backoff retries for transient OAuth/network glitches.

---

## 🚀 Quickstart

### Prerequisites
- Python >= 3.12
- [`uv`](https://github.com/astral-sh/uv)
- Authenticated Antigravity CLI (`agy`)

### 1. Install & Sync
```bash
uv sync
```

### 2. Run Locally
```bash
uv run uvicorn karaagy.main:app --reload --port 8000
```

---

## 💻 Usage Examples

### Listing Models (`GET /v1/models`)
```bash
curl http://localhost:8000/v1/models
```

### Chat Completion — Non-Streaming (`POST /v1/chat/completions`)
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a concise assistant."},
      {"role": "user", "content": "Explain quantum computing in one sentence."}
    ]
  }'
```

### Chat Completion — Streaming (`stream: true`)
```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.8-flash-high",
    "messages": [
      {"role": "user", "content": "Count from 1 to 5."}
    ],
    "stream": true
  }'
```

### Using Official OpenAI Python SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none",  # Auth not required
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Hello Antigravity!"},
    ],
    stream=True,
)

for chunk in response:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
print()
```

---
 
## 🖥️ Interactive Web Status Dashboard

Access `http://localhost:8000/` in any browser to view the diagnostic dashboard:
- ⚡ **Antigravity Quota Tracking (`/usage`)**: Visual progress bars showing remaining requests and reset times per model tier with on-demand cache refresh.
- 📊 **Gateway Metrics**: Live concurrency, request count, and throughput.
- 🤖 **Model Catalog & Aliases**: Active models and OpenAI compatibility aliases.
- ⚙️ **Sanitized Environment**: Secure inspector with sensitive tokens automatically masked.

---

## 📚 Documentation

- [User Guide](docs/user_guide.md) — Comprehensive client integration (Python, TypeScript, Open WebUI, LibreChat, Continue.dev, Cursor, Vision/Multimodal), model aliases, and configuration reference.
- [Installation & Deployment Guide](docs/installation_guide.md) — Host user isolation (UID 8888), OAuth persistence, and Docker/Portainer production deployment.
- [Developer Guide](docs/developer_guide.md) — Architecture, testing, and contribution guidelines.

---

## 🧪 Verification & Static Checks

```bash
# Code Formatting & Linting
uv run ruff check
uv run ruff format --check

# Strict Type Checking
uv run mypy .

# Test Suite
uv run pytest
```

---

## 🐳 Docker Deployment

```bash
docker compose up -d
```

