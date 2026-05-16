"""Flask REST API exposing the forecasting and logging endpoints."""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.forecasting.arima import model

app = Flask(__name__)
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

# Module-level alias
DIRECTORY_LOGS: Path = cfg.directory_logs


def _read_log_events(
    log_dir: Path,
    event_type: str,
) -> list[dict[str, object]]:
    """Read JSONL log events filtered by event type.

    Args:
        log_dir: Directory containing the ``events.jsonl`` log file.
        event_type: Value of the ``event`` field used to filter records.

    Returns:
        List of log-record dicts whose ``event`` field matches
        ``event_type``. Malformed lines are silently skipped.

    Notes:
        Reads ``events.jsonl`` from disk via :meth:`~pathlib.Path.read_text`.
        Returns an empty list without raising if the file does not exist.
    """
    log_file = log_dir / "events.jsonl"
    if not log_file.exists():
        return []
    records: list[dict[str, object]] = []
    for raw_line in log_file.read_text().splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            record: dict[str, object] = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if record.get("event") == event_type:
            records.append(record)
    return records


@app.route("/healthz", methods=["GET"])
def healthz() -> ResponseReturnValue:
    """Liveness probe endpoint.

    Returns:
        JSON ``{"status": "ok"}`` with HTTP 200.

    Examples:
        >>> from ai_enterprise_workflow.service.api import app
        >>> client = app.test_client()
        >>> r = client.get("/healthz")
        >>> r.get_json()
        {'status': 'ok'}
        >>> r.status_code
        200
    """
    return jsonify({"status": "ok"})


@app.route("/predict", methods=["POST"])
def predict() -> ResponseReturnValue:
    """Run the ARIMA/SARIMA forecast for the given query parameters.

    Returns:
        JSON response with ``{"data": result}`` on success, or an error string.

    Notes:
        Reads query parameters from the request:

        - ``date`` (required): forecast origin date (``YYYY-MM-DD``).
        - ``duration`` (optional): number of days to forecast; defaults to
          ``30``.
        - ``country`` (optional): country name; omit for global totals.

    Examples:
        >>> from unittest.mock import patch
        >>> from ai_enterprise_workflow.service.api import app
        >>> client = app.test_client()
        >>> target = "ai_enterprise_workflow.service.api.model"
        >>> with patch(target, return_value={"arima": 1.0}):
        ...     r = client.post("/predict?date=2019-01-01")
        >>> "data" in r.get_json()
        True
    """
    # Check date parameter in request
    if "date" in request.args:
        date = request.args["date"]
    else:
        return jsonify({"error": "No date parameter was provided."}), 400
    # Check country parameter in request
    country = request.args.get("country", None)
    # Check duration parameter in request
    if "duration" in request.args:
        _duration_raw = request.args["duration"]
        if _duration_raw == "":
            duration = 30
        else:
            try:
                duration = int(_duration_raw)
            except ValueError:
                return jsonify({"error": "duration must be an integer."}), 422
    else:
        duration = 30
    # Call model with parameters
    result = model(date, duration, country)
    # Return result
    return jsonify({"data": result})


@app.route("/logs", methods=["POST"])
def logs() -> ResponseReturnValue:
    """Return the requested log file as JSON.

    Returns:
        JSON response with ``{"data": log_rows}`` on success, or an error string.

    Notes:
        Reads query parameters from the request:

        - ``type`` (required): log category; one of ``"ingest"``,
          ``"train"``, or ``"predict"``.

    Examples:
        >>> from unittest.mock import patch
        >>> from ai_enterprise_workflow.service.api import app
        >>> client = app.test_client()
        >>> target = "ai_enterprise_workflow.service.api._read_log_events"
        >>> with patch(target, return_value=[{"event": "predict"}]):
        ...     r = client.post("/logs?type=predict")
        >>> "data" in r.get_json()
        True
    """
    if "type" in request.args:
        log_type = request.args["type"]
    else:
        return jsonify({"error": "No type parameter was provided."}), 400
    if log_type in ("ingest", "train", "predict"):
        log_records = _read_log_events(DIRECTORY_LOGS, log_type)
    else:
        return jsonify({"error": "Invalid type parameter was provided."}), 422
    return jsonify({"data": log_records})
