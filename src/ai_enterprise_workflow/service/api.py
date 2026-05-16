"""Flask REST API exposing the forecasting and logging endpoints."""

import datetime
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.forecasting.arima import model

# Module-level alias — patched in tests via monkeypatch.setattr
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


def predict() -> ResponseReturnValue:
    """Run the ARIMA/SARIMA forecast for the given query parameters.

    Returns:
        JSON response with keys ``"data"`` (forecast result dict) and
        ``"drift_warning"`` (``True`` when the Wasserstein drift score exceeds
        ``cfg.drift_threshold``) on success, or an error JSON on failure.

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
        >>> mock_ret = {"arima": 1.0, "sarima": 2.0, "drift": 0.05}
        >>> with patch(target, return_value=mock_ret):
        ...     r = client.post("/predict?date=2019-01-01")
        >>> "data" in r.get_json()
        True
    """
    # Check date parameter in request
    if "date" in request.args:
        date = request.args["date"]
    else:
        return jsonify({"error": "No date parameter was provided."}), 400
    # ISO 8601 date validation
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return jsonify({"error": f"Invalid date '{date}'. Expected YYYY-MM-DD."}), 422
    # Check country parameter in request
    country = request.args.get("country", None)
    # Check duration parameter in request
    if "duration" in request.args:
        raw_duration = request.args["duration"]
        try:
            duration = 30 if raw_duration == "" else int(raw_duration)
        except ValueError:
            return jsonify({"error": "duration must be a positive integer."}), 422
        if duration <= 0:
            return jsonify({"error": "duration must be a positive integer."}), 422
    else:
        duration = 30
    # Call model with parameters
    result = model(date, duration, country)
    # Return result
    return jsonify(
        {"data": result, "drift_warning": result["drift"] > cfg.drift_threshold}
    )


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


def readyz() -> ResponseReturnValue:
    """Readiness probe endpoint.

    Returns:
        JSON ``{"status": "ready"}`` with HTTP 200 when the ingested data
        artefact is present; JSON ``{"status": "not ready",
        "reason": "data not ingested"}`` with HTTP 503 otherwise.

    Notes:
        Checks for ``cfg.directory_output / "4 revenue_total.csv"`` — the
        sentinel file written by the ingestion pipeline.

    Examples:
        >>> from pathlib import Path
        >>> from unittest.mock import patch
        >>> from ai_enterprise_workflow.service.api import app
        >>> client = app.test_client()
        >>> with patch.object(Path, "exists", return_value=True):
        ...     r = client.get("/readyz")
        >>> r.get_json()
        {'status': 'ready'}
        >>> r.status_code
        200
    """
    csv_path = cfg.directory_output / "4 revenue_total.csv"
    if csv_path.exists():
        return jsonify({"status": "ready"}), 200
    return jsonify({"status": "not ready", "reason": "data not ingested"}), 503


def create_app(config: dict[str, object] | None = None) -> Flask:
    """Create and return a configured Flask application instance.

    Args:
        config: Optional mapping of Flask configuration overrides applied
            after defaults (e.g. ``{"TESTING": True}``).

    Returns:
        Configured :class:`~flask.Flask` application with all routes
        registered via :func:`~flask.Flask.add_url_rule`.

    Notes:
        Reads ``FLASK_DEBUG`` from the environment to set the ``DEBUG``
        flag; defaults to ``False`` when the variable is absent or not
        ``"1"``.

    Examples:
        >>> flask_app = create_app({"TESTING": True})
        >>> flask_app.config["TESTING"]
        True
    """
    flask_app = Flask(__name__)
    flask_app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"
    if config:
        flask_app.config.update(config)  # type: ignore[reportUnknownMemberType]
    flask_app.add_url_rule("/healthz", "healthz", healthz, methods=["GET"])
    flask_app.add_url_rule("/predict", "predict", predict, methods=["POST"])
    flask_app.add_url_rule("/logs", "logs", logs, methods=["POST"])
    flask_app.add_url_rule("/readyz", "readyz", readyz, methods=["GET"])
    return flask_app


app: Flask = create_app()
