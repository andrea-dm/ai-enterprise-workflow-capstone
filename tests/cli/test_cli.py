"""Unit tests for cli.main() dispatch."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from ai_enterprise_workflow.cli import main

_INGEST_TARGET = "ai_enterprise_workflow.ingestion.pipeline.ingest"
_MODEL_TARGET = "ai_enterprise_workflow.forecasting.arima.model"
_APP_TARGET = "ai_enterprise_workflow.service.api.app"


@pytest.mark.unit
class TestCli:
    def test_cli_ingest_invokes_pipeline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dispatches 'ingest' subcommand to pipeline.ingest and returns 0."""
        monkeypatch.setattr(sys, "argv", ["ai_enterprise_workflow", "ingest"])
        mock_ingest = MagicMock()
        with patch(_INGEST_TARGET, mock_ingest):
            result = main()
        assert result == 0
        mock_ingest.assert_called_once_with(force=False)

    def test_cli_train_invokes_arima_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dispatches 'train' subcommand to arima.model with the given date."""
        monkeypatch.setattr(
            sys, "argv", ["ai_enterprise_workflow", "train", "--date", "2019-01-01"]
        )
        mock_model = MagicMock(return_value={"arima": 1.0})
        with patch(_MODEL_TARGET, mock_model):
            result = main()
        assert result == 0
        mock_model.assert_called_once_with("2019-01-01", 30, None)

    def test_cli_predict_invokes_arima_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dispatches 'predict' subcommand with all flags to arima.model."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ai_enterprise_workflow",
                "predict",
                "--date",
                "2019-01-01",
                "--duration",
                "14",
                "--country",
                "UK",
            ],
        )
        mock_model = MagicMock(return_value={"forecast": [1.0]})
        with patch(_MODEL_TARGET, mock_model):
            result = main()
        assert result == 0
        mock_model.assert_called_once_with("2019-01-01", 14, "UK")

    def test_cli_serve_starts_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dispatches 'serve' subcommand and calls app.run exactly once."""
        monkeypatch.setattr(sys, "argv", ["ai_enterprise_workflow", "serve"])
        mock_app = MagicMock()
        with patch(_APP_TARGET, mock_app):
            result = main()
        assert result == 0
        mock_app.run.assert_called_once()

    def test_cli_missing_subcommand_returns_code_2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns exit code 2 when no subcommand is provided."""
        monkeypatch.setattr(sys, "argv", ["ai_enterprise_workflow"])
        result = main()
        assert result == 2
