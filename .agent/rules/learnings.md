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
