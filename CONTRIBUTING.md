# Contributing

Contributions are welcome. Please follow these guidelines:

## Development Setup

```bash
uv sync --group dev

# CI-style quality checks only
uv sync --locked --only-group lint --no-install-project
```

## Running Tests

```bash
uv run pytest
```

## Code Quality

```bash
uv run ruff check src/ tests/ debug/
uv run pyright src/ tests/ debug/ main.py
uv run deptry src/
uv run tach check
```

`deptry` validates that declared distributions match the imports under `src/`.
`tach` enforces the package boundaries declared in `tach.toml`.
GitHub Actions runs `ruff`, `pyright`, `deptry`, and `tach` on pushes to `main` and on pull requests.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

- `fix:` for bug fixes
- `feat:` for new features
- `docs:` for documentation changes
- `refactor:` for code restructuring
