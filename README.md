# Modern Python Project Template

> Production-ready Python project boilerplate featuring FastAPI, `uv`, Ruff, Mypy, Pytest, Docker, and Gitea Actions CI/CD.

---

## 🚀 Quickstart

### Prerequisites
- Python >= 3.12
- [`uv`](https://github.com/astral-sh/uv) (Fast Python package installer)

### Setup & Installation
```bash
# Clone your repository created from this template
git clone git@gitea.ruk.info:roukine/<repo-name>.git
cd <repo-name>

# Install dependencies and setup virtualenv
uv sync
```

### Running Locally
```bash
uv run uvicorn src.my_project.main:app --reload --port 8000
```

---

## 🧪 Development & Verification

```bash
# Code Formatting & Linting
uv run ruff check
uv run ruff format

# Type Checking
uv run mypy .

# Test Suite
uv run pytest
```

---

## 🐳 Docker Deployment

```bash
# Build container image
docker build -t my-project:latest .

# Run container
docker run -p 8000:8000 my-project:latest
```
