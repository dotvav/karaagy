# Workspace Development Guidelines

## Python Environment & Tooling
- Always use `uv` for python dependencies and execution (`uv run pytest`, `uv run ruff check`, `uv run mypy .`).
- Enforce strict typing with `mypy .` (`strict = true`).
- Format and lint code with `ruff`.

## Strict Test-Driven Development (TDD)
- Write unit tests first before writing production code.
- Implement minimum code required to make tests pass.
- Verify static analysis and test coverage.

## Verification
- Before completing tasks, always run `uv run ruff check && uv run mypy . && uv run pytest`.
