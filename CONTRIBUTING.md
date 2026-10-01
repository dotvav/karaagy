# Contributing to Karaagy 🤝

Thank you for your interest in contributing to **Karaagy**! We welcome bug reports, feature suggestions, documentation enhancements, and code contributions.

---

## 🛠️ Development Setup

Karaagy utilizes [`uv`](https://github.com/astral-sh/uv) for fast, deterministic dependency management and virtual environments.

### 1. Prerequisites
* Python >= 3.12
* [`uv`](https://github.com/astral-sh/uv)
* Google Antigravity CLI (`agy`) installed and authenticated locally

### 2. Clone & Install
```bash
git clone https://github.com/dotvav/karaagy.git
cd karaagy
uv sync
```

### 3. Run Locally
```bash
uv run uvicorn karaagy.main:app --reload --port 8000
```
Visit `http://localhost:8000/` in your browser to verify the interactive Status Dashboard.

---

## 🧪 Quality Standards & Pre-Commit Verification

Before submitting a pull request, ensure all linters, strict type checkers, and unit tests pass:

```bash
# 1. Strict Linting & Formatting
uv run ruff check
uv run ruff format --check

# 2. Strict Type Checking
uv run mypy .

# 3. Unit Test Suite
uv run pytest
```

---

## 📝 Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):
* `feat(...)`: A new feature or endpoint
* `fix(...)`: A bug fix
* `docs(...)`: Documentation updates
* `refactor(...)`: Code refactoring without behavioral change
* `test(...)`: Adding or updating test cases
* `chore(...)`: Maintenance, dependency bumps, or CI updates

---

## 🚀 Pull Request Workflow

1. Fork the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Implement your changes with accompanying unit tests in `tests/`.
3. Verify that `uv run ruff check && uv run mypy . && uv run pytest` succeeds with 0 errors.
4. Open a Pull Request on GitHub targeting `main`.
