# AI Enterprise Workflow

Invoice-revenue forecasting service built on ARIMA/SARIMA time-series models,
exposed via a Flask REST API.

## Installation

```bash
uv sync
```

See [Getting Started](docs/getting_started/installation.md) for prerequisites
and environment-variable reference.

## CLI

Four subcommands are available via the `ai_enterprise_workflow` entrypoint:

```bash
# Load and clean invoice JSON files from data/input/
uv run ai_enterprise_workflow ingest

# Train ARIMA/SARIMA models for a reference date
uv run ai_enterprise_workflow train --date 2019-01-01

# Generate a revenue forecast
uv run ai_enterprise_workflow predict --date 2019-01-01 --duration 30

# Start the development server (default: port 5000)
uv run ai_enterprise_workflow serve
```

## API

Predict revenue for the next 30 days:

```bash
curl -X POST 'http://localhost:5000/predict?date=2019-01-01'
```

Expected response:

```json
{"data": {"arima": 12345.6, "sarima": 12300.0, "drift": 0.03}, "drift_warning": false}
```

Add `country` to filter by market, `duration` to set the horizon:

```bash
curl -X POST 'http://localhost:5000/predict?date=2019-01-01&duration=14&country=United+Kingdom'
```

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/predict` | POST | ARIMA/SARIMA forecast; params: `date` (required), `duration` (default 30), `country` |
| `/logs` | POST | Query event logs; param: `type` — one of `ingest`, `train`, `predict` |
| `/healthz` | GET | Liveness probe — `{"status": "ok"}` |
| `/readyz` | GET | Readiness probe — 503 until ingestion artefact is present |

## Tests

```bash
uv run pytest tests/
```

## Docker

```bash
docker build -t app .

docker run \
    -it \
    --rm \
    -p 3000:80 \
    --name app \
    app
```

The server is available at `http://localhost:3000` when running via Docker.

## References

[IBM AI Enterprise Workflow Specialization](https://www.coursera.org/specializations/ibm-ai-workflow)
