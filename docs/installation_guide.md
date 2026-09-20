# Installation & Deployment Guide

This guide details the setup and deployment architecture for **Karaagy**, covering local installation, dedicated host user isolation (UID 8888), Google Antigravity OAuth persistence, and production Docker/Portainer deployment.

---

## 1. Google Antigravity Authentication & Dedicated Host User Isolation

### Rationale
To prevent configuration drift, history pollution, and rule leakage between your personal Antigravity IDE/CLI environment and the autonomous API wrapper, Karaagy uses a dedicated host system user (`karaagy`) with UID `8888`.

### Host User Setup & OAuth Initial Login
1. **Create the dedicated system user**:
   ```bash
   sudo useradd -m -u 8888 -s /bin/bash karaagy
   ```

2. **Install `agy` CLI for the `karaagy` user and complete one-time authentication**:
   ```bash
   sudo -u karaagy -i
   curl -fsSL https://antigravity.google/cli/install.sh | bash
   # Launch agy to trigger the OAuth browser authentication flow
   agy
   # Once authenticated, exit the subshell
   exit
   ```
   *OAuth tokens are persisted securely in `/home/karaagy/.gemini` with `0700` permissions.*

3. **Set host directory permissions**:
   ```bash
   sudo chown -R 8888:8888 /home/karaagy/.gemini
   ```

---

## 2. Local Development Installation

If you prefer running Karaagy directly on the host for development:

### 1. Prerequisites
- Python >= 3.12
- [`uv`](https://github.com/astral-sh/uv)
- Antigravity CLI (`agy`) installed and authenticated

### 2. Install & Run
```bash
# Clone the repository
git clone git@gitea.ruk.info:roukine/karaagy.git
cd karaagy

# Install dependencies into virtualenv
uv sync

# Run the API server with auto-reload
uv run uvicorn karaagy.main:app --reload --port 8000
```

---

## 3. Production Container Deployment (Docker & Portainer)

### `docker-compose.yml` Specification

```yaml
version: "3.8"

services:
  karaagy:
    image: gitea.ruk.info/roukine/karaagy:latest
    container_name: karaagy-api
    user: "8888:8888"
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - HOME=/home/karaagy
      - KARAAGY_HOST=0.0.0.0
      - KARAAGY_PORT=8000
      - KARAAGY_DEFAULT_MODEL=gemini-3.8-flash-high
      - KARAAGY_DEFAULT_EFFORT=medium
      - KARAAGY_ENABLE_AUTO_PRUNE_SESSIONS=true
    volumes:
      - /home/karaagy/.gemini:/home/karaagy/.gemini:rw
    labels:
      - "com.docker.compose.project=karaagy"
      - "com.centurylinklabs.watchtower.enable=true"
      - "com.centurylinklabs.watchtower.scope=standard"
```

### Launching the Container
```bash
docker compose up -d
```

---

## 4. Connecting OpenAI Clients to Karaagy

### Open WebUI Configuration
1. Open **Settings** $\to$ **Admin Settings** $\to$ **Connections**.
2. Under **OpenAI API**, add a new connection:
   - **Base URL**: `http://<host-ip>:8000/v1`
   - **API Key**: `none` (or any dummy string)
3. Click **Verify Connection** and select your model (e.g., `gemini-3.8-flash-high`, `gpt-4o`).

### Continue.dev (`config.json`)
```json
{
  "models": [
    {
      "title": "Karaagy Gemini Flash",
      "provider": "openai",
      "model": "gemini-3.8-flash-high",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "none"
    }
  ]
}
```

### LiteLLM / Custom Python SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain async I/O in 1 sentence."}],
    stream=True,
)

for chunk in response:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
print()
```

---

## 5. Deployment Verification Checklist

- [ ] **Host User & Permissions**: Verified `/home/karaagy/.gemini` exists and is owned by `8888:8888`.
- [ ] **OAuth Token Persistence**: Verified `agy` inside `/home/karaagy` executes without triggering interactive re-authentication.
- [ ] **Liveness & Readiness**: `curl http://localhost:8000/healthz` returns `{"status":"ok","service":"karaagy"}`.
- [ ] **Models Endpoint**: `curl http://localhost:8000/v1/models` returns model list with `gemini-3.8-flash-high` and aliases.
- [ ] **Streaming Completion**: `curl -N -X POST http://localhost:8000/v1/chat/completions ...` returns token SSE events with `data: [DONE]`.
