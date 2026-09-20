# Developer Guide

## Architecture Overview
- **Framework**: FastAPI (async HTTP framework)
- **Settings**: Pydantic Settings
- **Package Manager**: `uv`
- **Quality Assurance**: `ruff check`, `mypy .` (strict mode), `pytest`

## Development Workflow
1. **Branching Strategy**: Standard feature branches (`feature/xxx`, `fix/yyy`) off `dev`.
2. **Pre-Commit Verification**: Always ensure static checks and tests pass before committing:
   ```bash
   uv run ruff check && uv run mypy . && uv run pytest
   ```
