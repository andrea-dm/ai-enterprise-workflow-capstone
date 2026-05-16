"""Package-level event logging for the AI Enterprise Workflow service.

This module replaces ``core/logging.py`` with a proper stdlib-based logging
implementation that:

- Provides :func:`get_logger` — returns child loggers of the package root.
- Provides :func:`setup_logging` — attaches ``StreamHandler`` and optional
  ``FileHandler`` (JSONL) to the package root logger.
- Exposes :func:`log_ingest`, :func:`log_train`, :func:`log_predict` as
  structured event emitters writing one JSON object per line to
  ``<log_dir>/events.jsonl``.

Notes:
    This module avoids the name ``logging.py`` to prevent shadowing the
    standard-library :mod:`logging` module (D1).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from logging import FileHandler, Formatter, Logger, StreamHandler, getLogger
from pathlib import Path

from ai_enterprise_workflow.core.config import cfg

PACKAGE_LOGGER_NAME: str = "ai_enterprise_workflow"
"""Namespace root for all package loggers."""

_STDLIB_LOG_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)
"""Standard :class:`~logging.LogRecord` attribute names excluded from JSONL output."""

_logger: Logger = getLogger(PACKAGE_LOGGER_NAME)


class _JsonlFormatter(Formatter):
    """Format :class:`~logging.LogRecord` instances as single-line JSON objects.

    Each record serialises to a JSON object with keys ``timestamp``, ``level``,
    ``logger``, ``message``, plus any extra fields injected via ``extra=`` on
    the log call.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Return the log record serialised as a single JSON line.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string without a trailing newline.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STDLIB_LOG_KEYS:
                payload[key] = value
        return json.dumps(payload)


def get_logger(name: str) -> Logger:
    """Return a child logger scoped under the package namespace.

    Args:
        name: Module name, typically ``__name__``. Automatically prefixed
            with ``"ai_enterprise_workflow."`` unless already namespaced.

    Returns:
        A :class:`~logging.Logger` that inherits handlers from the package
        root logger configured by :func:`setup_logging`.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.name.startswith("ai_enterprise_workflow")
        True

    See Also:
        :func:`setup_logging`: Configures the package root logger that child
            loggers created here inherit from.
    """
    if name.startswith(PACKAGE_LOGGER_NAME):
        return getLogger(name)
    return getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")


def setup_logging(
    level: int = logging.INFO,
    log_dir: Path | None = None,
) -> None:
    """Configure the package-level logger for this process.

    Attaches a :class:`~logging.StreamHandler` (always) and, when *log_dir*
    is provided, a :class:`~logging.FileHandler` writing JSONL records to
    ``<log_dir>/events.jsonl``. Clears existing handlers first to prevent
    duplicate output on repeated calls.

    Args:
        level: Numeric log level for the package logger and all handlers
            (default: :data:`logging.INFO`).
        log_dir: Directory for the ``events.jsonl`` file. Created if absent.
            Pass ``None`` to disable file logging.

    Examples:
        >>> import pathlib, tempfile
        >>> with tempfile.TemporaryDirectory() as tmp:  # doctest: +SKIP
        ...     setup_logging(log_dir=pathlib.Path(tmp))

    See Also:
        :func:`get_logger`: Returns child loggers configured by this function.
    """
    pkg_logger = getLogger(PACKAGE_LOGGER_NAME)
    pkg_logger.setLevel(level)
    pkg_logger.handlers.clear()
    stream_handler = StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(
        Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    pkg_logger.addHandler(stream_handler)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = FileHandler(log_dir / "events.jsonl", encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(_JsonlFormatter())
        pkg_logger.addHandler(file_handler)


def log_ingest(shape: tuple[int, ...]) -> None:
    """Emit a structured ingestion event to the package logger.

    Args:
        shape: Shape of the ingested dataset (e.g. ``(rows, cols)``).

    Notes:
        Emits an :data:`logging.INFO` record with
        ``extra={"event": "ingest", "shape": list(shape), …}``.
        Written to ``events.jsonl`` when :func:`setup_logging` has been
        called with a *log_dir*.

    Examples:
        >>> log_ingest((100, 9))  # doctest: +SKIP

    See Also:
        :func:`log_train`: Emits a structured training event.
        :func:`log_predict`: Emits a structured prediction event.
    """
    _logger.info(
        "ingest event",
        extra={
            "event": "ingest",
            "id": str(uuid.uuid4())[:8],
            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
            "shape": list(shape),
        },
    )


def log_train(
    model: str,
    shape: tuple[int, ...],
    performance: Mapping[str, object],
    version: float = cfg.version,
) -> None:
    """Emit a structured training event to the package logger.

    Args:
        model: Model name or identifier (e.g. ``"arima"``).
        shape: Shape of the training dataset.
        performance: Performance metrics dictionary.
        version: Package version recorded in the log entry.

    Notes:
        Emits an :data:`logging.INFO` record with
        ``extra={"event": "train", "model": model, …}``.

    Examples:
        >>> log_train("arima", (100,), {"rmse": 1.5})  # doctest: +SKIP

    See Also:
        :func:`log_ingest`: Emits a structured ingestion event.
        :func:`log_predict`: Emits a structured prediction event.
    """
    _logger.info(
        "train event",
        extra={
            "event": "train",
            "id": str(uuid.uuid4())[:8],
            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
            "version": version,
            "model": model,
            "shape": list(shape),
            "performance": dict(performance),
        },
    )


def log_predict(
    model: str,
    query: Mapping[str, object],
    prediction: Mapping[str, object],
    version: float = cfg.version,
) -> None:
    """Emit a structured prediction event to the package logger.

    Args:
        model: Model name or identifier.
        query: Query parameters used for the prediction.
        prediction: Prediction output mapping.
        version: Package version recorded in the log entry.

    Notes:
        Emits an :data:`logging.INFO` record with
        ``extra={"event": "predict", "model": model, …}``.

    Examples:
        >>> log_predict(  # doctest: +SKIP
        ...     "arima", {"start": 0, "end": 30}, {"revenue": 1000.0}
        ... )

    See Also:
        :func:`log_ingest`: Emits a structured ingestion event.
        :func:`log_train`: Emits a structured training event.
    """
    _logger.info(
        "predict event",
        extra={
            "event": "predict",
            "id": str(uuid.uuid4())[:8],
            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
            "version": version,
            "model": model,
            "query": dict(query),
            "prediction": dict(prediction),
        },
    )
