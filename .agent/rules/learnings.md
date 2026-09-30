# Technical Learnings & Gotchas

This document records critical gotchas, library constraints, and configurations resolved during development.

---

## 🛠️ 1. Mypy Performance Optimization for Heavy Libraries
- **Issue**: Strict Mypy parses all transitive imports of heavy third-party packages, slowing checks down by 20+ seconds.
- **Solution**: Set `follow_imports = "skip"` in `pyproject.toml` for heavy modules, paired with `warn_unused_ignores = false`.

---

## 🛠️ 2. Antigravity CLI NDJSON Streaming & Ephemeral Session Storage Pruning
- **Last Updated**: 2026-09-20T12:46:45Z
- **The Issue**: Exposing `agy` as an OpenAI gateway via `--output-format stream-json` or `--output-format json` creates a distinct conversation directory under `~/.gemini/antigravity-cli/brain/<conversation-id>/` and a JSON file under `~/.gemini/antigravity-cli/conversations/<conversation-id>.json` on every single stateless request, accumulating disk clutter over time.
- **The Gotcha**: `agy` does not auto-purge or clean ephemeral one-off prompt sessions.
- **Code / Solution**: In the subprocess runner, parse the returned `conversation_id` from the result payload and remove the ephemeral `brain/<conversation_id>` directory and `conversations/<conversation_id>.json` file after the request completes:
```python
def prune_conversation_storage(conversation_id: str | None) -> None:
    if not conversation_id or not settings.enable_auto_prune_sessions:
        return
    base_dir = settings.antigravity_home
    brain_dir = base_dir / "brain" / conversation_id
    convo_file = base_dir / "conversations" / f"{conversation_id}.json"
    shutil.rmtree(brain_dir, ignore_errors=True)
    convo_file.unlink(missing_ok=True)
```

---

## 🛠️ 3. Antigravity CLI Model Suffix & `--effort` Flag Conflict
- **Last Updated**: 2026-09-20T13:04:50Z
- **The Issue**: When invoking `agy --model gemini-3.8-flash-high --effort medium`, the CLI exits with code 1: `error: invalid model selection: --model gemini-3.8-flash-high conflicts with --effort=medium`.
- **The Gotcha**: Antigravity models returned by `agy models` (such as `gemini-3.8-flash-high`, `gemini-3.7-flash-low`, `gemini-3.1-pro-high`) already have reasoning effort baked into their model name suffix (`-low`, `-medium`, `-high`). Passing the `--effort` CLI parameter alongside these explicit models triggers an invalid flag collision in the CLI.
- **Code / Solution**: Do not pass `--effort` by default; only supply `--effort` if explicitly requested by the caller AND the target model name does not already end with an effort suffix (`-low`, `-medium`, `-high`, `-thinking`).

---

## 🛠️ 4. OpenAI Multimodal Structured Message Parts Support
- **Last Updated**: 2026-09-20T13:16:00Z
- **The Issue**: Clients sending multimodal vision requests (e.g. LiteLLM, Vibrisse) send `messages[i].content` as a list of structured dictionaries (`[{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}]`) instead of a single string. Pydantic models typed as `content: str` fail validation with HTTP `422 (Input should be a valid string)`.
- **The Gotcha**: OpenAI standard schemas allow `content` to be either `str`, `list[dict[str, Any]]`, or `None`.
- **Code / Solution**: Type `ChatCompletionMessage.content` as `str | list[dict[str, Any]] | None = ""` and implement an unrolling helper `extract_message_text()` that concatenates text parts and converts image URL objects into structured inline references `[Attached Image URL: <url>]`.

---

## 🛠️ 5. Subprocess Prompt Piping via `stdin` to Prevent Linux `ARG_MAX` Limit
- **Last Updated**: 2026-09-21T07:04:00Z
- **The Issue**: When clients pass large payloads (large marketplace item catalogs, lengthy instructions, base64 data), passing `--prompt "<text>"` on the command-line arguments exceeds the Linux kernel `MAX_ARG_STRLEN` (128 KB per argument), crashing with `OSError: [Errno 7] Argument list too long`.
- **The Gotcha**: Subprocess command argument arrays in POSIX systems have strict size bounds per argument.
- **Code / Solution**: Do not pass `--prompt` in CLI `args`. Instead, omit `--prompt` and stream the prompt bytes directly via standard input `stdin=asyncio.subprocess.PIPE` using `proc.communicate(input=prompt.encode("utf-8"))` for JSON mode, or `proc.stdin.write(prompt.encode("utf-8"))` for streaming mode.

---

## 🛠️ 6. Antigravity CLI Transient Subscriber Lag Handling and Base64 Media Offloading
- **Last Updated**: 2026-09-21T07:37:30Z
- **The Issue**: When concurrent requests or large multimodal payloads hit the gateway, the Antigravity CLI subprocess occasionally fails with `the connection to the agent was interrupted before the response finished: subscriber fell behind updates, stalled for 5s` or returns an empty response payload (`{"status": "ERROR", "response": ""}`). Without specific pattern matching and retry loops on error payloads/empty responses, the gateway returns HTTP 500 or empty content, causing client fallback errors.
- **The Gotcha**: If base64 data URIs are piped directly as plaintext in stdin, the massive text strings can trigger buffer delays. Furthermore, `subscriber fell behind updates` and status `ERROR` payloads must be classified as retryable.
- **Code / Solution**:
  1. Add `subscriber fell behind`, `stalled for`, `interrupted`, and `channel closed` to `RETRYABLE_AGY_ERROR_PATTERNS`.
  2. In `execute_agy_json`, trigger exponential backoff retries if `parsed.status == "ERROR"`, `parsed.error` is present, or `clean_text` is empty.
  3. Extract base64 image data URIs to temporary image files (`[Attached Image File: /tmp/karaagy_images/img_xxx.jpg]`) rather than sending megabytes of raw base64 string text over stdin.

