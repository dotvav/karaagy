# Installation & Deployment Guide 🚀

Karaagy can be deployed in two distinct modes depending on your workflow:

1. [**Track 1: Production Deployment (Docker Compose - Recommended)**](#-track-1-production-deployment-docker-compose): Runs Karaagy in an isolated container backed by a dedicated host system user (`karaagy`, UID `8888`) with persistent OAuth tokens.
2. [**Track 2: Local Development Setup (Native Python)**](#-track-2-local-development-setup-native-python): Runs Karaagy directly on your host machine for development and testing using your existing user's `agy` CLI authentication.

---

## 🐳 Track 1: Production Deployment (Docker Compose)

### Step 1: Set Up the Isolated Host User & OAuth Credentials

To prevent configuration drift, history pollution, and rule leakage between your personal Antigravity IDE/CLI workspace and the background gateway daemon, Karaagy runs under a dedicated system user (`karaagy`) with UID `8888`.

1. **Create the dedicated system user**:
   ```bash
   sudo useradd -m -u 8888 -s /bin/bash karaagy
   ```

2. **Install `agy` CLI for the `karaagy` user and complete one-time browser authentication**:
   ```bash
   sudo -u karaagy -i
   curl -fsSL https://antigravity.google/cli/install.sh | bash
   # Launch agy to trigger the OAuth browser authentication flow
   agy
   # Once authenticated, exit the subshell
   exit
   ```
   *OAuth tokens are saved in `/home/karaagy/.gemini` with `0700` permissions.*

3. **Ensure proper directory ownership**:
   ```bash
   sudo chown -R 8888:8888 /home/karaagy/.gemini
   ```

### Step 2: Deploy with Docker Compose

Create a `docker-compose.yml` file:

```yaml
services:
  karaagy:
    image: ghcr.io/dotvav/karaagy:latest
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
      - KARAAGY_MAX_CONCURRENT_SESSIONS=4
    volumes:
      - /home/karaagy/.gemini:/home/karaagy/.gemini:rw
    labels:
      - "com.docker.compose.project=karaagy"
```

Start the container:
```bash
docker compose up -d
```

### Step 3: Verify Container Health
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/v1/models
```

---

## 💻 Track 2: Local Development Setup (Native Python)

If you are developing, testing, or contributing to Karaagy directly on your host machine without Docker:

### Prerequisites
- Python >= 3.12
- [`uv`](https://github.com/astral-sh/uv)
- Antigravity CLI (`agy`) installed and authenticated under your current user account.

### Clone & Run
```bash
# 1. Clone the repository
git clone https://github.com/dotvav/karaagy.git
cd karaagy

# 2. Install dependencies into isolated virtualenv
uv sync

# 3. Start the development server with hot-reload
uv run uvicorn karaagy.main:app --reload --port 8000
```
Open `http://localhost:8000/` in your browser to view the interactive Web Status Dashboard.

---

## 🔌 Connecting AI Clients to Karaagy

### Open WebUI
1. Open **Settings** $\to$ **Admin Settings** $\to$ **Connections**.
2. Under **OpenAI API**, add a new connection:
   - **Base URL**: `http://<host-ip>:8000/v1`
   - **API Key**: `none` (or any dummy string)
3. Click **Verify Connection** and select your desired model (`gemini-3.8-flash-high`, `gpt-4o`).

### Continue.dev (`config.json`)
> [!NOTE]
> Set `"tools": false` to prevent client-side tool loops from conflicting with the underlying `agy` agent.

```json
{
  "models": [
    {
      "title": "Karaagy Flash High",
      "provider": "openai",
      "model": "gemini-3.8-flash-high",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "none",
      "capabilities": {
        "tools": false
      }
    }
  ]
}
```

### Official OpenAI Python SDK
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

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

## ✅ Deployment Verification Checklist

- [ ] **Host User & Permissions (Docker)**: Verified `/home/karaagy/.gemini` exists and is owned by `8888:8888`.
- [ ] **OAuth Token Persistence**: Verified `agy` executes inside `/home/karaagy` without triggering interactive re-authentication.
- [ ] **Liveness & Readiness**: `curl http://localhost:8000/healthz` returns `{"status":"ok","service":"karaagy"}`.
- [ ] **Models Catalog**: `curl http://localhost:8000/v1/models` returns the dynamic model list with aliases.
- [ ] **Streaming SSE Output**: `curl -N -X POST http://localhost:8000/v1/chat/completions ...` returns token delta events ending with `data: [DONE]`.
