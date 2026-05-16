# Quickstart

## 1. Install

```bash
uv sync
```

## 2. Run ingestion

```bash
python -c "from ai_enterprise_workflow.ingestion import ingest; ingest()"
```

Expected output: five CSV files written to `data/output/`.

## 3. Run a forecast

```bash
python -c "
from ai_enterprise_workflow.forecasting import model
result = model('2019-01-01', duration=30)
print(result)
"
```

Expected output: a dict with `arima` and `sarima` keys containing predicted
revenue sums.

## 4. Start the API server

```bash
python run.py
```

Then query the forecast endpoint:

```bash
curl -X POST 'http://localhost:80/predict?date=2019-01-01&duration=30'
```

Expected response:

```json
{"data": {"arima": 12345.6, "sarima": 12300.0}}
```
