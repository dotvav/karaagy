# Technical Learnings & Gotchas

This document records critical gotchas, library constraints, and configurations resolved during development.

---

## 🛠️ 1. Mypy Performance Optimization for Heavy Libraries
- **Issue**: Strict Mypy parses all transitive imports of heavy third-party packages, slowing checks down by 20+ seconds.
- **Solution**: Set `follow_imports = "skip"` in `pyproject.toml` for heavy modules, paired with `warn_unused_ignores = false`.
