# Karaagy User Guide 📖

This guide is intended for developers, AI engineers, and system operators who consume or manage the **Karaagy** OpenAI-compatible API gateway.

---

## 🎯 Target Audience & Use Cases

* **Application Developers**: Integrating LLMs into apps using the official OpenAI SDK (Python, TypeScript/JavaScript, Go, Rust) or orchestration frameworks (LangChain, LlamaIndex, Semantic Kernel).
* **Self-Hosted & Automation Services**: Powering dedicated applications that integrate standard OpenAI endpoints for backend processing (e.g. **Mealie** for recipe ingestion/ingredient parsing, content classifiers, web scrapers, data tagging, and automated text evaluation).
* **AI Tool & IDE Users**: Powering developer tools like **Continue.dev**, **Cursor**, **Aider**, or **Cline** with Google Antigravity models.
* **Self-Hosted AI UI Operators**: Connecting chat interfaces like **Open WebUI**, **LibreChat**, or **Dify** to local/hosted Antigravity backends.
* **Operators & Sysadmins**: Monitoring quota usage, rate limits, active gateway throughput, and service status via the built-in Web Dashboard.

---

## ⚠️ Important Architectural Caveat: Underlying Agentic Layer vs Raw LLM

> [!WARNING]
> **Karaagy exposes an autonomous AI coding assistant (`agy`), NOT a raw token-inference API.**

Unlike direct LLM APIs (e.g. standard OpenAI, Anthropic, or Vertex AI endpoints) that simply predict tokens based on prompt probability distributions, the underlying Google Antigravity CLI is an **interactive agent system** with built-in system prompts, toolsets, and coding behaviors.

### 🔍 Failure Modes & Tool Collisions:

1. **Remote Execution Hijacking (Gateway Host vs Local Client)**:
   - When an IDE or agent harness requests a tool execution (e.g. `read_file`, `run_command`, `git_status`), `agy` executes that command on the **gateway host/container environment** (with `--dangerously-skip-permissions`), not inside the user's local IDE workspace or repository.
   - If the IDE client and `agy` share tool names, `agy` intercepts and executes on the server side, returning plaintext outputs instead of standard OpenAI `delta.tool_calls` JSON payloads, breaking the IDE's client-side tool loop.
2. **Nested Autonomous Agent Collisions (OpenClaw, SWE-agent, AutoGPT, Cline Act Mode)**:
   - Nested agent architectures create infinite reflection loops, duplicate tool executions, or unexpected file mutations on the host server.
3. **Meta-Prompt Bias & Hyperparameter Abstraction**:
   - Responses reflect built-in Antigravity developer system instructions that cannot be completely stripped by client prompts.
   - Sampling controls (`temperature`, `top_p`, `seed`, `logprobs`) are managed internally by the Antigravity backend.

---

### 📊 Recommended vs Incompatible Use Cases:

| Mode / Environment | Compatibility | Recommendation & Configuration |
| :--- | :---: | :--- |
| **Self-Hosted Services & Automation (Mealie, bots, classifiers)** | ✅ **Ideal** | Recipe parsing, text classification, summarization, entity extraction, and content judging without tool loops. |
| **Chat UIs (Open WebUI, LibreChat, Dify)** | ✅ **Ideal** | Standard chat completion, multi-turn Q&A, and system prompts work out-of-the-box. |
| **IDE Chat & Explanation (Continue, Cursor `Cmd+L`, Aider `/ask`)** | ✅ **Ideal** | Asking questions, reviewing code, writing docstrings, and explaining algorithms. |
| **IDE Code Editing / Prompt Refactor (Continue `/edit`)** | ⚠️ **Qualified** | Safe when client-side tool calling is disabled (`capabilities: { tools: false }`). |
| **IDE Autonomous Agents (Cursor Composer Agent, Cline Act Mode)** | ❌ **Incompatible** | Tool namespace collision and remote host execution hijacking risk. |
| **Autonomous Agent Harnesses (OpenClaw, SWE-bench, AutoGPT)** | ❌ **Incompatible** | High risk of tool loop recursion and protocol failure. |
| **Raw Base Model Evaluation / Token Benchmarks** | ❌ **Incompatible** | Cannot bypass Antigravity system meta-prompt. |

---

### 🛠️ Safe IDE Client Configuration

#### Continue.dev (`config.json`)
Explicitly disable client tool invocation to ensure pure text/diff streaming without tool collisions:

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

#### Aider CLI
Launch Aider in `ask` mode so it performs prompt-based discussion without auto-committing or attempting host tool calls:

```bash
aider --openai-api-base http://localhost:8000/v1 --openai-api-key none --model openai/gemini-3.8-flash-high --chat-mode ask
```


---

## 🖥️ Interactive Web Status Dashboard

When accessed via a web browser (`Accept: text/html`), the root endpoint `GET /` serves a responsive, self-contained status dashboard (with light/dark theme support and zero external CDN dependencies):

```
http://localhost:8000/
```

