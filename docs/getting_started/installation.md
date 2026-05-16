# Installation

## Prerequisites

- Python 3.12 (pinned in `.python-version`)
- [uv](https://github.com/astral-sh/uv) ≥ 0.4

## Install

```bash
uv sync
```

This installs all runtime and development dependencies from `uv.lock`.

## Environment variables

All settings can be overridden via environment variables or a `.env` file at
the repository root. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `DIRECTORY_INPUT` | `data/input` | Source JSON invoice files |
| `DIRECTORY_OUTPUT` | `data/output` | Processed CSV output |
| `DIRECTORY_MODELS` | `models` | Trained model artefacts |
| `DIRECTORY_LOGS` | `logs` | JSONL event logs |
| `APP_VERSION` | `0.1` | Package version stamped in log events |
| `APP_BASE_URL` | `http://127.0.0.1/` | Base URL for internal API references |

## Caveats

- The `data/input` directory must be populated with invoice JSON files before
  running ingestion.
- Model artefacts are stored as pickle files; the `models/` directory is created
  automatically on first training run.