---

## 🛠️ 7. Process Concurrency Semaphore Guard
- **Last Updated**: 2026-09-21T07:45:00Z
- **The Issue**: Unbounded concurrent requests trigger numerous concurrent `agy` subprocesses, causing high memory usage, token lock contention, and gRPC subscriber drops.
- **The Gotcha**: Completely serializing executions (limit = 1) slows down multi-item batch screening in downstream clients.
- **Code / Solution**: Use an asynchronous semaphore `asyncio.Semaphore(settings.max_concurrent_sessions)` (defaulting to 4, configurable via `KARAAGY_MAX_CONCURRENT_SESSIONS` or `0` for unbounded) around `execute_agy_json` and `execute_agy_stream`. Excess requests queue in memory at FastAPI level and execute smoothly as slots free up.

---

## 🛠️ 8. Dynamic Status Page with Antigravity `/usage` Quota Caching & Content Negotiation
- **Last Updated**: 2026-09-24T15:37:30Z
- **The Issue**: Serving an interactive status page on `GET /` that calls `agy -p "/usage"` on every request adds 3-4s latency per page view. Furthermore, automated API clients require JSON output while browsers require HTML.
- **The Gotcha**: `agy -p "/usage" --output-format json` queries Google's backend and must not be run synchronously on every HTTP request. Content negotiation should check for `text/html` explicitly in `Accept` headers so curl and testing tools receive clean JSON while browsers receive the dashboard.
- **Code / Solution**: Cache `/usage` quota data via `DiagnosticsManager` with a 10-minute TTL and warm it up during FastAPI startup lifespan. Return a self-contained, air-gap-safe HTML dashboard when `text/html` is in `Accept` headers, and structured JSON otherwise. Mask sensitive environment variables containing `TOKEN`, `KEY`, `SECRET`, `AUTH`, and `PASS`.

---

## 🛠️ 9. Gitea Issue Asset Attachment API & Pure Vector Transparent SVGs
- **Last Updated**: 2026-09-30T07:08:20Z
- **The Issue**: Uploading vector design assets directly to Gitea issues programmatically requires finding the correct API endpoint and ensuring inline rendering in markdown comments, while SVGs designed for both light and dark mode web UI must avoid hardcoded background rectangles.
- **The Gotcha**: Hardcoded `<rect width="100%" height="100%" fill="#..."/>` prevents SVGs from blending into transparent web headers and dark/light themes. Additionally, Gitea issue asset attachments are managed via `POST /api/v1/repos/{owner}/{repo}/issues/{id}/assets` using `multipart/form-data; name=attachment` with the standard API token header.
- **Code / Solution**:
  1. For vector SVG assets, define a tight `viewBox` (e.g. `0 0 512 512`) without any root `<rect>` canvas, using dual neon accents (`#06b6d4` cyan, `#a855f7` violet) and warm golden amber tones (`#f59e0b`, `#fbbf24`, `#d97706`) with dark amber outlines (`#78350f`) so all elements maintain high contrast against pure white (`#ffffff`) and dark slate (`#0d1117`) backgrounds.
  2. Upload assets via Gitea API:
  ```bash
  curl -s -X POST "https://gitea.example.com/api/v1/repos/owner/repo/issues/1/assets" \
    -H "Authorization: token <token>" \
    -H "Accept: application/json" \
    -F "attachment=@assets/logo.svg;type=image/svg+xml"
  ```

---

## 🛠️ 10. Raster-to-Vector Pipeline: `rembg` Model Sizing & `vtracer` Spline Fitting
- **Last Updated**: 2026-09-30T07:16:30Z
- **The Issue**: Converting AI-generated concept art (diffusion bitmaps) into vector SVGs cannot be done by LLM text generation alone. Using `rembg` out-of-the-box defaults to `bria-rmbg-2.0` (1.02 GB model) which causes OOM process kills (exit code 137) on standard dev runners.
- **The Gotcha**: `rembg.new_session("u2netp")` loads a lightweight 4.5 MB U2-Net model that executes in <2s with negligible RAM footprint, isolating the subject cleanly. Then `vtracer` with `colormode="color"`, `hierarchical="stacked"`, `filter_speckle=6`, and `color_precision=6` produces crisp, scalable Bézier multi-layer vector paths.
- **Code / Solution**:
```python
from rembg import new_session, remove
import vtracer

session = new_session("u2netp")
nobg_bytes = remove(input_bytes, session=session)
vtracer.convert_image_to_svg_py(
    image_path=str(nobg_path),
    out_path=str(svg_path),
    colormode="color",
    hierarchical="stacked",
    filter_speckle=6,
    color_precision=6,
    layer_difference=16,
)
```


