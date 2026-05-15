"""Flask REST API exposing the forecasting and logging endpoints."""

import os

import pandas as pd
from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ai_enterprise_workflow.core.config import DIRECTORY_LOGS
from ai_enterprise_workflow.forecasting.arima import model

app = Flask(__name__)
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"


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
        return "Error: No date parameter was provided."
    # Check country parameter in request
    country = request.args.get("country", None)
    # Check duration parameter in request
    if "duration" in request.args:
        duration = request.args["duration"]
        duration = 30 if duration == "" else int(duration)
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
        >>> import pandas as pd
        >>> from ai_enterprise_workflow.service.api import app
        >>> client = app.test_client()
        >>> target = "ai_enterprise_workflow.service.api.pd.read_csv"
        >>> mock_df = pd.DataFrame({"col": [1]})
        >>> with patch(target, return_value=mock_df):
        ...     r = client.post("/logs?type=predict")
        >>> "data" in r.get_json()
        True
    """
    if "type" in request.args:
        log_type = request.args["type"]
    else:
        return "Error: No type parameter was provided."
    if log_type == "ingest":
        logs = pd.read_csv(DIRECTORY_LOGS + "ingest.csv").to_dict()
    elif log_type == "train":
        logs = pd.read_csv(DIRECTORY_LOGS + "train.csv").to_dict()
    elif log_type == "predict":
        logs = pd.read_csv(DIRECTORY_LOGS + "predict.csv").to_dict()
    else:
        return "Error: Invalid type parameter was provided."
    return jsonify({"data": logs})
