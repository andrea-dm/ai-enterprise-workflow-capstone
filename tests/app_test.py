"""Flask application endpoint tests for /predict and /logs routes."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from ai_enterprise_workflow.service.api import app


class AppTest(unittest.TestCase):
    """Tests for the Flask REST API endpoints."""

    def setUp(self) -> None:
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("ai_enterprise_workflow.service.api.model")
    def test_01_app_predict_country(self, mock_model: MagicMock) -> None:
        """POST /predict returns JSON data key when country is specified."""
        # Arrange
        mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
        # Act
        response = self.client.post(
            "/predict?date=2018-11-20&duration=30&country=Australia"
        )
        # Assert
        assert "data" in response.get_json()

    @patch("ai_enterprise_workflow.service.api.model")
    def test_02_app_predict_total(self, mock_model: MagicMock) -> None:
        """POST /predict returns JSON data key when no country is specified."""
        # Arrange
        mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
        # Act
        response = self.client.post("/predict?date=2018-11-20&duration=30")
        # Assert
        assert "data" in response.get_json()

    @patch("ai_enterprise_workflow.service.api.pd.read_csv")
    def test_03_app_logs(self, mock_read_csv: MagicMock) -> None:
        """POST /logs returns JSON data key for a valid log type."""
        # Arrange
        mock_read_csv.return_value = pd.DataFrame({"type": ["predict"]})
        # Act
        response = self.client.post("/logs?type=predict")
        # Assert
        assert "data" in response.get_json()
