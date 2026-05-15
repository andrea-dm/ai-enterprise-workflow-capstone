import unittest
from unittest.mock import patch

import pandas as pd

from ai_enterprise_workflow.service.api import app


class AppTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("ai_enterprise_workflow.service.api.model")
    def test_01_app_predict_country(self, mock_model):
        mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
        response = self.client.post(
            "/predict?date=2018-11-20&duration=30&country=Australia"
        )
        assert "data" in response.get_json()

    @patch("ai_enterprise_workflow.service.api.model")
    def test_02_app_predict_total(self, mock_model):
        mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
        response = self.client.post("/predict?date=2018-11-20&duration=30")
        assert "data" in response.get_json()

    @patch("ai_enterprise_workflow.service.api.pd.read_csv")
    def test_03_app_logs(self, mock_read_csv):
        mock_read_csv.return_value = pd.DataFrame({"type": ["predict"]})
        response = self.client.post("/logs?type=predict")
        assert "data" in response.get_json()
