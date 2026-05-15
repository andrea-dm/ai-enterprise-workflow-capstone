"""Flask REST API exposing the forecasting and logging endpoints."""

import pandas as pd
from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ai_enterprise_workflow.core.config import DIRECTORY_LOGS
from ai_enterprise_workflow.forecasting.arima import model

app = Flask(__name__)
app.config["DEBUG"] = True


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
