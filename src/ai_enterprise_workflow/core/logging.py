"""CSV-file event logger for ingestion / training / prediction stages.

Note:
    The module name shadows the stdlib ``logging`` package. The module
    deliberately avoids ``import logging`` to keep the shadow harmless.
"""

import csv
import os
import uuid
from datetime import datetime

from ai_enterprise_workflow.core.config import DIRECTORY_LOGS, VERSION


def log_common(log_file, log_data, headers, directory_logs):  # noqa: ANN001
    """Append a row to a CSV log file, writing the header row on first write.

    Args:
        log_file: Base filename of the log (e.g. ``"ingest.csv"``).
        log_data: Row values to write.
        headers: Column header names used when creating a new file.
        directory_logs: Directory path where the log file lives.
    """
    header = False
    if not os.path.exists(directory_logs):
        os.makedirs(directory_logs)
    if not os.path.exists(directory_logs + log_file):
        header = True
    with open(directory_logs + log_file, "a", newline="") as file:
        writer = csv.writer(file)
        if header:
            writer.writerow(headers)
        writer.writerow(log_data)


def log_ingest(shape):  # noqa: ANN001
    """Write an ingestion event to the ingest log.

    Args:
        shape: Shape of the ingested dataset.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "ingest.csv"
    log_data = list(map(str, [_id, now, shape]))
    headers = ["id", "time", "shape"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)


def log_train(model, shape, performance, version=VERSION):  # noqa: ANN001
    """Write a training event to the train log.

    Args:
        model: Model name or identifier.
        shape: Shape of the training dataset.
        performance: Performance metrics dictionary.
        version: Package version string.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "train.csv"
    log_data = list(map(str, [_id, now, version, model, shape, performance]))
    headers = ["id", "time", "version", "model", "shape", "performance"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)


def log_predict(model, query, prediction, version=VERSION):  # noqa: ANN001
    """Write a prediction event to the predict log.

    Args:
        model: Model name or identifier.
        query: Query parameters used for the prediction.
        prediction: Prediction output.
        version: Package version string.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "predict.csv"
    log_data = list(map(str, [_id, now, version, model, query, prediction]))
    headers = ["id", "time", "version", "model", "query", "prediction"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)
