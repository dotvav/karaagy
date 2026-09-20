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
