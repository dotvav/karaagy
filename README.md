# Karaagy 🚀

> High-performance, lightweight OpenAI-compatible REST and SSE API gateway wrapping the Google Antigravity CLI (`agy`).

Karaagy provides drop-in compatibility for standard OpenAI SDKs (Python, TypeScript), AI IDEs (Continue.dev, Cursor), and web UIs (Open WebUI, LibreChat) to communicate with Antigravity models.

---

## 🌟 Key Features

- **OpenAI Standard Endpoints**: Supports `GET /v1/models` and `POST /v1/chat/completions`.
- **Real-Time Streaming**: Full Server-Sent Events (SSE) streaming (`stream: true`) with token deltas.
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
