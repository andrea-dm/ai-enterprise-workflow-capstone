"""Typed configuration for the AI Enterprise Workflow service.

All path fields default to relative paths suitable for running from the
repository root. Override individual fields via environment variables or
a ``.env`` file in the working directory.

Attributes:
    cfg: Process-level singleton. Import this in all application code.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables or a ``.env`` file.

    Attributes:
        version: Package version number. Override via ``APP_VERSION``.
        directory_input: Source JSON invoice files directory.
            Override via ``DIRECTORY_INPUT``.
        directory_output: Processed CSV output directory.
            Override via ``DIRECTORY_OUTPUT``.
        directory_models: Trained model artefacts directory.
            Override via ``DIRECTORY_MODELS``.
        directory_logs: JSONL event log directory.
            Override via ``DIRECTORY_LOGS``.
        app_base_url: Base URL for internal API references.
            Override via ``APP_BASE_URL``.
        KEYS: Ordered tuple of canonical invoice column names.
            Not env-configurable (ClassVar).
        KEY_NAMES: Source-to-canonical column name mapping.
            Not env-configurable (ClassVar).
        KEY_TYPES: Canonical column name to Python type mapping.
            Not env-configurable (ClassVar).

    Examples:
        >>> from ai_enterprise_workflow.core.config import cfg
        >>> isinstance(cfg.version, float)
        True
        >>> cfg.directory_input.name
        'input'

    See Also:
        `Implementation Design <advanced/implementation_design.md>`_:
            Configuration layer architecture and override mechanism.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    version: float = Field(default=0.1, validation_alias="APP_VERSION")
    directory_input: Path = Field(
        default=Path("data/input"), validation_alias="DIRECTORY_INPUT"
    )
    directory_output: Path = Field(
        default=Path("data/output"), validation_alias="DIRECTORY_OUTPUT"
    )
    directory_models: Path = Field(
        default=Path("models"), validation_alias="DIRECTORY_MODELS"
    )
    directory_logs: Path = Field(
        default=Path("logs"), validation_alias="DIRECTORY_LOGS"
    )
    app_base_url: str = Field(
        default="http://127.0.0.1/", validation_alias="APP_BASE_URL"
    )

    # ── Schema constants (ClassVar: excluded from Pydantic validation and env) ── #

    KEYS: ClassVar[tuple[str, ...]] = (
        "invoice_id",
        "customer_id",
        "stream_id",
        "price",
        "view_count",
        "country",
        "year",
        "month",
        "day",
    )
    KEY_NAMES: ClassVar[dict[str, str]] = {
        "invoice": "invoice_id",
        "customer_id": "customer_id",
        "stream_id": "stream_id",
        "price": "price",
        "times_viewed": "view_count",
        "country": "country",
        "year": "year",
        "month": "month",
        "day": "day",
        "total_price": "price",
        "TimesViewed": "view_count",
        "StreamID": "stream_id",
    }
    KEY_TYPES: ClassVar[dict[str, type[int | float | str]]] = {
        "invoice_id": int,
        "customer_id": int,
        "stream_id": int,
        "price": float,
        "view_count": int,
        "country": str,
        "year": int,
        "month": int,
        "day": int,
    }


cfg: AppSettings = AppSettings()
