# Contributing to psqlomni

Thanks for contributing.

## Development Setup

1. Clone the repo.
2. Install dependencies:

```bash
poetry install
```

3. Activate the virtual environment:

```bash
poetry shell
```

4. (Optional) Copy example env values:

```bash
cp env.example .env
```

## Run the Project

Run from source:

```bash
poetry run python -m psqlomni
```

## Code Quality

Run lint checks:

```bash
poetry run ruff check .
```

Run tests:

```bash
poetry run pytest
```

Run tests with coverage:

```bash
poetry run pytest --cov=psqlomni --cov-report=term-missing
```

## Branch and Commit Workflow

1. Create a branch from `main` for your change.
2. Keep commits focused and descriptive.
3. Rebase or merge `main` before opening a PR if needed.

Suggested branch patterns:

- `feat/<short-description>`
- `fix/<short-description>`
- `chore/<short-description>`
- `docs/<short-description>`

## Pull Request Guidelines

Before opening a PR:

1. Run lint and tests locally.
2. Update docs when behavior or commands change.
3. Add or update tests for bug fixes and new behavior.

In your PR description, include:

- what changed
- why it changed
- how it was tested
- any follow-up work

## Reporting Issues

When filing a bug, include:

- expected behavior
- actual behavior
- reproduction steps
- environment details (OS, Python version, DB type)