### Dashboard Features:
1. **⚡ Antigravity Quota & Rate Limits (`/usage`)**:
   - Live visual progress bars showing remaining request quotas and reset windows per model tier (e.g. Flash, Pro).
   - Background caching (10-minute TTL) to keep dashboard views instantaneous, with a **🔄 Refresh Quota** button for forced updates.
2. **📊 Gateway Metrics & Throughput**:
   - Active concurrent sessions vs. configured semaphore concurrency limits.
   - Total requests processed, successful completions, and error counts since gateway startup.
3. **🤖 Available Models & Aliases**:
   - Dynamic list of all models discovered on the host (`agy models`).
   - Active alias mapping table (e.g., `gpt-4o` $\to$ `gemini-3.8-flash-high`).
4. **⚙️ Configuration & Sanitized Environment Inspector**:
   - Collapsible inspection panel showing runtime settings and environment variables (with automatic redaction of all sensitive tokens, secrets, and keys).
5. **📋 Ready-to-Use Code Snippets**:
   - Instant copy-paste `curl` commands preconfigured with the resolved gateway address.

> [!NOTE]
> When accessed programmatically by API clients or `curl` (without `text/html` in `Accept` headers), `GET /` returns a structured JSON health and status payload.

---

## 🤖 Model Routing & Alias System

Karaagy automatically discovers installed models from `agy models` and provides transparent aliasing so existing OpenAI-based client configurations work out-of-the-box:

| Requested Model Name / Alias | Resolved Antigravity Target | Recommended Use Case |
| :--- | :--- | :--- |
| `gemini-3.8-flash-high` | `gemini-3.8-flash-high` | Default ultra-fast high-reasoning model |
| `gemini-3.7-flash-low` | `gemini-3.7-flash-low` | Low-latency simple queries |
| `gemini-3.1-pro-high` | `gemini-3.1-pro-high` | Complex multi-step reasoning / code |
| `gpt-4o`, `gpt-4` | `gemini-3.8-flash-high` | Drop-in OpenAI flagship alias |
| `gpt-4o-mini`, `gpt-3.5-turbo` | `gemini-3.7-flash-low` | Drop-in lightweight model alias |
| `claude-3-5-sonnet` | `gemini-3.8-flash-high` | Drop-in Anthropic alias |

---

## 🔌 Client Integration Guide

### 1. Python (`openai` SDK)

#### Synchronous / Standard Completion:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none",  # Not required for local gateway
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a concise technical assistant."},
        {"role": "user", "content": "Explain vector embeddings in one sentence."},
    ],
)

print(response.choices[0].message.content)
```

#### Real-Time SSE Streaming:
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

stream = client.chat.completions.create(
    model="gemini-3.8-flash-high",
    messages=[{"role": "user", "content": "Write a Python quicksort implementation."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
print()
```

---

### 2. TypeScript / JavaScript (`openai` SDK)

```typescript
import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "none",
});

async function main() {
  const stream = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: "Hello from TypeScript!" }],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

main();
```

---

### 3. Open WebUI & LibreChat

1. Go to **Settings** $\to$ **Connections** $\to$ **OpenAI API**.
2. Set **Base URL**: `http://<karaagy-host-ip>:8000/v1`
3. Set **API Key**: `none` (or any string).
4. Click **Verify Connection** $\to$ Karaagy models will automatically populate in your model selection dropdown.

---

### 4. Continue.dev (`config.json`)

```json
{
  "models": [
    {
      "title": "Karaagy Flash High",
      "provider": "openai",
      "model": "gemini-3.8-flash-high",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "none"
    },
    {
      "title": "Karaagy Pro High",
      "provider": "openai",
      "model": "gemini-3.1-pro-high",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "none"
    }
  ]
}
```

---

### 5. Multimodal (Vision & Image Input)

Karaagy supports OpenAI standard multimodal message structures (`type: "image_url"`), handling both external image URLs and base64 data URIs:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

response = client.chat.completions.create(
    model="gemini-3.8-flash-high",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is depicted in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-cross-guard.jpg/2560px-Gfp-wisconsin-madison-the-cross-guard.jpg"
                    },
                },
            ],
        }
    ],
)

print(response.choices[0].message.content)
```

---

## ⚙️ Configuration Reference

All settings can be customized via environment variables prefixed with `KARAAGY_`:

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `KARAAGY_HOST` | Host IP address to bind to | `0.0.0.0` |
| `KARAAGY_PORT` | HTTP port for the gateway service | `8000` |
| `KARAAGY_DEFAULT_MODEL` | Fallback model if request does not specify one | `gemini-3.8-flash-high` |
| `KARAAGY_DEFAULT_EFFORT` | Reasoning effort (`low`, `medium`, `high`) | `medium` |
| `KARAAGY_MAX_CONCURRENT_SESSIONS`| Max parallel `agy` executions (semaphore guard; `0` for unlimited)| `4` |
| `KARAAGY_ENABLE_AUTO_PRUNE_SESSIONS`| Purges temporary conversation history after each call | `true` |
| `KARAAGY_PUBLIC_BASE_URL` | Explicit public URL override for status page & snippets | `None` (auto-detected) |
| `KARAAGY_DEBUG` | Enables verbose HTTP debug logging | `false` |
