# Workflows

## Ingestion workflow

**Entry point:** `ingest()` in `ai_enterprise_workflow.ingestion.pipeline`.

**High-level:** See [How To → Ingestion](../how_to/ingestion.md).

```mermaid
sequenceDiagram
    participant Caller
    participant ingest
    participant get_data
    participant clean_data
    participant prepare_data
    participant calc_country as calculate_revenue_country
    participant calc_total as calculate_revenue_total
    participant log_ingest

    Caller ->> ingest: ingest(force=False)
    ingest ->> ingest: check output exists
    ingest ->> get_data: cfg.KEYS, cfg.KEY_NAMES, DIRECTORY_INPUT, DIRECTORY_OUTPUT
    get_data -->> ingest: raw DataFrame
    ingest ->> clean_data: raw DataFrame, cfg.KEYS, cfg.KEY_TYPES, DIRECTORY_OUTPUT
    clean_data -->> ingest: cleaned DataFrame
    ingest ->> prepare_data: cleaned DataFrame, DIRECTORY_OUTPUT
    prepare_data -->> ingest: engineered DataFrame
    ingest ->> calc_country: engineered DataFrame, DIRECTORY_OUTPUT
    ingest ->> calc_total: engineered DataFrame, DIRECTORY_OUTPUT
    ingest ->> log_ingest: shape tuple
```

*`ingest()` orchestrates all five pipeline steps and emits a structured log
event on completion.*

---

## Forecast workflow

**Entry point:** `model()` in `ai_enterprise_workflow.forecasting.arima`.

**High-level:** See [How To → Deployment](../how_to/deployment.md) for
end-to-end service usage.

```mermaid
sequenceDiagram
    participant Caller
    participant model
    participant ingest
    participant train_ARIMA as train_ARIMA_model
    participant train_SARIMA as train_SARIMA_model
    participant predict
    participant log_predict

    Caller ->> model: model(date, duration, country)
    model ->> model: check 4 revenue_total.csv exists
    alt output absent
        model ->> ingest: ingest()
    end
    model ->> model: load revenue CSV
    alt pickle absent
        model ->> train_ARIMA: data, order, DIRECTORY_MODELS
        train_ARIMA ->> log_predict: log_train event
    end
    alt pickle absent
        model ->> train_SARIMA: data, order, seasonal_order, DIRECTORY_MODELS
        train_SARIMA ->> log_predict: log_train event
    end
    model ->> predict: arima_model, "arima", start, end, actual
    predict ->> log_predict: log_predict event
    model ->> predict: sarima_model, "sarima", start, end, actual
    predict ->> log_predict: log_predict event
    model -->> Caller: {"arima": sum, "sarima": sum}
```

*`model()` auto-triggers ingestion if outputs are absent, trains or loads
pickled models, runs both ARIMA and SARIMA predictions, and emits log events.*

---

## Flask API workflow

**Entry points:** `healthz()`, `predict()`, `logs()` in
`ai_enterprise_workflow.service.api`.

```mermaid
sequenceDiagram
    participant Client
    participant Flask
    participant model as forecasting.model
    participant _read_log_events

    Client ->> Flask: GET /healthz
    Flask -->> Client: {"status": "ok"}

    Client ->> Flask: POST /predict?date=...
    Flask ->> Flask: validate date param
    Flask ->> model: model(date, duration, country)
    model -->> Flask: {"arima": x, "sarima": y}
    Flask -->> Client: {"data": {"arima": x, "sarima": y}}

    Client ->> Flask: POST /logs?type=predict
    Flask ->> Flask: validate type param
    Flask ->> _read_log_events: DIRECTORY_LOGS, "predict"
    _read_log_events -->> Flask: list of records
    Flask -->> Client: {"data": [...]}
```

*The Flask API validates request parameters, delegates to domain functions,
and returns JSON responses.*

---

## Logging setup workflow

**Entry point:** `setup_logging()` in `ai_enterprise_workflow.core.log_events`.

Called once at process start in `run.py`:

```python
setup_logging(log_dir=cfg.directory_logs)
```

`setup_logging()` attaches:

1. A `StreamHandler` with plain-text formatter (always).
2. A `FileHandler` writing JSONL to `<log_dir>/events.jsonl` (when `log_dir`
   is provided).

Subsequent `log_ingest()`, `log_train()`, and `log_predict()` calls emit INFO
records on the package logger, which are handled by both handlers.
