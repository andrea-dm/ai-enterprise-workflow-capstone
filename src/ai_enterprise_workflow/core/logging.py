"""CSV-file event logger for ingestion / training / prediction stages.

Notes:
    The module name shadows the stdlib ``logging`` package. The module
    deliberately avoids ``import logging`` to keep the shadow harmless.
"""

import csv
import os
import uuid
from collections.abc import Mapping
from datetime import datetime

from ai_enterprise_workflow.core.config import DIRECTORY_LOGS, VERSION


def log_common(
    log_file: str,
    log_data: list[str],
    headers: list[str],
    directory_logs: str,
) -> None:
    """Append a row to a CSV log file, writing the header row on first write.

    Args:
        log_file: Base filename of the log (e.g. ``"ingest.csv"``).
        log_data: Row values to write.
        headers: Column header names used when creating a new file.
        directory_logs: Directory path where the log file lives.

    Notes:
        Creates ``directory_logs`` if it does not exist. Opens the log
        file in append mode, writing the header row only on the first
        write.
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


def log_ingest(shape: tuple[int, ...]) -> None:
    """Write an ingestion event to the ingest log.

    Args:
        shape: Shape of the ingested dataset.

    Notes:
        Writes to the ingest log via :func:`log_common`.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "ingest.csv"
    log_data = list(map(str, [_id, now, shape]))
    headers = ["id", "time", "shape"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)


def log_train(
    model: str,
    shape: tuple[int, ...],
    performance: Mapping[str, object],
    version: float = VERSION,
) -> None:
    """Write a training event to the train log.

    Args:
        model: Model name or identifier.
        shape: Shape of the training dataset.
        performance: Performance metrics dictionary.
        version: Package version number.

    Notes:
        Writes to the train log via :func:`log_common`.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "train.csv"
    log_data = list(map(str, [_id, now, version, model, shape, performance]))
    headers = ["id", "time", "version", "model", "shape", "performance"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)


def log_predict(
    model: str,
    query: Mapping[str, object],
    prediction: Mapping[str, object],
    version: float = VERSION,
) -> None:
    """Write a prediction event to the predict log.

    Args:
        model: Model name or identifier.
        query: Query parameters used for the prediction.
        prediction: Prediction output.
        version: Package version number.

    Notes:
        Writes to the predict log via :func:`log_common`.
    """
    now = datetime.now()
    _id = str(uuid.uuid4())[:8]
    log_file = "predict.csv"
    log_data = list(map(str, [_id, now, version, model, query, prediction]))
    headers = ["id", "time", "version", "model", "query", "prediction"]
    log_common(log_file, log_data, headers, DIRECTORY_LOGS)
